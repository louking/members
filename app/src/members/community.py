"""community helpers
"""

# pypi
from flask import current_app, g
from running.runsignup import RunSignupFluent
from fluent_discourse import Discourse, DiscourseError
from email_normalize import normalize
from fasteners import InterProcessLock
from datetime import date

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
                participants[p['user']['email']] = p
            
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
                members[m['user']['email']] = m
            
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
    
    def __init__(self, interest, communitygroupname):
        """_summary_

        """
        self.communitygroupname = communitygroupname
        
        try:
            uinterest = interest.upper()
            self.discourse = Discourse(
                base_url=current_app.config[f'DISCOURSE_API_URL_{uinterest}'],
                username=current_app.config[f'DISCOURSE_API_INVITE_USERNAME_{uinterest}'],
                api_key=current_app.config[f'DISCOURSE_API_KEY_{uinterest}'],
                raise_for_rate_limit=False,
            )
        except KeyError as e:
            raise ValueError(f'Missing Discourse configuration for interest {interest}: {e}')
    
    def get_group_key_from_service_user(self, svcuser):
        """get unique key for service user used by internal group
        
        :param svcuser: record from service which contains email
        :rtype: normalized email address
        """
        
        # find email in race participant record, normalize it, and use that as the key
        email = normalize(self.get_email(svcuser)).normalized_address
        return self.email2user[email]['user_id'] if email in self.email2user else None
    
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
        userrows = self.discourse.admin.users.json.get()
        self.id2users = {row['id']: row for row in userrows}

        # save group id for current group
        # https://docs.discourse.org/#tag/Groups/operation/listGroups
        groups = self.discourse.groups.json.get()
        self.communitygroupid = None
        for group in groups['groups']:
            if group['name'] == self.communitygroupname:
                self.communitygroupid = group['id']
                break
        if not self.communitygroupid:
            raise ValueError(f'{self.start_import.__qualname__}(): community group {self.communitygroupname} not found in Discourse')
        current_app.logger.debug(f'{self.start_import.__qualname__}(): community group {self.communitygroupname} has id {self.communitygroupid}')
        
        # https://meta.discourse.org/t/run-data-explorer-queries-with-the-discourse-api/120063
        resp = self.discourse.admin.plugins.explorer.queries._(current_app.config['DISCOURSE_API_INVITES_QUERY_FSRC']).run.post()
        inviterows = [dict(zip(resp['columns'], row)) for row in resp['rows']]
        # only save active invites targeted to specific email addresses which have not been redeemed
        self.invites = {row['email']: row for row in inviterows if not row['deleted_at'] and not row['invalidated_at'] 
                        and row['email'] 
                        and row['redemption_count']==0}

        resp = self.discourse.admin.plugins.explorer.queries._(current_app.config['DISCOURSE_API_INVITE_GROUPS_QUERY_FSRC']).run.post()
        invitegrouprows = [dict(zip(resp['columns'], row)) for row in resp['rows']]
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
        resp = self.discourse.admin.plugins.explorer.queries._(current_app.config['DISCOURSE_API_USER_EMAIL_QUERY_FSRC']).run.post()
        emailrows = [dict(zip(resp['columns'], row)) for row in resp['rows']]
        self.email2user = {row['normalized_email']: row for row in emailrows}
        id2emails = {}
        for row in emailrows:
            id2emails.setdefault(row['user_id'], [])
            id2emails[row['user_id']].append(row['email'])
        
        # https://docs.discourse.org/#tag/Groups/operation/listGroupMembers
        groupmembers = self.discourse.groups._(self.communitygroupname).members.json.get()
        
        groupusers = {}
        for member in groupmembers['members']:
            userid = member['id']
            user = self.id2users.get(userid)
            if not user:
                current_app.logger.error(f'{self.get_users_from_group.__qualname__}(): user id {userid} in group {self.communitygroupname} not found in user list')
                continue
            groupusers[userid] = user
        current_app.logger.debug(f'{self.get_users_from_group.__qualname__}(): found {len(groupusers)} users in community group {self.communitygroupname}')
        
        # include invites targeted for our group
        for invite in self.invites.values():
            invitegroups = self.invitegroups.get(invite['id'], [])
            if invitegroups and self.communitygroupid in invitegroups:
                normemail = normalize(invite['email']).normalized_address
                groupusers[normemail] = invite
                
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
            groupuserkey (discourse user): userid from Discourse, or None if no user yet
        """
        # if user exists in Discourse
        if groupuserkey:
            # by adding this here, the user will be added to the group in finish_import
            self.add_userids.add(groupuserkey)
            current_app.logger.debug(f'{self.add_user_to_group.__qualname__}(): added user id {groupuserkey} to group {self.communitygroupname}')
            
        # if user does not exist in Discourse yet
        # send an invite request if it hasn't already been sent
        else:
            email = self.get_email(svcuser)
            normemail = normalize(email).normalized_address
            
            # handle if invite has already been sent
            if normemail in self.invites:
                # check what groups this invite is for -- if it's already for our group, skip
                invite = self.invites[normemail]
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
                
            # invite user if no invite exists
            else:
                current_app.logger.debug(f'{self.add_user_to_group.__qualname__}(): creating Discourse invite for email {email} to join group {self.communitygroupname}')
                try:
                    self.discourse.invites.json.post({
                        'email': email,
                        'group_ids': self.communitygroupid,
                        'skip_email': False,
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
        """get email from service user record (non-normalized)
        
        :param svcuser: record from service which contains email
        
        :rtype: email address
        """
        return svcuser['user']['email']
    

class DbTagCommunitySyncManager(CommunitySyncManager):
    """puts users associated with a position tag into discourse community group
    
    Args:
        interest (str): interest short name
        tagname (str): tag name to filter users by
        communitygroupname (str): Discourse community group name
    """

    def __init__(self, interest, tagname, communitygroupname):
        """set up for tag-based user retrieval"""
        self.tagname = tagname
        g.interest = interest
        CommunitySyncManager.__init__(self, interest, communitygroupname)
        
    def get_email(self, svcuser):
        """get email from service user record (un-normalized)
        
        :param svcuser: record from service which contains email
        
        :rtype: email address
        """
        return svcuser.email

    def get_users_from_service(self):
        """get users associated with a position tag from the database
        
        :rtype: dict of LocalUser records, indexed by email (un-normalized)"""
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
    
    def __init__(self, interest, raceid, communitygroupname):
        """initialize Rsu, Discourse, and base classes"""
        RsuUserCommunitySyncManager.__init__(self, interest, communitygroupname)
        RsuRaceSyncManager.__init__(self, raceid)

class RsuClubCommunitySyncManager(RsuClubSyncManager, RsuUserCommunitySyncManager):
    """put participants into discourse community group from RunSignup race"""
    
    def __init__(self, interest, clubid, communitygroupname):
        """initialize Rsu, Discourse, and base classes"""
        RsuUserCommunitySyncManager.__init__(self, interest, communitygroupname)
        RsuClubSyncManager.__init__(self, clubid)
