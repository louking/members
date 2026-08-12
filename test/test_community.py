'''
test_community - test members.community
=========================================================
'''

# standard
import json
from datetime import date

# pypi
import pytest
from flask import g

# homegrown
from members import community
from members.community import (
    _RateLimiter, _RateLimitedDiscourse, make_discourse_client, run_query_paged,
    DbTagCommunitySyncManager,
)
from members.model import db, LocalInterest, LocalUser, Position, Tag
from loutilities.user.model import Interest
from fakediscourse import FakeDiscourse


# ----------------------------------------------------------------------
# _RateLimiter
# ----------------------------------------------------------------------

@pytest.fixture
def ratelimit_files(tmp_path, monkeypatch):
    state_file = tmp_path / 'state.json'
    lock_file = tmp_path / 'state.lock'
    monkeypatch.setattr(community, '_RATE_LIMIT_STATE_FILE', state_file)
    monkeypatch.setattr(community, '_RATE_LIMIT_STATE_LOCKFILE', str(lock_file))
    return state_file


def test_ratelimiter_first_acquire_records_one_timestamp(ratelimit_files):
    rl = _RateLimiter(max_calls=5, window_secs=60)
    rl.acquire()
    calls = json.loads(ratelimit_files.read_text())
    assert len(calls) == 1


def test_ratelimiter_prunes_calls_outside_window(ratelimit_files, monkeypatch):
    fixed_now = 1_000_000.0
    monkeypatch.setattr(community.time, 'time', lambda: fixed_now)
    # three calls well outside a 60s window
    ratelimit_files.write_text(json.dumps([fixed_now - 1000, fixed_now - 2000, fixed_now - 3000]))

    rl = _RateLimiter(max_calls=1, window_secs=60)
    rl.acquire()

    calls = json.loads(ratelimit_files.read_text())
    assert calls == [fixed_now]


def test_ratelimiter_throttles_when_over_budget(ratelimit_files, monkeypatch, bareapp):
    fixed_now = 1_000_000.0
    monkeypatch.setattr(community.time, 'time', lambda: fixed_now)
    sleeps = []
    monkeypatch.setattr(community.time, 'sleep', lambda secs: sleeps.append(secs))
    # two calls already recorded, well within the 60s window
    ratelimit_files.write_text(json.dumps([fixed_now - 10, fixed_now - 5]))

    rl = _RateLimiter(max_calls=2, window_secs=60)
    with bareapp.app_context():
        rl.acquire()

    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(50.0)


# ----------------------------------------------------------------------
# _RateLimitedDiscourse
# ----------------------------------------------------------------------

class _CountingLimiter:
    def __init__(self):
        self.calls = 0

    def acquire(self):
        self.calls += 1


def test_ratelimiteddiscourse_rate_limits_terminal_http_calls():
    target = FakeDiscourse({'groups.5.members.json': {'ok': True}})
    rl = _CountingLimiter()
    proxy = _RateLimitedDiscourse(target, rl)

    result = proxy.groups._(5).members.json.get({'x': 1})

    assert result == {'ok': True}
    assert rl.calls == 1


def test_ratelimiteddiscourse_does_not_rate_limit_chain_building():
    target = FakeDiscourse({'a.b.json': 'value'})
    rl = _CountingLimiter()
    proxy = _RateLimitedDiscourse(target, rl)

    node = proxy.a.b  # attribute chaining only, no terminal HTTP call
    assert rl.calls == 0
    assert node.json.get() == 'value'
    assert rl.calls == 1


class _PrimitiveTarget:
    flag = True

    def method_returning_str(self):
        return 'plain string'


def test_ratelimiteddiscourse_passes_through_primitives_unwrapped():
    rl = _CountingLimiter()
    proxy = _RateLimitedDiscourse(_PrimitiveTarget(), rl)

    assert proxy.flag is True
    assert proxy.method_returning_str() == 'plain string'
    assert rl.calls == 0


# ----------------------------------------------------------------------
# make_discourse_client
# ----------------------------------------------------------------------

def test_make_discourse_client_returns_rate_limited_wrapper(bareapp):
    bareapp.config['DISCOURSE_API_URL_FSRC'] = 'https://community.example.com'
    bareapp.config['DISCOURSE_API_INVITE_USERNAME_FSRC'] = 'admin'
    bareapp.config['DISCOURSE_API_KEY_FSRC'] = 'key123'
    with bareapp.app_context():
        client = make_discourse_client('fsrc')
    assert isinstance(client, _RateLimitedDiscourse)


def test_make_discourse_client_missing_config_raises_value_error(bareapp):
    with bareapp.app_context():
        with pytest.raises(ValueError):
            make_discourse_client('fsrc')


# ----------------------------------------------------------------------
# run_query_paged
# ----------------------------------------------------------------------

def test_run_query_paged_single_short_page(bareapp):
    resp = {'columns': ['a'], 'rows': [[1], [2]], 'result_count': 2}
    discourse = FakeDiscourse({'admin.plugins.explorer.queries.9.run': resp})
    with bareapp.app_context():
        columns, rows = run_query_paged(discourse, 9, page_size=1000)
    assert columns == ['a']
    assert rows == [[1], [2]]


def test_run_query_paged_follows_multiple_full_pages(bareapp):
    def run(body):
        page_num = int(body['params']['page_num'])
        if page_num == 0:
            return {'columns': ['a'], 'rows': [[0], [1], [2]], 'result_count': 3}
        return {'columns': ['a'], 'rows': [[99]], 'result_count': 1}
    discourse = FakeDiscourse({'admin.plugins.explorer.queries.9.run': run})
    with bareapp.app_context():
        columns, rows = run_query_paged(discourse, 9, page_size=3)
    assert rows == [[0], [1], [2], [99]]


def test_run_query_paged_empty_first_page_returns_empty(bareapp):
    discourse = FakeDiscourse({'admin.plugins.explorer.queries.9.run':
                               {'columns': [], 'rows': [], 'result_count': 0}})
    with bareapp.app_context():
        columns, rows = run_query_paged(discourse, 9)
    assert rows == []


# ----------------------------------------------------------------------
# DbTagCommunitySyncManager / CommunitySyncManager, end to end via import_group()
# ----------------------------------------------------------------------

@pytest.fixture
def tagsyncsetup(bare_dbapp):
    '''DB fixture: an interest with a tag having two active members (alice, bob)'''
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()

    tag = Tag(tag='board', description='board members', interest=localinterest)
    alice = LocalUser(name='Alice', email='alice@example.com', active=True, interest=localinterest)
    bob = LocalUser(name='Bob', email='bob@example.com', active=True, interest=localinterest)
    tag.users.append(alice)
    tag.users.append(bob)
    db.session.add_all([tag, alice, bob])
    db.session.commit()
    return {'localinterest': localinterest, 'tag': tag, 'alice': alice, 'bob': bob}


@pytest.fixture
def discourse_config(bareapp):
    bareapp.config['DISCOURSE_API_INVITES_QUERY_FSRC'] = 10
    bareapp.config['DISCOURSE_API_INVITE_GROUPS_QUERY_FSRC'] = 11
    bareapp.config['DISCOURSE_API_USER_EMAIL_QUERY_FSRC'] = 12
    return bareapp


def test_communitysyncmanager_import_group_adds_and_removes_members(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''full import_group() run: bob (existing Discourse user, not yet in group) gets
    added, alice (no Discourse account) gets a new invite, carol (in the group but no
    longer in the DB tag) gets removed -- exercises SyncManager's add/update/remove
    algorithm through its real CommunitySyncManager/DbTagCommunitySyncManager subclass'''

    invite_posts = []

    def admin_users(params):
        if params['page'] == 1:
            return [{'id': 42, 'username': 'bob'}, {'id': 99, 'username': 'carol'}]
        return []

    def groups_list(params):
        return {'groups': [{'id': 7, 'name': 'my-group'}]}

    def group_members(params):
        return {'members': [{'id': 99}], 'meta': {'total': 1, 'limit': 50}}

    def invites_query(body):
        return {'columns': ['id', 'email', 'deleted_at', 'invalidated_at', 'redemption_count'],
                'rows': [], 'result_count': 0}

    def invite_groups_query(body):
        return {'columns': ['invite_id', 'group_id'], 'rows': [], 'result_count': 0}

    def user_email_query(body):
        return {'columns': ['email', 'user_id'], 'rows': [['bob@example.com', 42]], 'result_count': 1}

    def create_invite(body):
        invite_posts.append(body)
        return {}

    responses = {
        'admin.users.json': admin_users,
        'groups.json': groups_list,
        'groups.my-group.members.json': group_members,
        'admin.plugins.explorer.queries.10.run': invites_query,
        'admin.plugins.explorer.queries.11.run': invite_groups_query,
        'admin.plugins.explorer.queries.12.run': user_email_query,
        'invites.json': create_invite,
        ('groups.7.members.json', 'put'): lambda body: {'added': body},
        ('groups.7.members.json', 'delete'): lambda body: {'removed': body},
    }
    fake = FakeDiscourse(responses)
    monkeypatch.setattr(community, 'make_discourse_client', lambda interest: fake)
    monkeypatch.setattr(community, 'COMMUNITY_LOCKFILE', str(tmp_path / 'lock'))

    mgr = DbTagCommunitySyncManager('fsrc', 'board', 'my-group', skipemail=True)
    mgr.import_group()

    # bob (existing Discourse user id 42) was added to the group
    put_calls = [c for c in fake._calls if c[0] == 'groups.7.members.json' and c[1] == 'put']
    assert len(put_calls) == 1
    assert put_calls[0][2]['usernames'] == 'bob'

    # carol (group member no longer in the DB tag) was removed
    delete_calls = [c for c in fake._calls if c[0] == 'groups.7.members.json' and c[1] == 'delete']
    assert len(delete_calls) == 1
    assert delete_calls[0][2]['usernames'] == 'carol'

    # alice (no Discourse account, no prior invite) got a fresh invite
    assert len(invite_posts) == 1
    assert invite_posts[0]['email'] == 'alice@example.com'
    assert invite_posts[0]['group_ids'] == 7


def test_communitysyncmanager_start_import_filters_invites(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''start_import() should only keep invites that are active (not deleted/invalidated),
    unredeemed, and targeted to a specific email -- the filter documented in community.py'''
    rows = [
        ['1', 'keep@example.com', None, None, 0],
        ['2', 'deleted@example.com', '2026-01-01', None, 0],
        ['3', 'invalidated@example.com', None, '2026-01-01', 0],
        ['4', 'redeemed@example.com', None, None, 1],
        ['5', '', None, None, 0],
    ]

    def invites_query(body):
        return {'columns': ['id', 'email', 'deleted_at', 'invalidated_at', 'redemption_count'],
                'rows': rows, 'result_count': len(rows)}

    responses = {
        'admin.users.json': lambda params: [],
        'groups.json': lambda params: {'groups': [{'id': 7, 'name': 'my-group'}]},
        'admin.plugins.explorer.queries.10.run': invites_query,
        'admin.plugins.explorer.queries.11.run': lambda body: {'columns': ['invite_id', 'group_id'],
                                                                'rows': [], 'result_count': 0},
    }
    fake = FakeDiscourse(responses)
    monkeypatch.setattr(community, 'make_discourse_client', lambda interest: fake)
    monkeypatch.setattr(community, 'COMMUNITY_LOCKFILE', str(tmp_path / 'lock'))

    mgr = DbTagCommunitySyncManager('fsrc', 'board', 'my-group', skipemail=True)
    mgr.start_import()
    mgr.lock.release()

    assert set(mgr.invites.keys()) == {'keep@example.com'}
