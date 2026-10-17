"""community helpers
"""

# stdlib
import json
import random
import time
from pathlib import Path

# pypi
from flask import current_app, g
from fluent_discourse import Discourse, DiscourseError
from fasteners import InterProcessLock
from datetime import date, datetime, timedelta, timezone

# Lock/state files below live on the 'community-locks' Docker volume
# (docker-compose.yml), NOT /tmp -- 'app' (web requests, e.g. calendar_feed())
# and 'crond' (cron-fired CLI commands) are separate containers with separate
# filesystems. An earlier version of these paths under /tmp worked for
# coordinating multiple CLI invocations within the crond container (or multiple
# web requests within the app container), but /tmp is never actually shared
# between the two containers -- confirmed as the root cause of a real 429 that
# occurred despite that "working" cross-process fix: a calendar_feed() request
# in 'app' and two cron-fired notify-pending-reviews runs in 'crond' were each
# reading/writing their own container-local /tmp, invisible to each other.
_LOCKS_DIR = Path('/locks')

# shared across all community commands that hit the Discourse API, so concurrent
# commands (not just concurrent runs of the *same* command) can't together exceed
# Discourse's real server-side rate limit, which each process's own in-memory
# _RateLimiter has no way to coordinate against
COMMUNITY_LOCKFILE = str(_LOCKS_DIR / 'communitygroupmanager.lock')

# _RateLimiter's shared state: a JSON list of recent call timestamps, plus its
# own dedicated lock (a short per-call critical section, unlike COMMUNITY_LOCKFILE
# which some but not all community commands hold for their whole duration)
_RATE_LIMIT_STATE_FILE = _LOCKS_DIR / 'discourse_ratelimit_state.json'
_RATE_LIMIT_STATE_LOCKFILE = str(_LOCKS_DIR / 'discourse_ratelimit_state.lock')

# Discourse's confirmed default (config/discourse_defaults.conf,
# max_admin_api_reqs_per_minute = 60) is 60 calls/minute for the admin API key;
# 55 is a 5-call margin below that for a single well-behaved caller, and works
# fine for steady single-threaded use. A real 429 was still observed live under
# a 3-way burst (a calendar_feed() web request overlapping two cron-fired
# notify-pending-reviews runs for different categories, both firing from
# separate cron lines at the same minute) -- traced to the /tmp-not-actually-shared
# issue above, not a flaw in the pacing logic itself or evidence that 55 is too
# close to the real 60/minute limit. Fix the burst at the source (e.g.
# consolidate same-minute cron lines into one multi-category invocation) rather
# than permanently taxing every normal run's throughput by lowering this further.
DISCOURSE_RATE_LIMIT_MAX_CALLS = 55
DISCOURSE_RATE_LIMIT_WINDOW_SECS = 60

# pending invites are renewed by the community sync while the person is still on
# the source list, so the invite is still redeemable when they sign up. Discourse
# only redeems an unexpired invite for the new user's email when the signup email
# is confirmed (EmailToken.confirm -> Invite.redeem_for_existing_user), so an
# expired invite means no group membership until the next sync run.
# Each renewal adds a random 0 to INVITE_EXPIRY_SPREAD_DAYS on top of
# INVITE_EXPIRY_DAYS, so invites renewed in the same run don't all come due
# again together, which would make one sync run do hundreds of renewals.
# Discourse puts no cap on an explicit expires_at; its invite_expiry_days site
# setting only supplies the default when none is given.
INVITE_RENEW_WITHIN_DAYS = 14
INVITE_EXPIRY_DAYS = 182
INVITE_EXPIRY_SPREAD_DAYS = 30


class _RateLimiter:
    """Sliding-window rate limiter shared across processes via a small state file.

    A purely in-memory, per-process limiter (the original implementation) only
    protects a single process from exceeding the budget within its own lifetime.
    It can't stop two sequential-but-close processes from together exceeding
    Discourse's real server-side limit -- e.g. command B starting right after
    command A releases COMMUNITY_LOCKFILE gets a fresh, empty in-memory limiter
    with no memory of A's calls from moments earlier, bursts ahead assuming a
    full budget, and hits Discourse's real 429 (observed live: fluent_discourse's
    own "Discourse rate limit hit, trying again in N seconds" retry, which is
    the real server-side limit being hit, not this class). Uses time.time()
    (wall clock), not time.monotonic(), since timestamps must be comparable
    across separate process invocations.
    """
    def __init__(self, max_calls, window_secs):
        self.max_calls = max_calls
        self.window_secs = window_secs

    def _read_calls(self) -> list[float]:
        try:
            return json.loads(_RATE_LIMIT_STATE_FILE.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def acquire(self):
        with InterProcessLock(_RATE_LIMIT_STATE_LOCKFILE):
            now = time.time()
            calls = [t for t in self._read_calls() if now - t < self.window_secs]
            if len(calls) >= self.max_calls:
                wait = self.window_secs - (now - calls[0])
                if wait > 0:
                    current_app.logger.debug(
                        f'_RateLimiter.acquire(): throttling {wait:.1f}s '
                        f'({len(calls)}/{self.max_calls} calls in window, shared across processes)'
                    )
                    time.sleep(wait)
                    now = time.time()
                    calls = [t for t in calls if now - t < self.window_secs]
            calls.append(now)
            _RATE_LIMIT_STATE_FILE.write_text(json.dumps(calls))


def make_discourse_client(interest: str, username: str | None = None) -> '_RateLimitedDiscourse':
    """Create a rate-limited fluent_discourse client for the given interest.

    username overrides DISCOURSE_API_INVITE_USERNAME_{INTEREST} when provided,
    e.g. to post as a dedicated bot account rather than the default admin user.
    """
    uinterest = interest.upper()
    try:
        return _RateLimitedDiscourse(
            _Discourse(
                base_url=current_app.config[f'DISCOURSE_API_URL_{uinterest}'],
                username=username or current_app.config[f'DISCOURSE_API_INVITE_USERNAME_{uinterest}'],
                api_key=current_app.config[f'DISCOURSE_API_KEY_{uinterest}'],
                raise_for_rate_limit=False,
            ),
            _RateLimiter(max_calls=DISCOURSE_RATE_LIMIT_MAX_CALLS, window_secs=DISCOURSE_RATE_LIMIT_WINDOW_SECS),
        )
    except KeyError as e:
        raise ValueError(f'Missing Discourse configuration for interest {interest}: {e}')


# wait used when a 429 response gives no usable wait time at all
_DEFAULT_429_WAIT_SECS = 10


class _Discourse(Discourse):
    """fluent_discourse client that tolerates a 429 response without a JSON body.

    fluent_discourse's _wait_for_rate_limit() reads response.json()['extras']['wait_seconds'],
    which is only present on Discourse's own application-level rate limit response. A 429
    with a plain-text or empty body (e.g., a per-IP limit enforced before the request
    reaches the API layer) made it raise JSONDecodeError, crashing the command instead of
    waiting and retrying. This falls back to the Retry-After header, then to a fixed wait.
    """

    def _(self, name):
        # the base class hardcodes Discourse(...) here, which would drop this subclass
        # from every chained segment
        return _Discourse(
            self._base_url,
            self._username,
            self._api_key,
            self._cache + [str(name)],
            self._raise_for_rate_limit,
        )

    def _wait_for_rate_limit(self, response, method, url, data, params):
        wait_seconds = None
        try:
            wait_seconds = int(response.json()['extras']['wait_seconds']) + 1
        except (ValueError, KeyError, TypeError):
            try:
                wait_seconds = int(response.headers.get('Retry-After', '')) + 1
            except ValueError:
                pass
            # log what came back, to identify which layer is returning these
            current_app.logger.warning(
                f'Discourse 429 without JSON wait_seconds: {method} {url}, '
                f'Retry-After={response.headers.get("Retry-After")!r}, '
                f'body={response.text[:200]!r}'
            )
        if wait_seconds is None:
            wait_seconds = _DEFAULT_429_WAIT_SECS
        current_app.logger.warning(f'Discourse rate limit hit, trying again in {wait_seconds} seconds')
        time.sleep(wait_seconds)


class _RateLimitedDiscourse:
    """Transparent proxy around a fluent_discourse client that rate-limits all HTTP calls.

    Intercepts .get()/.post()/.put()/.delete() to acquire a rate-limit token first.
    All other attribute accesses (fluent chain segments) are re-wrapped so the proxy
    follows the entire chain automatically.
    """
    _HTTP_METHODS = frozenset({'get', 'post', 'put', 'delete'})

    def __init__(self, target, rate_limiter):
        object.__setattr__(self, '_target', target)
        object.__setattr__(self, '_rl', rate_limiter)

    def __getattr__(self, name):
        target = object.__getattribute__(self, '_target')
        rl = object.__getattribute__(self, '_rl')
        attr = getattr(target, name)
        if name in self._HTTP_METHODS and callable(attr):
            def _throttled(*args, **kwargs):
                rl.acquire()
                return attr(*args, **kwargs)
            return _throttled
        if callable(attr):
            def _chained(*args, **kwargs):
                result = attr(*args, **kwargs)
                if isinstance(result, (str, int, float, bool, type(None))):
                    return result
                return _RateLimitedDiscourse(result, rl)
            return _chained
        # Non-callable: pass primitives through; wrap everything else (fluent chain objects)
        if isinstance(attr, (str, int, float, bool, type(None))):
            return attr
        return _RateLimitedDiscourse(attr, rl)


class _ReadOnlyDiscourse:
    """Proxy around a fluent_discourse client that refuses every write, for dry runs.

    Allows .get(), and .post() only for Data Explorer query runs
    (admin/plugins/explorer/queries/<id>/run), which are reads despite the verb.
    Any other .post(), and every .put() or .delete(), raises RuntimeError without
    reaching Discourse. This backs up the dry-run checks at each write site, so a
    write added later without its own check still can't go through.
    """

    def __init__(self, target, path=()):
        object.__setattr__(self, '_target', target)
        object.__setattr__(self, '_path', path)

    def _is_query_run(self):
        path = object.__getattribute__(self, '_path')
        return len(path) == 6 and path[:4] == ('admin', 'plugins', 'explorer', 'queries') and path[5] == 'run'

    def __getattr__(self, name):
        target = object.__getattribute__(self, '_target')
        path = object.__getattribute__(self, '_path')
        if name == '_':
            return lambda arg: _ReadOnlyDiscourse(target._(arg), path + (str(arg),))
        if name.startswith('_'):
            raise AttributeError(name)
        if name == 'get' or (name == 'post' and self._is_query_run()):
            return getattr(target, name)
        if name in ('post', 'put', 'delete'):
            def _refuse(*args, **kwargs):
                raise RuntimeError(f'dry run: refused Discourse {name.upper()} {"/".join(path)}')
            return _refuse
        return _ReadOnlyDiscourse(getattr(target, name), path + (name,))

# homegrown
from .sync import SyncManager
from .helpers import get_tags_users, make_runsignup_fluent_client
from .model import Tag, localinterest_query_params


def run_query_paged(discourse, query_id, params=None, page_size=1000):
    """Run a Data Explorer query collecting all pages of results.

    :param discourse: rate-limited fluent_discourse client
    :param query_id: Discourse Data Explorer query id
    :param params: extra query params (e.g. an int_list filter) merged into every
                    page's request alongside page_num/page_size
    :param page_size: rows per page; must match the :page_size SQL parameter default
    :returns: (columns, rows) where rows is the combined list across all pages
    """
    # https://meta.discourse.org/t/run-data-explorer-queries-with-the-discourse-api/120063
    columns = []
    rows = []
    page = 0
    base_params = dict(params or {})
    while True:
        query_params = {**base_params, 'page_num': str(page), 'page_size': str(page_size)}
        resp = discourse.admin.plugins.explorer.queries._(query_id).run.post({'params': query_params})
        result_count = resp.get('result_count', 0)
        page_rows = resp.get('rows', [])
        current_app.logger.debug(
            f'run_query_paged(): query {query_id} page {page} '
            f'result_count={result_count} rows={len(page_rows)}'
        )
        if result_count == 0 or not page_rows:
            columns = resp.get('columns', columns)
            break
        columns = resp['columns']
        rows.extend(page_rows)
        if result_count < page_size:
            break
        page += 1
    return columns, rows


def _parse_discourse_time(value):
    """parse a Discourse timestamp (e.g. '2026-07-19T16:31:39.483Z') to an aware datetime

    :param value: timestamp string, or None
    :returns: aware datetime in UTC, or None if value is empty
    """
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

class RsuRaceSyncManager(SyncManager):
    """put participants into internal group from RunSignup
    
    expects the following to be set in config:
        RSU_KEY
        RSU_SECRET
        RSU_API_REG_TOKEN
        RSU_API_REG_SECRET

    Args:
        raceid (int): RunSignup race id
    """
    
    def __init__(self, raceid):
        """_summary_"""
        self.raceid = raceid

        self.rsu = make_runsignup_fluent_client()
        
    def get_users_from_service(self):
        """get participants from RunSignup race, latest event
        
        :rtype: dict of service user records, indexed by email"""
        # https://runsignup.com/API/race/:race_id/GET
        events = self.rsu.race._(self.raceid).params({'most_recent_events_only': 'T'}).get().json()['race']['events']
        if not events:
            return {}
        
        if len(events) > 1:
            current_app.logger.warning(f'{self.get_users_from_service.__qualname__}(): multiple events found for race {self.raceid}, using first one')
            
        event_id = events[0]['event_id']
        page = 1
        
        participants = {}
        while True:
            # https://runsignup.com/API/race/:race_id/participants/GET
            current_app.logger.debug(f'{self.get_users_from_service.__qualname__}(): retrieving event {event_id} participants page {page}')
            resp = self.rsu.race._(self.raceid).participants.params({'event_id': event_id, 'page':page}).get()
            pageparticipants = resp.json()[0].pop('participants', [])
            
            # jump out of loop if we're done
            if not pageparticipants:
                break
            
            # collect all the participants on this page
            for p in pageparticipants:
                participants[p['user']['email'].lower()] = p
            
            # next page
            page += 1
            
        return participants
    
class RsuClubSyncManager(SyncManager):
    """put members into internal group from RunSignup
    
    expects the following to be set in config:
        RSU_KEY
        RSU_SECRET
        RSU_API_REG_TOKEN
        RSU_API_REG_SECRET

    Args:
        clubid (int): RunSignup club id
    """
    
    def __init__(self, clubid):
        """_summary_"""
        self.clubid = clubid

        self.rsu = make_runsignup_fluent_client()
        
    def get_users_from_service(self):
        """get members from RunSignup club, latest event
        
        :rtype: dict of service user records, indexed by email"""
        page = 1
        members = {}
        while True:
            # https://runsignup.com/API/club/:club_id/members/GET
            current_app.logger.debug(f'{self.get_users_from_service.__qualname__}(): retrieving club {self.clubid} members page {page}')
            resp = self.rsu.club._(self.clubid).members.params({'current_members_only': 'T', 'page':page}).get()
            pagemembers = resp.json().pop('club_members', [])
            
            # jump out of loop if we're done
            if not pagemembers:
                break
            
            # collect all the members on this page
            for m in pagemembers:
                members[m['user']['email'].lower()] = m
            
            # next page
            page += 1
            
        return members
    

class CommunitySyncManager(SyncManager):
    """put participants into discourse community group
    
    expects the following to be set in config:
        DISCOURSE_API_URL_<INTEREST>
        DISCOURSE_API_INVITE_USERNAME_<INTEREST>
        DISCOURSE_API_KEY_<INTEREST>
        
    Args:
        interest (str): interest short name
        communitygroupname (str): Discourse community group name
        skipemail (bool): if True, don't send email for new invites
        dryrun (bool): if True, print each Discourse write instead of making it
    """

    def __init__(self, interest, communitygroupname, skipemail, dryrun=False):
        """_summary_

        """
        self.communitygroupname = communitygroupname
        self.skipemail = skipemail
        self.dryrun = dryrun

        self.discourse = make_discourse_client(interest)
        if dryrun:
            self.discourse = _ReadOnlyDiscourse(self.discourse)
    
    def get_group_key_from_service_user(self, svcuser):
        """get unique key for service user used by internal group
        
        :param svcuser: record from service which contains email
        :rtype: email address
        """
        
        # find email in race participant record and use that as the key
        # if not a current user, return email because there may be a pending invite
        email = self.get_email(svcuser)
        return self.email2user[email]['user_id'] if email in self.email2user else email
    
    def _run_query_paged(self, query_id, page_size=1000):
        """Run a Data Explorer query collecting all pages of results.

        :param query_id: Discourse Data Explorer query id
        :param page_size: rows per page; must match the :page_size SQL parameter default
        :returns: (columns, rows) where rows is the combined list across all pages
        """
        return run_query_paged(self.discourse, query_id, page_size=page_size)

    def _skip_for_dryrun(self, description):
        """in dry-run mode, print the Discourse write that would be made

        :param description: what the write would do
        :rtype: bool, True if the write should be skipped
        """
        if self.dryrun:
            print(f'  [DRY RUN] {self.communitygroupname}: {description}')
        return self.dryrun

    def _invite_needs_renewal(self, invite):
        """check whether an invite has expired or will expire soon

        :param invite: invite record from self.invites
        :rtype: bool
        """
        expires_at = invite.get('expires_at')
        if not expires_at:
            return False
        return expires_at < self.now + timedelta(days=INVITE_RENEW_WITHIN_DAYS)

    def _new_expires_at(self):
        """expiration for a new or renewed invite

        :rtype: aware datetime, INVITE_EXPIRY_DAYS plus a random 0 to
            INVITE_EXPIRY_SPREAD_DAYS from now
        """
        return self.now + timedelta(days=INVITE_EXPIRY_DAYS + random.uniform(0, INVITE_EXPIRY_SPREAD_DAYS))

    def _update_invite(self, invite, group_ids, renew, caller):
        """update an existing invite's groups, and optionally renew its expiration

        :param invite: invite record from self.invites
        :param group_ids: complete list of group ids the invite should target
        :param renew: True to push the expiration out, see _new_expires_at()
        :param caller: qualname of calling method, for logging
        """
        email = invite['email']
        body = {
            'email': email,
            'group_ids': ','.join([str(g) for g in group_ids]),
            'skip_email': True,
        }
        if renew:
            expires_at = self._new_expires_at()
            body['expires_at'] = expires_at.isoformat()
        current_app.logger.debug(f'{caller}(): updating Discourse invite for email {email} '
                                 f'group_ids {body["group_ids"]}'
                                 + (f' expires_at {body["expires_at"]}' if renew else ''))
        if self._skip_for_dryrun(f'update invite {invite["id"]} for {email}: group_ids {body["group_ids"]}'
                                 + (f', expires_at {invite["expires_at"].isoformat()} -> {body["expires_at"]}'
                                    if renew else '')):
            return
        # interface reverse engineered from Discourse web app
        try:
            self.discourse.invites._(invite['id']).put(body)
        except DiscourseError as e:
            current_app.logger.error(f'{caller}(): error updating Discourse invite for email {email}: {e}')
            return
        if renew:
            invite['expires_at'] = expires_at

    def start_import(self):
        """runtime start for import from Community perspective

        """
        # interprocess lock to prevent multiple imports at once
        self.lock = InterProcessLock(COMMUNITY_LOCKFILE)
        self.lock.acquire()
        
        # sets to track users to add/remove
        self.add_userids = set()
        self.remove_userids = set()
        self.remove_group_invites = set()

        # https://docs.discourse.org/#tag/Admin/operation/adminListUsers
        
        page = 1
        userrows = []
        while True:
            resp = self.discourse.admin.users.json.get({'page': page})
            if not resp:
                break
            userrows.extend(resp)
            page += 1
        self.id2users = {row['id']: row for row in userrows}

        # save group id for current group
        # https://docs.discourse.org/#tag/Groups/operation/listGroups
        self.communitygroupid = None
        page = 0
        while not self.communitygroupid:
            resp = self.discourse.groups.json.get({'page': page})
            page_groups = resp.get('groups', [])
            if not page_groups:
                break
            for group in page_groups:
                if group['name'] == self.communitygroupname:
                    self.communitygroupid = group['id']
                    break
            page += 1
        if not self.communitygroupid:
            raise ValueError(f'{self.start_import.__qualname__}(): community group {self.communitygroupname} not found in Discourse')
        current_app.logger.debug(f'{self.start_import.__qualname__}(): community group {self.communitygroupname} has id {self.communitygroupid}')

        # https://meta.discourse.org/t/run-data-explorer-queries-with-the-discourse-api/120063
        columns, rows = self._run_query_paged(current_app.config['DISCOURSE_API_INVITES_QUERY_FSRC'])
        inviterows = [dict(zip(columns, row)) for row in rows]
        # only save active invites targeted to specific email addresses which have not been redeemed
        self.invites = {row['email']: row for row in inviterows if not row['deleted_at'] and not row['invalidated_at']
                        and row['email']
                        and row['redemption_count']==0}
        # expired invites are kept too, so they can be renewed rather than duplicated
        for invite in self.invites.values():
            invite['expires_at'] = _parse_discourse_time(invite.get('expires_at'))
        self.now = datetime.now(timezone.utc)

        columns, rows = self._run_query_paged(current_app.config['DISCOURSE_API_INVITE_GROUPS_QUERY_FSRC'])
        invitegrouprows = [dict(zip(columns, row)) for row in rows]
        # create list of group ids by invite id
        self.invitegroups = {}
        for row in invitegrouprows:
            self.invitegroups.setdefault(row['invite_id'], [])
            self.invitegroups[row['invite_id']].append(row['group_id'])

        super().start_import()
    
    def get_users_from_group(self):
        """get users from discourse community group
        
        :rtype: dict of group user records indexed by user_id / invite records indexed by email
        """
        # https://meta.discourse.org/t/run-data-explorer-queries-with-the-discourse-api/120063
        columns, rows = self._run_query_paged(current_app.config['DISCOURSE_API_USER_EMAIL_QUERY_FSRC'])
        emailrows = [dict(zip(columns, row)) for row in rows]
        self.email2user = {row['email']: row for row in emailrows}
        id2emails = {}
        for row in emailrows:
            id2emails.setdefault(row['user_id'], [])
            id2emails[row['user_id']].append(row['email'])

        # https://docs.discourse.org/#tag/Groups/operation/listGroupMembers
        all_members = []
        offset = 0
        while True:
            groupmembers = self.discourse.groups._(self.communitygroupname).members.json.get(
                {'offset': offset, 'order': '', 'asc': 'true', 'filter': ''}
            )
            page = groupmembers.get('members', [])
            all_members.extend(page)
            meta = groupmembers.get('meta', {})
            current_app.logger.debug(
                f'{self.get_users_from_group.__qualname__}(): group {self.communitygroupname} '
                f'offset={offset} fetched={len(page)} total={meta.get("total")}'
            )
            if len(all_members) >= meta.get('total', len(all_members)) or not page:
                break
            offset += meta.get('limit', 50)

        groupusers = {}
        nusers = 0
        ninvites = 0
        for member in all_members:
            userid = member['id']
            user = self.id2users.get(userid)
            if not user:
                current_app.logger.error(f'{self.get_users_from_group.__qualname__}(): user id {userid} in group {self.communitygroupname} not found in user list')
                continue
            groupusers[userid] = user
            nusers += 1
        
        # include invites targeted for our group
        for invite in self.invites.values():
            invitegroups = self.invitegroups.get(invite['id'], [])
            if invitegroups and self.communitygroupid in invitegroups:
                groupusers[invite['email']] = invite
                ninvites += 1
                
        current_app.logger.debug(f'{self.get_users_from_group.__qualname__}(): found {len(groupusers)} ({nusers} users, {ninvites} invites) for community group {self.communitygroupname}')

        return groupusers

    def remove_user_from_group(self, groupuserkey):
        """remove user from internal group
        
        :param groupuserkey: userid for user
        """
        # by adding this here, the user will be removed from the group in finish_import
        # note that groupuserkey will be integer for existing user, and email address for invite
        if type(groupuserkey) is int:
            self.remove_userids.add(groupuserkey)
        else:
            self.remove_group_invites.add(groupuserkey)
        current_app.logger.debug(f'{self.remove_user_from_group.__qualname__}(): removed user id {groupuserkey} from group {self.communitygroupname}')
        
    def finish_import(self):    
        """finalize import process"""
        
        # add users to group
        if self.add_userids and not self._skip_for_dryrun(
                f'add users {sorted(self.id2users[uid]["username"] for uid in self.add_userids)}'):
            current_app.logger.debug(f'{self.finish_import.__qualname__}(): adding users {self.add_userids} to group {self.communitygroupname}')
            try:
                # https://docs.discourse.org/#tag/Groups/operation/addGroupMembers
                self.discourse.groups._(self.communitygroupid).members.json.put({
                    'usernames': ','.join([self.id2users[uid]['username'] for uid in list(self.add_userids)])
                })
            except DiscourseError as e:
                current_app.logger.error(f'{self.finish_import.__qualname__}(): error adding users to group {self.communitygroupname}: {e}')

        # remove users from group
        if self.remove_userids and not self._skip_for_dryrun(
                f'remove users {sorted(self.id2users[uid]["username"] for uid in self.remove_userids)}'):
            current_app.logger.debug(f'{self.finish_import.__qualname__}(): removing users {self.remove_userids} from group {self.communitygroupname}')
            try:
                # https://docs.discourse.org/#tag/Groups/operation/removeGroupMembers
                self.discourse.groups._(self.communitygroupid).members.json.delete({
                    'usernames': ','.join([self.id2users[uid]['username'] for uid in list(self.remove_userids)])
                })
            except DiscourseError as e:
                current_app.logger.error(f'{self.finish_import.__qualname__}(): error removing users from group {self.communitygroupname}: {e}')
        
        # remove group from invites
        if self.remove_group_invites:
            current_app.logger.debug(f'{self.finish_import.__qualname__}(): removing group {self.communitygroupname} from invites {self.remove_group_invites}')
            for email in self.remove_group_invites:
                invite = self.invites[email]
                invite_id = invite['id']
                email = invite['email']
                invite_group_ids = self.invitegroups[invite_id]

                # remove this group from the invite
                invite_group_ids.remove(self.communitygroupid)

                # still have other groups, so update invite. An expired invite is
                # updated rather than deleted, so the other groups' syncs renew it
                # instead of creating a new invite, which might send an email
                if len(invite_group_ids) != 0:
                    current_app.logger.debug(f'{self.finish_import.__qualname__}(): removing '
                                             f'group {self.communitygroupname} from Discourse invite for email {email}')
                    self._update_invite(invite, invite_group_ids, renew=False,
                                        caller=self.finish_import.__qualname__)

                # no other groups, so delete invite
                else:
                    current_app.logger.debug(f'{self.finish_import.__qualname__}(): deleting Discourse invite for email {email} since no more groups remain')
                    if self._skip_for_dryrun(f'delete invite {invite_id} for {email}'):
                        continue
                    try:
                        self.discourse.invites.json.delete({'id': invite_id})
                    except DiscourseError as e:
                        current_app.logger.error(f'{self.finish_import.__qualname__}(): error deleting Discourse invite for email {email}: {e}')
                # TODO: do we need to update our local invite tracking info?

        # release interprocess lock to prevent multiple imports at once
        self.lock.release()

    def add_user_to_group(self, svcuser, groupuserkey):
        """add user to internal group

        Args:
            svcuser: user record from service, which includes email
            groupuserkey (discourse user): userid from Discourse, or email address if no user yet
        """
        # if user exists in Discourse
        if groupuserkey and type(groupuserkey) is int:
            # an account created after start_import() fetched the user list (e.g. a
            # member signing up while this run is throttled) is in the email lookup
            # but not in id2users; fetch it so finish_import() has its username
            if groupuserkey not in self.id2users:
                try:
                    # https://docs.discourse.org/#tag/Users/operation/adminGetUser
                    self.id2users[groupuserkey] = self.discourse.admin.users._(groupuserkey).json.get({})
                except DiscourseError as e:
                    current_app.logger.error(f'{self.add_user_to_group.__qualname__}(): user id {groupuserkey} not in '
                                             f'user list and lookup failed, not adding to group {self.communitygroupname}: {e}')
                    return
            # by adding this here, the user will be added to the group in finish_import
            self.add_userids.add(groupuserkey)
            current_app.logger.debug(f'{self.add_user_to_group.__qualname__}(): added user id {groupuserkey} to group {self.communitygroupname}')
            
        # if user does not exist in Discourse yet
        # send an invite request if it hasn't already been sent
        else:
            email = self.get_email(svcuser)
            
            # handle if invite has already been sent
            if email in self.invites:
                # check what groups this invite is for -- if it's already for our group, skip
                invite = self.invites[email]
                invite_id = invite['id']
                invite_group_ids = self.invitegroups.get(invite_id, [])
    
                # add this group to the invite if it's not already there, and renew
                # it in the same call if it has expired or will expire soon
                renew = self._invite_needs_renewal(invite)
                if self.communitygroupid not in invite_group_ids or renew:
                    if self.communitygroupid not in invite_group_ids:
                        invite_group_ids.append(self.communitygroupid)
                        self.invitegroups[invite_id] = invite_group_ids
                    self._update_invite(invite, invite_group_ids, renew=renew,
                                        caller=self.add_user_to_group.__qualname__)

            # invite user if no invite exists; only send email if requested
            else:
                current_app.logger.debug(f'{self.add_user_to_group.__qualname__}(): creating Discourse invite for email {email} to join group {self.communitygroupname}')
                if self._skip_for_dryrun(f'create invite for {email}'
                                         + (', no email' if self.skipemail else ', sending email')):
                    return
                try:
                    self.discourse.invites.json.post({
                        'email': email,
                        'group_ids': self.communitygroupid,
                        'skip_email': self.skipemail,
                        # same expiration rule as renewals, rather than Discourse's invite_expiry_days default
                        'expires_at': self._new_expires_at().isoformat(),
                    })
                except DiscourseError as e:
                    current_app.logger.error(f'{self.add_user_to_group.__qualname__}(): error creating Discourse invite for email {email}: {e}')
                # TODO: do we need to update our local invite tracking info?

    def check_update_user_in_group(self, svcuser, groupuser):
        """this is called when the user is found in the group already. Nothing
        needs to be updated for an existing Discourse user, but a pending invite
        targeting the group is renewed if it has expired or will expire soon.

        Args:
            svcuser: user record from service, which includes email
            groupuser (discourse user): user record from Discourse, or invite record
        """
        # groupuser is an invite if get_users_from_group() took it from self.invites
        email = groupuser.get('email')
        if self.invites.get(email) is groupuser and self._invite_needs_renewal(groupuser):
            self._update_invite(groupuser, self.invitegroups[groupuser['id']], renew=True,
                                caller=self.check_update_user_in_group.__qualname__)
        super().check_update_user_in_group(svcuser, groupuser)
    

class RsuUserCommunitySyncManager(CommunitySyncManager):
    """puts users from RunSignup into discourse community group
    
    RunSignup user records are expected to have 'user' dict with 'email' key
    """

    def get_email(self, svcuser):
        """get email from service user record
        
        :param svcuser: record from service which contains email
        
        :rtype: email address (lower case)
        """
        return svcuser['user']['email'].lower()
    

class DbTagCommunitySyncManager(CommunitySyncManager):
    """puts users associated with a position tag into discourse community group
    
    Args:
        interest (str): interest short name
        tagname (str): tag name to filter users by
        communitygroupname (str): Discourse community group name
    """

    def __init__(self, interest, tagname, communitygroupname, skipemail, dryrun=False):
        """set up for tag-based user retrieval"""
        self.tagname = tagname
        g.interest = interest
        CommunitySyncManager.__init__(self, interest, communitygroupname, skipemail, dryrun)
        
    def get_email(self, svcuser):
        """get email from service user record
        
        :param svcuser: record from service which contains email
        
        :rtype: email address
        """
        return svcuser.email

    def get_users_from_service(self):
        """get users associated with a position tag from the database
        
        :rtype: dict of LocalUser records, indexed by email"""
        tag = Tag.query.filter_by(tag=self.tagname, **localinterest_query_params()).one()
        tags = [tag]
        dbusers = set()
        ondate = date.today()

        get_tags_users(tags, dbusers, ondate)
        users = {user.email: user for user in dbusers}
        current_app.logger.debug(f'{self.get_users_from_service.__qualname__}(): found {len(users)} users associated with tag "{self.tagname}"')
        
        return users


class RsuRaceCommunitySyncManager(RsuRaceSyncManager, RsuUserCommunitySyncManager):
    """put participants into discourse community group from RunSignup race"""
    
    def __init__(self, interest, raceid, communitygroupname, skipemail, dryrun=False):
        """initialize Rsu, Discourse, and base classes"""
        RsuUserCommunitySyncManager.__init__(self, interest, communitygroupname, skipemail, dryrun)
        RsuRaceSyncManager.__init__(self, raceid)

class RsuClubCommunitySyncManager(RsuClubSyncManager, RsuUserCommunitySyncManager):
    """put participants into discourse community group from RunSignup race"""
    
    def __init__(self, interest, clubid, communitygroupname, skipemail, dryrun=False):
        """initialize Rsu, Discourse, and base classes"""
        RsuUserCommunitySyncManager.__init__(self, interest, communitygroupname, skipemail, dryrun)
        RsuClubSyncManager.__init__(self, clubid)
