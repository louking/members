"""community helpers
"""

# stdlib
import time
from collections import deque

# pypi
from flask import current_app, g
from running.runsignup import RunSignupFluent
from fluent_discourse import Discourse, DiscourseError
from fasteners import InterProcessLock
from datetime import date

class _RateLimiter:
    """Sliding-window rate limiter. Blocks in acquire() when the call budget is exhausted."""
    def __init__(self, max_calls, window_secs):
        self.max_calls = max_calls
        self.window_secs = window_secs
        self._calls = deque()

    def acquire(self):
        now = time.monotonic()
        while self._calls and now - self._calls[0] >= self.window_secs:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            wait = self.window_secs - (now - self._calls[0])
            if wait > 0:
                current_app.logger.debug(
                    f'_RateLimiter.acquire(): throttling {wait:.1f}s '
                    f'({len(self._calls)}/{self.max_calls} calls in window)'
                )
                time.sleep(wait)
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.window_secs:
                    self._calls.popleft()
        self._calls.append(time.monotonic())


def make_discourse_client(interest: str) -> '_RateLimitedDiscourse':
    """Create a rate-limited fluent_discourse client for the given interest."""
    uinterest = interest.upper()
    try:
        return _RateLimitedDiscourse(
            Discourse(
                base_url=current_app.config[f'DISCOURSE_API_URL_{uinterest}'],
                username=current_app.config[f'DISCOURSE_API_INVITE_USERNAME_{uinterest}'],
                api_key=current_app.config[f'DISCOURSE_API_KEY_{uinterest}'],
                raise_for_rate_limit=False,
            ),
            _RateLimiter(max_calls=55, window_secs=60),
        )
    except KeyError as e:
        raise ValueError(f'Missing Discourse configuration for interest {interest}: {e}')


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

# homegrown
from .sync import SyncManager
from .helpers import get_tags_users
from .model import Tag, localinterest_query_params

class RsuRaceSyncManager(SyncManager):
    """put participants into internal group from RunSignup
    
    expects the following to be set in config:
        RSU_KEY
        RSU_SECRET
        
    Args:
        raceid (int): RunSignup race id
    """
    
    def __init__(self, raceid):
        """_summary_"""
        self.raceid = raceid

        self.rsu = RunSignupFluent(
            key=current_app.config['RSU_KEY'],
            secret=current_app.config['RSU_SECRET'],
        )
        
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
        
    Args:
        clubid (int): RunSignup club id
    """
    
    def __init__(self, clubid):
        """_summary_"""
        self.clubid = clubid

        self.rsu = RunSignupFluent(
            key=current_app.config['RSU_KEY'],
            secret=current_app.config['RSU_SECRET'],
        )
        
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
    """
    
    def __init__(self, interest, communitygroupname, skipemail):
        """_summary_

        """
        self.communitygroupname = communitygroupname
        self.skipemail = skipemail
        
        self.discourse = make_discourse_client(interest)
    
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
        # https://meta.discourse.org/t/run-data-explorer-queries-with-the-discourse-api/120063
        columns = []
        rows = []
        page = 0
        while True:
            resp = self.discourse.admin.plugins.explorer.queries._(query_id).run.post(
                {'params': {'page_num': str(page), 'page_size': str(page_size)}}
            )
            result_count = resp.get('result_count', 0)
            page_rows = resp.get('rows', [])
            current_app.logger.debug(
                f'{self._run_query_paged.__qualname__}(): query {query_id} page {page} '
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

    def start_import(self):
        """runtime start for import from Community perspective

        """
        # interprocess lock to prevent multiple imports at once
        lockfile = f'/tmp/communitygroupmanager.lock'
        self.lock = InterProcessLock(lockfile)
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
        if self.add_userids:
            current_app.logger.debug(f'{self.finish_import.__qualname__}(): adding users {self.add_userids} to group {self.communitygroupname}')
            try:
                # https://docs.discourse.org/#tag/Groups/operation/addGroupMembers
                self.discourse.groups._(self.communitygroupid).members.json.put({
                    'usernames': ','.join([self.id2users[uid]['username'] for uid in list(self.add_userids)])
                })
            except DiscourseError as e:
                current_app.logger.error(f'{self.finish_import.__qualname__}(): error adding users to group {self.communitygroupname}: {e}')

        # remove users from group
        if self.remove_userids:
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
                # TODO: what should we do if invite has expired?
                invite_group_ids.remove(self.communitygroupid)
                
                # still have other groups, so update invite
                if len(invite_group_ids) != 0:
                    group_ids = ','.join([str(g) for g in invite_group_ids])
                    current_app.logger.debug(f'{self.finish_import.__qualname__}(): updating '
                                                f'Discourse invite for email {email} to remove '
                                                f'group {self.communitygroupname} final group_ids {group_ids}')
                    # interface reverse engineered from Discourse web app
                    try:
                        self.discourse.invites._(invite_id).put({
                            'email': email,
                            'group_ids': group_ids,
                            'skip_email': True,
                        })
                    except DiscourseError as e:
                        current_app.logger.error(f'{self.finish_import.__qualname__}(): error updating Discourse invite for email {email}: {e}')

                # no other groups, so delete invite
                else:
                    current_app.logger.debug(f'{self.finish_import.__qualname__}(): deleting Discourse invite for email {email} since no more groups remain')
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
    
                # add this group to the invite if it's not already there
                # TODO: what should we do if invite has expired?
                if self.communitygroupid not in invite_group_ids:
                    invite_group_ids.append(self.communitygroupid)
                    group_ids = ','.join([str(g) for g in invite_group_ids])
                    current_app.logger.debug(f'{self.add_user_to_group.__qualname__}(): updating '
                                             f'Discourse invite for email {email} to add '
                                             f'group {self.communitygroupname} final group_ids {group_ids}')
                    # interface reverse engineered from Discourse web app
                    try:
                        self.discourse.invites._(invite_id).put({
                            'email': email,
                            'group_ids': group_ids,
                            'skip_email': True,
                        })
                    except DiscourseError as e:
                        current_app.logger.error(f'{self.add_user_to_group.__qualname__}(): error updating Discourse invite for email {email}: {e}')
                # TODO: do we need to update our local invite tracking info?

            # invite user if no invite exists; only send email if requested
            else:
                current_app.logger.debug(f'{self.add_user_to_group.__qualname__}(): creating Discourse invite for email {email} to join group {self.communitygroupname}')
                try:
                    self.discourse.invites.json.post({
                        'email': email,
                        'group_ids': self.communitygroupid,
                        'skip_email': self.skipemail,
                    })
                except DiscourseError as e:
                    current_app.logger.error(f'{self.add_user_to_group.__qualname__}(): error creating Discourse invite for email {email}: {e}')
                # TODO: do we need to update our local invite tracking info?

    def check_update_user_in_group(self, svcuser, groupuser):
        """this is called when the user is found in the group already. There
        shouldn't be anything that's needed to do to update, but is here for
        completeness.

        Args:
            svcuser: user record from service, which includes email
            groupuser (discourse user): user record from Discourse
        """
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

    def __init__(self, interest, tagname, communitygroupname, skipemail):
        """set up for tag-based user retrieval"""
        self.tagname = tagname
        g.interest = interest
        CommunitySyncManager.__init__(self, interest, communitygroupname, skipemail)
        
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
    
    def __init__(self, interest, raceid, communitygroupname, skipemail):
        """initialize Rsu, Discourse, and base classes"""
        RsuUserCommunitySyncManager.__init__(self, interest, communitygroupname, skipemail)
        RsuRaceSyncManager.__init__(self, raceid)

class RsuClubCommunitySyncManager(RsuClubSyncManager, RsuUserCommunitySyncManager):
    """put participants into discourse community group from RunSignup race"""
    
    def __init__(self, interest, clubid, communitygroupname, skipemail):
        """initialize Rsu, Discourse, and base classes"""
        RsuUserCommunitySyncManager.__init__(self, interest, communitygroupname, skipemail)
        RsuClubSyncManager.__init__(self, clubid)
