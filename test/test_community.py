'''
test_community - test members.community
=========================================================
'''

# standard
import json
from datetime import date, datetime, timedelta, timezone

# pypi
import pytest
from flask import g

# homegrown
from members import community
from members.community import (
    _Discourse, _RateLimiter, _RateLimitedDiscourse, _ReadOnlyDiscourse, make_discourse_client, run_query_paged,
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
# _Discourse (429 handling)
# ----------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code, text='', headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self):
        return json.loads(self.text)


def _run_429(bareapp, monkeypatch, first_response):
    """issue one GET that gets first_response, then 200; return the seconds slept"""
    responses = [first_response, _FakeResponse(200, '{"ok": true}')]
    urls = []
    def fake_request(method, url, **kwargs):
        urls.append(url)
        return responses.pop(0)
    slept = []
    monkeypatch.setattr('fluent_discourse.discourse.requests.request', fake_request)
    monkeypatch.setattr(community.time, 'sleep', slept.append)
    client = _Discourse('https://community.example.com', 'admin', 'key', raise_for_rate_limit=False)
    with bareapp.app_context():
        result = client.categories.json.get({})
    assert result == {'ok': True}
    assert urls == ['https://community.example.com/categories.json'] * 2
    return slept


def test_discourse_429_json_body_uses_wait_seconds(bareapp, monkeypatch):
    body = json.dumps({'extras': {'wait_seconds': 5}})
    assert _run_429(bareapp, monkeypatch, _FakeResponse(429, body)) == [6]


def test_discourse_429_non_json_body_uses_retry_after(bareapp, monkeypatch):
    resp = _FakeResponse(429, 'Slow down, too many requests', {'Retry-After': '7'})
    assert _run_429(bareapp, monkeypatch, resp) == [8]


def test_discourse_429_empty_body_no_header_uses_default(bareapp, monkeypatch):
    assert _run_429(bareapp, monkeypatch, _FakeResponse(429, '')) == [community._DEFAULT_429_WAIT_SECS]


def test_discourse_chained_segments_keep_subclass():
    client = _Discourse('https://community.example.com', 'admin', 'key')
    assert type(client.groups._(5).members.json) is _Discourse


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
    # new invites get the same expiration rule as renewals
    _assert_expiration_in_window(invite_posts[0])


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


# ----------------------------------------------------------------------
# CommunitySyncManager invite renewal
# ----------------------------------------------------------------------

INVITE_COLUMNS = ['id', 'email', 'deleted_at', 'invalidated_at', 'redemption_count', 'expires_at']


def _discourse_time(days_from_now):
    '''Discourse-style UTC timestamp string, days_from_now relative to now'''
    dt = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')


def _run_invite_sync(monkeypatch, tmp_path, invite_rows, invitegroup_rows, dryrun=False):
    '''run import_group() for tag 'board' (alice, bob, neither with a Discourse account)
    into group 'my-group' (id 7, no user members), with the given invites

    :returns: list of (invite_id, body) for each invite PUT, and the FakeDiscourse
    '''
    invite_puts = []

    def invite_put(invite_id):
        def put(body):
            invite_puts.append((invite_id, body))
            return {}
        return put

    responses = {
        'admin.users.json': lambda params: [],
        'groups.json': lambda params: {'groups': [{'id': 7, 'name': 'my-group'}]},
        'groups.my-group.members.json': lambda params: {'members': [], 'meta': {'total': 0, 'limit': 50}},
        'admin.plugins.explorer.queries.10.run': lambda body: {'columns': INVITE_COLUMNS,
                                                                'rows': invite_rows, 'result_count': len(invite_rows)},
        'admin.plugins.explorer.queries.11.run': lambda body: {'columns': ['invite_id', 'group_id'],
                                                                'rows': invitegroup_rows,
                                                                'result_count': len(invitegroup_rows)},
        'admin.plugins.explorer.queries.12.run': lambda body: {'columns': ['email', 'user_id'],
                                                                'rows': [], 'result_count': 0},
        'invites.json': lambda body: {},
    }
    for row in invite_rows:
        responses[('invites.' + str(row[0]), 'put')] = invite_put(row[0])
    fake = FakeDiscourse(responses)
    monkeypatch.setattr(community, 'make_discourse_client', lambda interest: fake)
    monkeypatch.setattr(community, 'COMMUNITY_LOCKFILE', str(tmp_path / 'lock'))

    mgr = DbTagCommunitySyncManager('fsrc', 'board', 'my-group', skipemail=True, dryrun=dryrun)
    mgr.import_group()
    return invite_puts, fake


def _assert_expiration_in_window(body):
    '''new or renewed expiration falls in INVITE_EXPIRY_DAYS plus 0 to INVITE_EXPIRY_SPREAD_DAYS from now'''
    expires_at = datetime.fromisoformat(body['expires_at'])
    now = datetime.now(timezone.utc)
    earliest = now + timedelta(days=community.INVITE_EXPIRY_DAYS) - timedelta(minutes=5)
    latest = now + timedelta(days=community.INVITE_EXPIRY_DAYS + community.INVITE_EXPIRY_SPREAD_DAYS) + timedelta(minutes=5)
    assert earliest <= expires_at <= latest


def test_invite_sync_renews_expired_invite_already_in_group(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''an expired invite already targeting the group is renewed (keeping its groups),
    and an invite with plenty of time left is left alone'''
    invite_rows = [
        [1, 'alice@example.com', None, None, 0, _discourse_time(-10)],
        [2, 'bob@example.com', None, None, 0, _discourse_time(60)],
    ]
    invitegroup_rows = [[1, 7], [1, 8], [2, 7]]

    invite_puts, fake = _run_invite_sync(monkeypatch, tmp_path, invite_rows, invitegroup_rows)

    assert [p[0] for p in invite_puts] == [1]
    body = invite_puts[0][1]
    assert body['email'] == 'alice@example.com'
    assert body['group_ids'] == '7,8'
    assert body['skip_email'] is True
    _assert_expiration_in_window(body)
    # no new invites created
    assert not [c for c in fake._calls if c[0] == 'invites.json']


def test_invite_sync_renews_invite_within_renewal_window(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''an invite that will expire within INVITE_RENEW_WITHIN_DAYS is renewed before it lapses'''
    invite_rows = [
        [1, 'alice@example.com', None, None, 0, _discourse_time(community.INVITE_RENEW_WITHIN_DAYS - 1)],
        [2, 'bob@example.com', None, None, 0, _discourse_time(community.INVITE_RENEW_WITHIN_DAYS + 1)],
    ]
    invitegroup_rows = [[1, 7], [2, 7]]

    invite_puts, fake = _run_invite_sync(monkeypatch, tmp_path, invite_rows, invitegroup_rows)

    assert [p[0] for p in invite_puts] == [1]
    _assert_expiration_in_window(invite_puts[0][1])


def test_invite_sync_adds_group_and_renews_in_one_call(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''an expired invite for other groups gets this group added and is renewed in a
    single PUT; a valid invite for other groups gets only the group added'''
    invite_rows = [
        [1, 'alice@example.com', None, None, 0, _discourse_time(-10)],
        [2, 'bob@example.com', None, None, 0, _discourse_time(60)],
    ]
    invitegroup_rows = [[1, 8], [2, 8]]

    invite_puts, fake = _run_invite_sync(monkeypatch, tmp_path, invite_rows, invitegroup_rows)

    puts = dict(invite_puts)
    assert len(invite_puts) == 2
    assert puts[1]['group_ids'] == '8,7'
    _assert_expiration_in_window(puts[1])
    assert puts[2]['group_ids'] == '8,7'
    assert 'expires_at' not in puts[2]


def test_invite_sync_removal_keeps_expired_invite_with_other_groups(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''removing the group from an expired invite that still has other groups updates it
    rather than deleting it, so the other groups' syncs can renew it'''
    invite_rows = [
        [1, 'alice@example.com', None, None, 0, _discourse_time(60)],
        [2, 'bob@example.com', None, None, 0, _discourse_time(60)],
        [3, 'carol@example.com', None, None, 0, _discourse_time(-10)],
    ]
    invitegroup_rows = [[1, 7], [2, 7], [3, 7], [3, 8]]

    invite_puts, fake = _run_invite_sync(monkeypatch, tmp_path, invite_rows, invitegroup_rows)

    assert [p[0] for p in invite_puts] == [3]
    assert invite_puts[0][1]['group_ids'] == '8'
    assert 'expires_at' not in invite_puts[0][1]
    assert not [c for c in fake._calls if c[0] == 'invites.json' and c[1] == 'delete']


def test_parse_discourse_time():
    assert community._parse_discourse_time(None) is None
    assert community._parse_discourse_time('2026-07-19T16:31:39.483Z') == \
        datetime(2026, 7, 19, 16, 31, 39, 483000, tzinfo=timezone.utc)


def test_invite_sync_dryrun_makes_no_writes(tagsyncsetup, discourse_config, monkeypatch, tmp_path, capsys):
    '''with dryrun, every write (invite renew, invite create, invite delete) is printed
    instead of sent; only reads and Data Explorer query runs reach Discourse'''
    invite_rows = [
        [1, 'alice@example.com', None, None, 0, _discourse_time(-10)],
        [3, 'carol@example.com', None, None, 0, _discourse_time(60)],
    ]
    invitegroup_rows = [[1, 7], [3, 7]]

    invite_puts, fake = _run_invite_sync(monkeypatch, tmp_path, invite_rows, invitegroup_rows, dryrun=True)

    writes = [c for c in fake._calls
              if c[1] in ('put', 'delete') or (c[1] == 'post' and 'explorer' not in c[0])]
    assert writes == []
    out = capsys.readouterr().out
    assert '[DRY RUN] my-group: update invite 1 for alice@example.com: group_ids 7, expires_at ' in out
    assert '[DRY RUN] my-group: create invite for bob@example.com, no email' in out
    assert '[DRY RUN] my-group: delete invite 3 for carol@example.com' in out


# ----------------------------------------------------------------------
# _ReadOnlyDiscourse
# ----------------------------------------------------------------------

def test_readonlydiscourse_allows_reads_and_query_runs():
    fake = FakeDiscourse({
        'groups.json': {'groups': []},
        'admin.plugins.explorer.queries.10.run': {'rows': []},
    })
    ro = _ReadOnlyDiscourse(fake)

    assert ro.groups.json.get({'page': 0}) == {'groups': []}
    assert ro.admin.plugins.explorer.queries._(10).run.post({'params': {}}) == {'rows': []}
    assert [c[:2] for c in fake._calls] == [('groups.json', 'get'),
                                            ('admin.plugins.explorer.queries.10.run', 'post')]


@pytest.mark.parametrize('chain, method', [
    (lambda ro: ro.invites._(1), 'put'),
    (lambda ro: ro.invites.json, 'post'),
    (lambda ro: ro.invites.json, 'delete'),
    (lambda ro: ro.groups._(7).members.json, 'put'),
    (lambda ro: ro.groups._(7).members.json, 'delete'),
    # a post under the explorer path that isn't a query run is still refused
    (lambda ro: ro.admin.plugins.explorer.queries, 'post'),
])
def test_readonlydiscourse_refuses_writes(chain, method):
    fake = FakeDiscourse({})
    ro = _ReadOnlyDiscourse(fake)

    with pytest.raises(RuntimeError, match='dry run: refused Discourse'):
        getattr(chain(ro), method)({})
    assert fake._calls == []


def test_communitysyncmanager_dryrun_client_refuses_unchecked_writes(tagsyncsetup, discourse_config, monkeypatch):
    '''a dry-run sync manager's client refuses a write even if the write site has no
    _skip_for_dryrun() check of its own'''
    fake = FakeDiscourse({})
    monkeypatch.setattr(community, 'make_discourse_client', lambda interest: fake)

    mgr = DbTagCommunitySyncManager('fsrc', 'board', 'my-group', skipemail=True, dryrun=True)
    with pytest.raises(RuntimeError):
        mgr.discourse.invites._(1).put({'expires_at': 'x'})
    assert fake._calls == []

    mgr = DbTagCommunitySyncManager('fsrc', 'board', 'my-group', skipemail=True)
    assert mgr.discourse is fake


def test_invite_sync_spreads_renewed_expirations(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''invites renewed in the same run get different expirations across the spread window,
    so they don't all come due for renewal again in the same run'''
    spreads = iter([0.0, community.INVITE_EXPIRY_SPREAD_DAYS])
    monkeypatch.setattr(community.random, 'uniform', lambda a, b: next(spreads))
    invite_rows = [
        [1, 'alice@example.com', None, None, 0, _discourse_time(-10)],
        [2, 'bob@example.com', None, None, 0, _discourse_time(-10)],
    ]
    invitegroup_rows = [[1, 7], [2, 7]]

    invite_puts, fake = _run_invite_sync(monkeypatch, tmp_path, invite_rows, invitegroup_rows)

    expirations = sorted(datetime.fromisoformat(body['expires_at']) for _, body in invite_puts)
    assert expirations[1] - expirations[0] == timedelta(days=community.INVITE_EXPIRY_SPREAD_DAYS)


def test_communitysyncmanager_adds_user_created_after_user_list_fetch(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''an account created after start_import() fetched the user list shows up in the
    email lookup but not in id2users; add_user_to_group() looks it up by id instead of
    finish_import() raising KeyError'''
    responses = {
        'admin.users.json': lambda params: [],
        'groups.json': lambda params: {'groups': [{'id': 7, 'name': 'my-group'}]},
        'groups.my-group.members.json': lambda params: {'members': [], 'meta': {'total': 0, 'limit': 50}},
        'admin.plugins.explorer.queries.10.run': lambda body: {'columns': INVITE_COLUMNS, 'rows': [], 'result_count': 0},
        'admin.plugins.explorer.queries.11.run': lambda body: {'columns': ['invite_id', 'group_id'], 'rows': [], 'result_count': 0},
        # bob signed up after the user list was fetched
        'admin.plugins.explorer.queries.12.run': lambda body: {'columns': ['email', 'user_id'],
                                                                'rows': [['bob@example.com', 42]], 'result_count': 1},
        'admin.users.42.json': {'id': 42, 'username': 'bob'},
        'invites.json': lambda body: {},
        ('groups.7.members.json', 'put'): lambda body: {},
    }
    fake = FakeDiscourse(responses)
    monkeypatch.setattr(community, 'make_discourse_client', lambda interest: fake)
    monkeypatch.setattr(community, 'COMMUNITY_LOCKFILE', str(tmp_path / 'lock'))

    mgr = DbTagCommunitySyncManager('fsrc', 'board', 'my-group', skipemail=True)
    mgr.import_group()

    put_calls = [c for c in fake._calls if c[0] == 'groups.7.members.json' and c[1] == 'put']
    assert len(put_calls) == 1
    assert put_calls[0][2]['usernames'] == 'bob'


def test_communitysyncmanager_skips_user_whose_lookup_fails(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''if looking up an account missing from the user list fails, that one account is
    skipped (picked up on the next run) and the rest of the run still completes'''
    from fluent_discourse import DiscourseError

    def lookup_fails(params):
        raise DiscourseError('boom')

    responses = {
        'admin.users.json': lambda params: [{'id': 99, 'username': 'carol'}] if params['page'] == 1 else [],
        'groups.json': lambda params: {'groups': [{'id': 7, 'name': 'my-group'}]},
        'groups.my-group.members.json': lambda params: {'members': [{'id': 99}], 'meta': {'total': 1, 'limit': 50}},
        'admin.plugins.explorer.queries.10.run': lambda body: {'columns': INVITE_COLUMNS, 'rows': [], 'result_count': 0},
        'admin.plugins.explorer.queries.11.run': lambda body: {'columns': ['invite_id', 'group_id'], 'rows': [], 'result_count': 0},
        'admin.plugins.explorer.queries.12.run': lambda body: {'columns': ['email', 'user_id'],
                                                                'rows': [['bob@example.com', 42]], 'result_count': 1},
        'admin.users.42.json': lookup_fails,
        'invites.json': lambda body: {},
        ('groups.7.members.json', 'delete'): lambda body: {},
    }
    fake = FakeDiscourse(responses)
    monkeypatch.setattr(community, 'make_discourse_client', lambda interest: fake)
    monkeypatch.setattr(community, 'COMMUNITY_LOCKFILE', str(tmp_path / 'lock'))

    mgr = DbTagCommunitySyncManager('fsrc', 'board', 'my-group', skipemail=True)
    mgr.import_group()

    assert not [c for c in fake._calls if c[0] == 'groups.7.members.json' and c[1] == 'put']
    # carol, no longer in the tag, is still removed
    delete_calls = [c for c in fake._calls if c[0] == 'groups.7.members.json' and c[1] == 'delete']
    assert len(delete_calls) == 1 and delete_calls[0][2]['usernames'] == 'carol'


def test_communitysyncmanager_two_records_one_account_already_in_group(tagsyncsetup, discourse_config, monkeypatch, tmp_path):
    '''two service records whose emails are both on one Discourse account that's already
    in the group (e.g. a parent's and a junior's memberships) don't make the sync try to
    add the account again, which Discourse rejects with a 422'''
    responses = {
        'admin.users.json': lambda params: [{'id': 42, 'username': 'alice'}] if params['page'] == 1 else [],
        'groups.json': lambda params: {'groups': [{'id': 7, 'name': 'my-group'}]},
        'groups.my-group.members.json': lambda params: {'members': [{'id': 42}], 'meta': {'total': 1, 'limit': 50}},
        'admin.plugins.explorer.queries.10.run': lambda body: {'columns': INVITE_COLUMNS, 'rows': [], 'result_count': 0},
        'admin.plugins.explorer.queries.11.run': lambda body: {'columns': ['invite_id', 'group_id'], 'rows': [], 'result_count': 0},
        # alice's and bob's emails are both on account 42
        'admin.plugins.explorer.queries.12.run': lambda body: {'columns': ['email', 'user_id'],
                                                                'rows': [['alice@example.com', 42], ['bob@example.com', 42]],
                                                                'result_count': 2},
    }
    fake = FakeDiscourse(responses)
    monkeypatch.setattr(community, 'make_discourse_client', lambda interest: fake)
    monkeypatch.setattr(community, 'COMMUNITY_LOCKFILE', str(tmp_path / 'lock'))

    mgr = DbTagCommunitySyncManager('fsrc', 'board', 'my-group', skipemail=True)
    mgr.import_group()

    # no group add or remove, and no invite created
    assert not [c for c in fake._calls if c[0] == 'groups.7.members.json']
    assert not [c for c in fake._calls if c[0] == 'invites.json']
