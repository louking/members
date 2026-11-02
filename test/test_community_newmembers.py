'''
test_community_newmembers - test members.community.RsuClubNewMembersCommunitySyncManager (#739)
=========================================================
'''

# standard
from datetime import datetime, timedelta, timezone

# pypi
import pytest

# homegrown
from members import community
from members.community import RsuClubNewMembersCommunitySyncManager
from members.model import db, LocalInterest, RsuClubSyncState
from loutilities.user.model import Interest
from fakediscourse import FakeDiscourse


CLUBID = '1234'
GROUP = 'club-members'
GROUPID = 7
INVITE_COLUMNS = ['id', 'email', 'deleted_at', 'invalidated_at', 'redemption_count', 'expires_at']


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return dict(self._data)


class FakeRsu:
    '''stands in for RunSignupFluent's rsu.club._(id).members.params({...}).get()

    :param members: every club member record, served results_per_page at a time
    '''
    def __init__(self, members):
        self._members = members
        self.calls = []
        self._params = None

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return self

    def _(self, arg):
        return self

    def params(self, params):
        self._params = params
        return self

    def get(self):
        self.calls.append(self._params)
        per_page = self._params['results_per_page']
        start = (self._params['page'] - 1) * per_page
        return _FakeResponse({'club_members': self._members[start:start + per_page]})


def _member(email, membership_id):
    return {'membership_id': membership_id, 'user': {'email': email}}


# members already in the club before the stored membership_id
OLD_MEMBERS = [_member('old1@example.com', 100), _member('old2@example.com', 101)]


@pytest.fixture
def interestsetup(bare_dbapp, bareapp):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()
    bareapp.config['DISCOURSE_API_INVITES_QUERY_FSRC'] = 10
    bareapp.config['DISCOURSE_API_INVITE_GROUPS_QUERY_FSRC'] = 11
    bareapp.config['DISCOURSE_API_USER_EMAIL_QUERY_FSRC'] = 12
    return localinterest


def _store(localinterest, last_membership_id, groupname=GROUP):
    state = RsuClubSyncState(interest=localinterest, club_id=int(CLUBID), groupname=groupname,
                             last_membership_id=last_membership_id, last_checked_at=datetime(2026, 11, 1, 12, 0, 0))
    db.session.add(state)
    db.session.commit()
    return state


def _responses(email_rows=(), invite_rows=(), invitegroup_rows=(), users=None):
    '''FakeDiscourse responses for an incremental run

    :param email_rows: [email, user_id] rows for the email lookup query
    :param users: dict of user id -> admin user record
    '''
    responses = {
        'groups.json': lambda params: {'groups': [{'id': GROUPID, 'name': GROUP}]},
        'admin.plugins.explorer.queries.10.run': lambda body: {'columns': INVITE_COLUMNS, 'rows': list(invite_rows),
                                                                'result_count': len(invite_rows)},
        'admin.plugins.explorer.queries.11.run': lambda body: {'columns': ['invite_id', 'group_id'],
                                                                'rows': list(invitegroup_rows),
                                                                'result_count': len(invitegroup_rows)},
        'admin.plugins.explorer.queries.12.run': lambda body: {'columns': ['email', 'user_id'],
                                                                'rows': list(email_rows),
                                                                'result_count': len(email_rows)},
        'invites.json': lambda body: {},
        (f'groups.{GROUPID}.members.json', 'put'): lambda body: {},
    }
    for userid, user in (users or {}).items():
        responses[f'admin.users.{userid}.json'] = user
    for row in invite_rows:
        responses[(f'invites.{row[0]}', 'put')] = lambda body: {}
    return responses


def _run(monkeypatch, tmp_path, members, responses, dryrun=False, after_membership_id=None):
    rsu = FakeRsu(members)
    fake = FakeDiscourse(responses)
    monkeypatch.setattr(community, 'make_runsignup_fluent_client', lambda: rsu)
    monkeypatch.setattr(community, 'make_discourse_client', lambda interest: fake)
    monkeypatch.setattr(community, 'COMMUNITY_LOCKFILE', str(tmp_path / 'lock'))
    mgr = RsuClubNewMembersCommunitySyncManager('fsrc', CLUBID, GROUP, skipemail=True, dryrun=dryrun)
    counts = mgr.import_new(after_membership_id=after_membership_id)
    return counts, rsu, fake


def _writes(fake):
    return [c for c in fake._calls if c[1] in ('put', 'delete') or (c[1] == 'post' and not c[0].endswith('.run'))]


def test_first_run_records_highest_membership_id_and_adds_nobody(interestsetup, monkeypatch, tmp_path):
    counts, rsu, fake = _run(monkeypatch, tmp_path, OLD_MEMBERS, _responses())

    assert counts['initialized'] == 101
    assert counts['new'] == 0
    assert len(rsu.calls) == 1
    assert rsu.calls[0]['current_members_only'] == 'T'
    assert rsu.calls[0]['results_per_page'] == community.CLUB_MEMBERS_PER_PAGE
    assert fake._calls == []

    state = RsuClubSyncState.query.one()
    assert state.club_id == int(CLUBID)
    assert state.groupname == GROUP
    assert state.last_membership_id == 101


def test_no_new_members_makes_one_rsu_call_and_no_discourse_calls(interestsetup, monkeypatch, tmp_path):
    state = _store(interestsetup, 101)

    counts, rsu, fake = _run(monkeypatch, tmp_path, OLD_MEMBERS, _responses())

    assert counts == {'new': 0, 'added': 0, 'invited': 0, 'unchanged': 0, 'initialized': None}
    assert len(rsu.calls) == 1
    assert fake._calls == []
    assert state.last_membership_id == 101
    assert state.last_checked_at > datetime(2026, 11, 1, 12, 0, 0)


def test_full_page_fetches_next_page(interestsetup, monkeypatch, tmp_path):
    _store(interestsetup, 101)
    monkeypatch.setattr(community, 'CLUB_MEMBERS_PER_PAGE', 2)

    counts, rsu, fake = _run(monkeypatch, tmp_path, OLD_MEMBERS + [_member('new@example.com', 102)],
                             _responses(email_rows=[['new@example.com', 42]],
                                        users={42: {'id': 42, 'username': 'new', 'groups': []}}))

    assert [c['page'] for c in rsu.calls] == [1, 2]
    assert counts['new'] == 1
    assert RsuClubSyncState.query.one().last_membership_id == 102


def test_stored_membership_id_kept_when_highest_membership_ends(interestsetup, monkeypatch, tmp_path):
    '''the member with the stored membership_id is no longer current'''
    state = _store(interestsetup, 150)

    counts, rsu, fake = _run(monkeypatch, tmp_path, OLD_MEMBERS, _responses())

    assert counts['new'] == 0
    assert state.last_membership_id == 150


def test_state_is_per_club_and_group(interestsetup, monkeypatch, tmp_path):
    other = _store(interestsetup, 50, groupname='other-group')

    _run(monkeypatch, tmp_path, OLD_MEMBERS, _responses())

    assert RsuClubSyncState.query.count() == 2
    assert other.last_membership_id == 50


def test_new_members_added_invited_or_left_alone(interestsetup, monkeypatch, tmp_path):
    '''bob has an account not in the group (added), carol has an account already in the
    group (left alone), alice has no account (invited). Old members are ignored and
    nothing is ever removed.'''
    state = _store(interestsetup, 101)
    invite_posts = []
    responses = _responses(
        email_rows=[['bob@example.com', 42], ['carol@example.com', 99]],
        users={
            42: {'id': 42, 'username': 'bob', 'groups': [{'id': 3, 'name': 'trust_level_0'}]},
            99: {'id': 99, 'username': 'carol', 'groups': [{'id': GROUPID, 'name': GROUP}]},
        },
    )
    responses['invites.json'] = lambda body: invite_posts.append(body) or {}
    members = OLD_MEMBERS + [_member('Bob@example.com', 102), _member('carol@example.com', 103),
                             _member('alice@example.com', 104)]

    counts, rsu, fake = _run(monkeypatch, tmp_path, members, responses)

    assert counts == {'new': 3, 'added': 1, 'invited': 1, 'unchanged': 1, 'initialized': None}
    puts = [c for c in fake._calls if c[0] == f'groups.{GROUPID}.members.json' and c[1] == 'put']
    assert len(puts) == 1
    assert puts[0][2]['usernames'] == 'bob'
    assert [c for c in fake._calls if c[1] == 'delete'] == []
    assert len(invite_posts) == 1
    assert invite_posts[0]['email'] == 'alice@example.com'
    assert invite_posts[0]['group_ids'] == GROUPID
    # only the new members' accounts are looked up, never the full user list
    assert not any(c[0] == 'admin.users.json' for c in fake._calls)
    assert {c[0] for c in fake._calls if c[0].startswith('admin.users.')} == {'admin.users.42.json', 'admin.users.99.json'}
    assert state.last_membership_id == 104


def test_family_membership_members_share_membership_id(interestsetup, monkeypatch, tmp_path):
    '''every member of a new family membership is new, though they share one membership_id'''
    _store(interestsetup, 101)
    invite_posts = []
    responses = _responses()
    responses['invites.json'] = lambda body: invite_posts.append(body) or {}
    members = OLD_MEMBERS + [_member('parent@example.com', 102), _member('kid@example.com', 102)]

    counts, rsu, fake = _run(monkeypatch, tmp_path, members, responses)

    assert counts['new'] == 2
    assert sorted(p['email'] for p in invite_posts) == ['kid@example.com', 'parent@example.com']


def test_invite_queries_skipped_when_every_new_member_has_an_account(interestsetup, monkeypatch, tmp_path):
    _store(interestsetup, 101)
    responses = _responses(
        email_rows=[['bob@example.com', 42]],
        users={42: {'id': 42, 'username': 'bob', 'groups': []}},
    )
    counts, rsu, fake = _run(monkeypatch, tmp_path, OLD_MEMBERS + [_member('bob@example.com', 102)], responses)

    assert counts['added'] == 1
    paths = {c[0] for c in fake._calls}
    assert 'admin.plugins.explorer.queries.10.run' not in paths
    assert 'admin.plugins.explorer.queries.11.run' not in paths


def test_existing_invite_gets_group_added(interestsetup, monkeypatch, tmp_path):
    '''alice already has an invite for another group; this group is added to it'''
    _store(interestsetup, 101)
    expires = (datetime.now(timezone.utc) + timedelta(days=100)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    invite_puts = []
    responses = _responses(
        invite_rows=[[5, 'alice@example.com', None, None, 0, expires]],
        invitegroup_rows=[[5, 20]],
    )
    responses[('invites.5', 'put')] = lambda body: invite_puts.append(body) or {}

    counts, rsu, fake = _run(monkeypatch, tmp_path, OLD_MEMBERS + [_member('alice@example.com', 102)], responses)

    assert counts['invited'] == 1
    assert len(invite_puts) == 1
    assert invite_puts[0]['group_ids'] == f'20,{GROUPID}'
    assert 'expires_at' not in invite_puts[0]


def test_existing_invite_already_for_group_is_unchanged(interestsetup, monkeypatch, tmp_path):
    _store(interestsetup, 101)
    expires = (datetime.now(timezone.utc) + timedelta(days=100)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    responses = _responses(
        invite_rows=[[5, 'alice@example.com', None, None, 0, expires]],
        invitegroup_rows=[[5, GROUPID]],
    )
    counts, rsu, fake = _run(monkeypatch, tmp_path, OLD_MEMBERS + [_member('alice@example.com', 102)], responses)

    assert counts == {'new': 1, 'added': 0, 'invited': 0, 'unchanged': 1, 'initialized': None}
    assert _writes(fake) == []


def test_dryrun_makes_no_writes_and_keeps_state(interestsetup, monkeypatch, tmp_path, capsys):
    state = _store(interestsetup, 101)
    responses = _responses(
        email_rows=[['bob@example.com', 42]],
        users={42: {'id': 42, 'username': 'bob', 'groups': []}},
    )
    members = OLD_MEMBERS + [_member('bob@example.com', 102), _member('alice@example.com', 103)]

    counts, rsu, fake = _run(monkeypatch, tmp_path, members, responses, dryrun=True)

    assert counts['added'] == 1
    assert counts['invited'] == 1
    assert _writes(fake) == []
    out = capsys.readouterr().out
    assert '[DRY RUN]' in out
    assert "add users ['bob']" in out
    assert 'create invite for alice@example.com' in out
    db.session.expire_all()
    assert RsuClubSyncState.query.one().last_membership_id == 101


def test_dryrun_first_run_stores_nothing(interestsetup, monkeypatch, tmp_path):
    counts, rsu, fake = _run(monkeypatch, tmp_path, OLD_MEMBERS, _responses(), dryrun=True)

    assert counts['initialized'] == 101
    assert RsuClubSyncState.query.count() == 0


def test_after_membership_id_overrides_stored_value(interestsetup, monkeypatch, tmp_path):
    '''with no stored state, --after-membership-id still treats members above it as new'''
    invite_posts = []
    responses = _responses()
    responses['invites.json'] = lambda body: invite_posts.append(body) or {}

    counts, rsu, fake = _run(monkeypatch, tmp_path, OLD_MEMBERS, responses, dryrun=True, after_membership_id=100)

    assert counts['initialized'] is None
    assert counts['new'] == 1
    assert counts['invited'] == 1
    assert invite_posts == []


def test_rsu_failure_leaves_state_alone(interestsetup, monkeypatch, tmp_path):
    _store(interestsetup, 101)

    class BrokenRsu(FakeRsu):
        def get(self):
            raise RuntimeError('RunSignup down')

    monkeypatch.setattr(community, 'make_runsignup_fluent_client', lambda: BrokenRsu([]))
    monkeypatch.setattr(community, 'make_discourse_client', lambda interest: FakeDiscourse({}))
    monkeypatch.setattr(community, 'COMMUNITY_LOCKFILE', str(tmp_path / 'lock'))
    mgr = RsuClubNewMembersCommunitySyncManager('fsrc', CLUBID, GROUP, skipemail=True)
    with pytest.raises(RuntimeError):
        mgr.import_new()

    db.session.expire_all()
    assert RsuClubSyncState.query.one().last_membership_id == 101
    # lock was released
    assert mgr.lock.acquire(blocking=False)
    mgr.lock.release()
