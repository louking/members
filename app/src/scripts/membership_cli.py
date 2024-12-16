"""
membership_cli - cli tasks needed for memberhip management
"""

# standard
from logging import basicConfig, DEBUG, INFO, WARNING, getLogger
from csv import DictReader
from datetime import timedelta, datetime
from os import mkdir
from os.path import join, exists
from hashlib import md5

# pypi
from flask import g, current_app
from flask.cli import with_appcontext
from click import argument, group, option
from loutilities.timeu import asctime
from loutilities.transform import Transform
from running.runsignup import RunSignUp
from sortedcollections import ItemSortedDict
from sortedcontainers import SortedList
from sqlalchemy import or_, and_, func
from mailchimp3 import MailChimp
from mailchimp3.mailchimpclient import MailChimpError

# homegrown
from scripts import catch_errors, ParameterError
from members.model import db, Member, MemberDates, Membership, TableUpdateTime
from members.views.admin.viewhelpers import localinterest
from members.applogging import timenow
from members.views.membership_common import analyzemembership

# set up database date formatter
isodate = asctime('%Y-%m-%d')
rsudt = asctime('%Y-%m-%d %H:%M:%S')

# set up logging
basicConfig()

# debug
debug = False

# needs to be before any commands
@group()
def membership():
    """Perform membership module tasks"""
    pass

@membership.command()
@argument('interest')
@option('--membershipfile', help='csv file with cached membership data')
@with_appcontext
@catch_errors
def update(interest, membershipfile):
    """update member, membership tables, from membershipfile if supplied, or from service based on interest"""
    thislogger = getLogger('members.cli')
    if debug:
        thislogger.setLevel(DEBUG)
    else:
        thislogger.setLevel(INFO)
    thislogger.propagate = True

    # set local interest
    g.interest = interest
    linterest = localinterest()

    try:
        # assume update will complete ok
        tableupdatetime = TableUpdateTime.query.filter_by(interest=linterest, tablename='member').one_or_none()
        if not tableupdatetime:
            tableupdatetime = TableUpdateTime(interest=linterest, tablename='member')
            db.session.add(tableupdatetime)
        tableupdatetime.lastchecked = datetime.today()
        
        # gender logic
        def get_gender(mem):
            """get gender from member record

            Args:
                mem (rsu_member): member record from RunSignUp

            Returns:
                str: gender for Member record in database
            """
            # bug in RunSignUp: no "gender" field if non-binary
            if 'gender' not in mem['user']:
                gender = 'Non-binary'
            
            else:
                rsu2gender = {
                    'M': 'Male',
                    'F': 'Female',
                    'X': 'Non-binary'
                }
                gender = rsu2gender[mem['user']['gender']]
            
            return gender
        
        # normal case is download from RunSignUp service
        if not membershipfile:
            # get, check club id
            club_id = linterest.service_id
            if not (linterest.club_service == 'runsignup' and club_id):
                raise ParameterError('interest Club Service must be runsignup, and Service ID must be defined')
            
            # transform: membership "file" format from RunSignUp API
            xform = Transform( {
                                'MemberID'       : lambda mem: mem['user']['user_id'],
                                'MembershipID'   : 'membership_id',
                                'MembershipType' : 'club_membership_level_name',
                                'FamilyName'     : lambda mem: mem['user']['last_name'],
                                'GivenName'      : lambda mem: mem['user']['first_name'],
                                'MiddleName'     : lambda mem: mem['user']['middle_name'] if mem['user']['middle_name'] else '',
                                'Gender'         : get_gender,
                                'DOB'            : lambda mem: mem['user']['dob'],
                                'City'           : lambda mem: mem['user']['address']['city'],
                                'State'          : lambda mem: mem['user']['address']['state'],
                                'Email'          : lambda mem: mem['user']['email'] if 'email' in mem['user'] else '',
                                'PrimaryMember'  : 'primary_member',
                                'JoinDate'       : 'membership_start',
                                'ExpirationDate' : 'membership_end',
                                'LastModified'   : 'last_modified',
                            },
                            sourceattr=False, # source and target are dicts
                            targetattr=False
                            )
            rsu = RunSignUp(key=current_app.config['RSU_KEY'], secret=current_app.config['RSU_SECRET'], debug=debug)

            def doxform(ms):
                membership = {}
                xform.transform(ms, membership)
                return membership

            with rsu:
                # get current and future members from RunSignUp, and put into common format
                rawmemberships = rsu.members(club_id, current_members_only='F')
                currfuturememberships = [m for m in rawmemberships if m['membership_end'] >= datetime.today().date().isoformat()]
                memberships = [doxform(ms) for ms in currfuturememberships]

        # membershipfile supplied
        else:
            with open(membershipfile, 'r') as _MF:
                MF = DictReader(_MF)
                # memberships already in common format
                memberships = [ms for ms in MF]
        
        # sort memberships by member (family_name, given_name, gender, dob), expiration_date
        memberships.sort(key=lambda m: (m['FamilyName'], m['GivenName'], m['Gender'], m['DOB'], m['ExpirationDate']))
        
        # optionally deduplicate memberships (RunSignup sometimes sends duplicate)
        if current_app.config.get('MEMBERSHIP_UPDATE_DEDUP', True):
            # the following will work because: each year gets a unique
            # membership id for the membership (multiple people), and each
            # member has a unique member id
            thislogger.debug(f"deduplicating memberships from RunSignup")
            deduped = []
            for i in range(len(memberships)):
                if (    i==len(memberships)-1 
                        or memberships[i]['MemberID'] != memberships[i+1]['MemberID']
                        or memberships[i]['MembershipID'] != memberships[i+1]['MembershipID']):
                    deduped.append(memberships[i])
                else:
                    thislogger.debug(f"duplicate removed for membership_id={memberships[i]['MembershipID']} user_id/member_id={memberships[i]['MemberID']}")
            
            # replace memberships with deduplicated list
            memberships = deduped

        # set up member, membership transforms to create db records
        # transform: member record from membership "file" format
        memxform = Transform({
            'family_name':      'FamilyName',
            'given_name':       'GivenName',
            'middle_name':      'MiddleName',
            'gender':           'Gender',
            'svc_member_id':    'MemberID',
            'dob':              lambda m: isodate.asc2dt(m['DOB']).date(),
            'hometown':         lambda m: f'{m["City"]}, {m["State"]}' if 'City' in m and 'State' in m else '',
            'email':            'Email',
        }, sourceattr=False, targetattr=True)
        memdatesxform = Transform({
            'start_date':           lambda m: isodate.asc2dt(m['JoinDate']).date(),
            'end_date':             lambda m: isodate.asc2dt(m['ExpirationDate']).date(),        
        })
        # transform: update member record from membership record
        memupdate = Transform({
            'svc_member_id':    'svc_member_id',
            'hometown':         'hometown',
            'email':            'email',
        }, sourceattr=True, targetattr=True)
        # transform: membership record from membership "file" format
        mshipxform = Transform({
            'svc_member_id':        'MemberID',
            'svc_membership_id':    'MembershipID',
            'membershiptype':       'MembershipType',
            'hometown':             lambda m: f'{m["City"]}, {m["State"]}' if 'City' in m and 'State' in m else '',
            'email':                'Email',
            'start_date':           lambda m: isodate.asc2dt(m['JoinDate']).date(),
            'end_date':             lambda m: isodate.asc2dt(m['ExpirationDate']).date(),
            'primary':              lambda m: m['PrimaryMember'].lower() == 't' or m['PrimaryMember'].lower() == 'yes',
            'last_modified':        lambda m: rsudt.asc2dt(m['LastModified']),
        }, sourceattr=False, targetattr=True)

        # insert member, memberdates, membership records
        for m in memberships:
            # need MembershipId to be string for comparison with database key
            m['MembershipID'] = str(m['MembershipID'])

            filternamedob = and_(
                Member.family_name == m['FamilyName'], 
                Member.given_name == m['GivenName'], 
                Member.gender == m['Gender'], 
                Member.dob == isodate.asc2dt(m['DOB'])
            )
            # func.binary forces case sensitive comparison. see https://stackoverflow.com/a/31788828/799921
            filtermemberid = Member.svc_member_id == func.binary(m['MemberID'])
            filtermember = or_(filternamedob, filtermemberid)

            # get all the memberdates records for this member
            # note there may currently be more than one member record, as the memberships may be discontiguous
            thesememberdates = SortedList(key=lambda md: md.end_date)
            thesememberdates.update(MemberDates.query.outerjoin(Member, MemberDates.member_id==Member.id).filter(filtermember).all())

            # if member doesn't exist, create member, memberdates, and membership records
            if len(thesememberdates) == 0:
                thismember = Member(interest=localinterest())
                memxform.transform(m, thismember)
                db.session.add(thismember)
                # flush so thismember can be referenced in thismship and thismdates, and can be found in later processing
                db.session.flush()
                
                thismdate = MemberDates(interest=localinterest(), member=thismember)
                memdatesxform.transform(m, thismdate)
                db.session.add(thismdate)
                thesememberdates.add(thismdate)

                thismship = Membership(interest=localinterest(), member=thismember, memberdates=thismdate)
                mshipxform.transform(m, thismship)
                db.session.add(thismship)
                
                # flush so thismdate and thismship can be found in later processing
                db.session.flush()
                
            # if there are already some memberships for this member, merge with this membership (m)
            else:
                # assumes memberdates.member is the same for all thesememberdates
                thismember = thesememberdates[0].member
                
                # dbmships is keyed by svc_membership_id, sorted by end_date
                # NOTE: svc_membership_id is unique only within a member -- be careful if the use of dbmships changes 
                # to include multiple members
                dbmships = ItemSortedDict(lambda k, v: v.end_date)
                for thismd in thesememberdates:
                    for mship in thismd.member.memberships:
                        dbmships[mship.svc_membership_id] = mship

                # add membership if not already there for this member
                mshipid = m['MembershipID']
                if mshipid not in dbmships:
                    newmship = True
                    thismship = Membership(interest=localinterest())
                    db.session.add(thismship)
                    # flush so thismship can be found in later processing
                    db.session.flush()

                # update existing membership
                else:
                    newmship = False
                    thismship = dbmships[mshipid]            

                # merge the new membership record into the database record
                mshipxform.transform(m, thismship)

                # add new membership to data structure
                if newmship:
                    dbmships[thismship.svc_membership_id] = thismship

                # need list view for some processing
                dbmships_keys = dbmships.keys()

                # check for overlaps
                for thisndx in range(1, len(dbmships_keys)):
                    prevmship = dbmships[dbmships_keys[thisndx-1]]
                    thismship = dbmships[dbmships_keys[thisndx]]
                    if thismship.start_date <= prevmship.end_date:
                        oldstart = thismship.start_date
                        newstart = prevmship.end_date + timedelta(1)
                        oldstartasc = isodate.dt2asc(oldstart)
                        newstartasc = isodate.dt2asc(newstart)
                        endasc = isodate.dt2asc(thismship.end_date)
                        memberkey = f'{m["FamilyName"]},{m["GivenName"]},{m["DOB"]}'
                        # TODO: check for #562 improve membertility member cache processing
                        thislogger.warning(f'overlap detected for {memberkey}: end={endasc} was start={oldstartasc} now start={newstartasc}')
                        thismship.start_date = newstart

                # calculate contigous range for membership records
                mship_date_range = {}
                contiguous_mshipids = []
                class DateRangeItem(object): 
                    def __init__(self, **kwargs):
                        for arg in kwargs:
                            setattr(self, arg, kwargs[arg])
                # dbmships is keyed by svc_membership_id, sorted by end_date
                for mshipid in dbmships_keys:
                    mship = dbmships[mshipid]
                    # contiguous_mshipids is empty (startup condition), let's get it started
                    if not contiguous_mshipids:
                        current_range = DateRangeItem(start_date=mship.start_date, end_date=mship.end_date)
                        contiguous_mshipids = [mshipid]
                    else:
                        last_mshipid = contiguous_mshipids[-1]
                        last_mship = dbmships[last_mshipid]
                        # if membership is contiguous
                        # TODO: check for #562 improve membertility member cache processing
                        if mship.start_date == last_mship.end_date + timedelta(1):
                            current_range.end_date = mship.end_date
                            contiguous_mshipids.append(mshipid)
                        # membership not contiguous
                        else:
                            for contiguous_mshipid in contiguous_mshipids:
                                mship_date_range[contiguous_mshipid] = current_range
                            current_range = DateRangeItem(start_date=mship.start_date, end_date=mship.end_date)
                            contiguous_mshipids = [mshipid]
                for contiguous_mshipid in contiguous_mshipids:
                    mship_date_range[contiguous_mshipid] = current_range
                
                # update appropriate memberdates record(s), favoring earlier records
                # NOTE: membership hometown, email get copied into appropriate member records; 
                #   since mship list is sorted, last one remains
                for mshipid in dbmships_keys:
                    mship = dbmships[mshipid]
                    date_range = mship_date_range[mshipid]
                    for nextmndx in range(len(thesememberdates)):
                        thismemberdates = thesememberdates[nextmndx]
                        lastmemberdates = thesememberdates[nextmndx-1] if nextmndx != 0 else None

                        # corner case: someone changed their birthdate and/or gender
                        # TODO: use Transform for these
                        thismemberdates.member.dob = isodate.asc2dt(m['DOB']).date()
                        thismemberdates.member.gender = m['Gender']
                        
                        # prefer last name found
                        thismemberdates.member.given_name = m['GivenName']
                        thismemberdates.member.family_name = m['FamilyName']
                        thismemberdates.member.middle_name = m['MiddleName'] if m['MiddleName'] else ''
                        
                        # mship causes new memberdates record before this one 
                        #   or after end of thesememberdates
                        #   or wholy between thesememberdates
                        if (mship.end_date + timedelta(1) < thismemberdates.start_date or
                                (nextmndx == len(thesememberdates)-1) and mship.start_date > thismemberdates.end_date + timedelta(1) or
                                lastmemberdates and mship.start_date > lastmemberdates.end_date + timedelta(1) and mship.end_date < thismemberdates.start_date):
                            newmemberdates = MemberDates(interest=localinterest(), member=thismember)
                            db.session.add(newmemberdates)
                            # flush so thismemberdates can be referenced in mship, and can be found in later processing
                            db.session.flush()
                            memdatesxform.transform(m, newmemberdates)
                            mship.member = thismember
                            mship.memberdates = newmemberdates
                            break

                        # mship extends this memberdates record from the beginning
                        if mship.end_date + timedelta(1) == thismemberdates.start_date:
                            thismemberdates.start_date = mship.start_date
                            mship.member = thismemberdates.member
                            mship.memberdates = thismemberdates
                            memupdate.transform(mship, thismemberdates.member)
                            break

                        # mship extends this memberdates from the end
                        if mship.start_date == thismemberdates.end_date + timedelta(1):
                            thismemberdates.end_date = mship.end_date
                            mship.member = thismemberdates.member
                            mship.memberdates = thismemberdates
                            memupdate.transform(mship, thismemberdates.member)
                            break

                        # mship end date was changed
                        if (mship.start_date >= thismemberdates.start_date and mship.start_date <= thismemberdates.end_date 
                                and date_range.end_date != thismemberdates.end_date):
                            thismemberdates.end_date = date_range.end_date
                            mship.member = thismemberdates.member
                            mship.memberdates = thismemberdates
                            memupdate.transform(mship, thismemberdates.member)
                            break

                        # mship start date was changed
                        if (mship.end_date >= thismemberdates.start_date and mship.end_date <= thismemberdates.end_date 
                                and date_range.start_date != thismemberdates.start_date):
                            thismemberdates.start_date = date_range.start_date
                            mship.member = thismemberdates.member
                            mship.memberdates = thismemberdates
                            memupdate.transform(mship, thismemberdates.member)
                            break

                        # mship wholly contained within this member
                        if mship.start_date >= thismemberdates.start_date and mship.end_date <= thismemberdates.end_date:
                            mship.member = thismemberdates.member
                            mship.memberdates = thismemberdates
                            memupdate.transform(mship, thismemberdates.member)
                            break
                        
                # delete unused memberdates records
                delmemberdates = []
                for mndx in range(len(thesememberdates)):
                    thismemberdates = thesememberdates[mndx]
                    if len(thismemberdates.member.memberships) == 0:
                        delmemberdates.append(thismemberdates)
                for delmember in delmemberdates:
                    db.session.delete(delmember)
                    thesememberdates.remove(delmember)
                if len(delmemberdates) > 0:
                    db.session.flush()

                # merge memberdates records as appropriate
                thisndx = 0
                delmemberdates = []
                for nextmndx in range(1, len(thesememberdates)):
                    thismemberdates = thesememberdates[thisndx]
                    nextmemberdates = thesememberdates[nextmndx]
                    if thismemberdates.end_date + timedelta(1) >= nextmemberdates.start_date:
                        for mship in nextmemberdates.member.memberships:
                            mship.member = thismemberdates.member
                            mship.memberdates = thismemberdates
                            delmemberdates.append(nextmemberdates)
                    else:
                        thisndx = nextmndx
                for delmember in delmemberdates:
                    db.session.delete(delmember)
                if len(delmemberdates) > 0:
                    db.session.flush()

        # save statistics file
        groupfolder = join(current_app.config['APP_FILE_FOLDER'], interest)
        if not exists(groupfolder):
            mkdir(groupfolder, mode=0o770)
        statspath = join(groupfolder, current_app.config['APP_STATS_FILENAME'])
        analyzemembership(statsfile=statspath)

        # make sure we remember everything we did
        db.session.commit()
    
    except:
        # back it out
        db.session.rollback()
        raise

@membership.command()
@argument('interest')
@option('--stats', default=False, is_flag=True, help='set for debug logging (DEBUG)')
@option('--debug', default=False, is_flag=True, help='set for stats logging (INFO)')
@with_appcontext
@catch_errors
def import2mailchimp(interest, stats, debug):
    """import member data from RunSignup to MailChimp"""

    # config file must have the following:
    # RSU_CLUB: <runsignup club_id>
    # RSU_KEY: <key from runsignup partnership>
    # RSU_SECRET: <secret from runsignup partnership>
    # MC_KEY: <api key from MailChimp>
    # MC_LIST: <name of list of interest>
    # MC_GROUPNAMES: groupname1,groupname2,...
    # MC_SHADOWCATEGORY: <name of shadowcategory>
    #     * shadowcategory groups are used to show desired inclusion but the group itself under other categories can be toggled by subscriber
    #     * this is used to prevent the recipient from being added back to the group against their wishes
    #     * if a groupname is not also under shadowcategory, it is only ticked if the subscriber was not present in the list prior to import
    #     * this category's group names include all of the group names which are reserved for members
    # MC_CURRMEMBERGROUP: <name of group which is set for current members>
    # MC_PASTMEMBERGROUP: <name of group which is set for current and past members>

    class Obj(object):
        '''
        just an object for saving attributes

        give str function
        '''
        def __str__(self):
            result = '<{}\n'.format(self.__class__.__name__)
            for key in list(vars(self).keys()):
                result += '   {} : {}\n'.format(key, getattr(self,key))
            result += '>'
            return result
        
    class Stat(Obj):
        '''
        stat object, stats initialized with 0

        :param statlist: list of stat attributes
        '''
        def __init__(self, statlist):
            for stat in statlist:
                setattr(self, stat, 0)


    def mcid(email):
        '''
        return md5 hash of lower case email address

        :param email: email address
        :rtype: md5 hash of email address
        '''
        h = md5(email.lower().encode('utf-8'))
        return h.hexdigest()

    def merge_dicts(*dict_args):
        '''
        Given any number of dicts, shallow copy and merge into a new dict,
        precedence goes to key value pairs in latter dicts.

        :param dict_args: any number of dicts
        :rtype: merged dict
        '''
        result = {}
        for dictionary in dict_args:
            result.update(dictionary)
        return result


    # set up logging
    thislogger = current_app.logger
    thislogger.propagate = True
    if debug:
        # set up debug logging
        thislogger.setLevel(DEBUG)
    elif stats:
        # INFO logging
        thislogger.setLevel(INFO)
    else:
        # WARNING logging
        thislogger.setLevel(WARNING)
    
    # load configuration
    club_id               = current_app.config['RSU_CLUB']
    rsukey                = current_app.config['RSU_KEY']
    rsusecret             = current_app.config['RSU_SECRET']
    mckey                 = current_app.config['MC_KEY']
    mclist                = current_app.config['MC_LIST']
    mcgroupnames          = current_app.config['MC_GROUPNAMES'].split(',')
    mcshadowcategory      = current_app.config['MC_SHADOWCATEGORY']
    mcpastmembergroupname = current_app.config['MC_PASTMEMBERGROUP']
    mccurrmembergroupname = current_app.config['MC_CURRMEMBERGROUP']
    mctimeout             = float(current_app.config['MC_TIMEOUT'])


    # use Transform to simplify RunSignUp format
    xform = Transform( {
                        'last'     : lambda mem: mem['user']['last_name'],
                        'first'    : lambda mem: mem['user']['first_name'],
                        'email'    : lambda mem: mem['user']['email'] if 'email' in mem['user'] else '',
                        'primary'  : lambda mem: mem['primary_member'] == 'T',
                        'start'    : 'membership_start',
                        'end'      : 'membership_end',
                        'modified' : 'last_modified',
                       },
                       # source and target are dicts, not objects
                       sourceattr=False,
                       targetattr=False
                     )

    # download current member list from RunSignUp
    # get current members from RunSignUp, transforming each to local format
    # only save one member per email address, primary member preferred
    rsu = RunSignUp(key=rsukey, secret=rsusecret, debug=debug)
    rsu.open()

    rsumembers = rsu.members(club_id)
    rsucurrmembers = {}
    for rsumember in rsumembers:
        memberrec = {}
        xform.transform(rsumember, memberrec)
        memberkey = memberrec['email'].lower()
        # only save if there's an email address
        # the primary member takes precedence, but if different email for nonprimary members save those as well
        if memberkey and (memberrec['primary'] or memberkey not in rsucurrmembers):
            rsucurrmembers[memberkey] = memberrec
    
    rsu.close()

    # It's important not to add someone back to a group which they've decided not to receive 
    # emails from. For this reason, a membergroup is defined with the same group names as
    # the real groups the user is interested in, for those groups which don't make up the whole
    # list.

    
    # download categories / groups from MailChimp
    client = MailChimp(mc_api=mckey, timeout=mctimeout)
    lists = client.lists.all(get_all=True, fields="lists.name,lists.id")
    list_id = [lst['id'] for lst in lists['lists'] if lst['name'] == mclist][0]
    categories = client.lists.interest_categories.all(list_id=list_id,fields="categories.title,categories.id")
    # groups are for anyone, shadowgroups are for members only
    groups = {}
    shadowgroups = {}
    # for debugging
    allgroups = {}
    for category in categories['categories']:
        mcgroups = client.lists.interest_categories.interests.all(list_id=list_id,category_id=category['id'],fields="interests.name,interests.id")
        for group in mcgroups['interests']:
            # save for debug
            allgroups[group['id']] = '{} / {}'.format(category['title'], group['name'])
            # special group to track past members
            if group['name'] == mcpastmembergroupname:
                mcpastmembergroup = group['id']

            # and current members
            elif group['name'] == mccurrmembergroupname:
                mccurrmembergroup = group['id']

            # newly found members are enrolled in all groups
            elif category['title'] != mcshadowcategory:
                groups[group['name']] = group['id']

            # shadowgroups is used to remember the state of member's only groups for previous members
            # if a member's membership has expired they must be removed from any group(s) which have the same name as 
            # those within the shadowgroup(s) (associated groups)
            # additionally if any nonmembers are found, they must be removed from the associated groups
            # this last bit can happen if someone who is not a member tries to enroll in a members only group
            else:
                shadowgroups[group['name']] = group['id']

    # set up specific groups for mc api
    mcapi = Obj()
    # members new to the list get all the groups
    mcapi.newmember = { id : True for id in list(groups.values()) + list(shadowgroups.values()) + [mccurrmembergroup] + [mcpastmembergroup]}
    # previous members who lapsed get the member groups disabled
    mcapi.nonmember = { id : False for id in [groups[gname] for gname in list(groups.keys()) if gname in shadowgroups] + [mccurrmembergroup] }
    # members groups set to True, for mcapi.unsubscribed merge
    mcapi.member = { id : True for id in list(shadowgroups.values()) + [groups[gname] for gname in list(groups.keys()) if gname in shadowgroups] + [mccurrmembergroup] + [mcpastmembergroup]}
    # unsubscribed members who previously were not past members get member groups turned on and 'other' groups turned off 
    mcapi.unsubscribed = merge_dicts (mcapi.member, { id:False for id in [groups[gname] for gname in list(groups.keys()) if gname not in shadowgroups] })

    # retrieve all members of this mailchimp list
    # key these into dict by id (md5 has of lower case email address)
    tmpmcmembers = client.lists.members.all(list_id=list_id, get_all=True, fields='members.id,members.email_address,members.status,members.merge_fields,members.interests')
    mcmembers = {}
    for mcmember in tmpmcmembers['members']:
        mcmembers[mcmember['id']] = mcmember

    # collect some stats
    stat = Stat(['addedtolist', 'newmemberunsubscribed', 'newmember', 'pastmember', 
                'nonmember', 'memberunsubscribedskipped', 'membercleanedskipped',
                'mailchimperror'])

    # loop through club members
    # if club member is in mailchimp
    #    make sure shadowgroups are set (but don't change groups as these may have been adjusted by club member)
    #    don't change subscribed status
    #    pop off mcmembers as we want to deal with the leftovers later
    # if club member is not already in mailchimp
    #    add assuming all groups (groups + shadowgroups)
    for memberkey in rsucurrmembers:
        clubmember = rsucurrmembers[memberkey]
        mcmemberid = mcid(clubmember['email'])
        thislogger.debug( 'processing {} {}'.format(clubmember['email'], mcmemberid) )

        # if club member is in mailchimp
        if mcmemberid in mcmembers:
            mcmember = mcmembers.pop(mcmemberid)
            # check if any changes are required
            # change required if current member not set
            if not mcmember['interests'][mccurrmembergroup]: 
                # if not past member, just set the needful
                if not mcmember['interests'][mcpastmembergroup]:
                    # if subscribed, all groups are set
                    if mcmember['status'] == 'subscribed':
                        client.lists.members.update(list_id=list_id, subscriber_hash=mcmemberid, data={'interests' : mcapi.newmember})
                        stat.newmember += 1
                    # if unsubscribed, subscribe them to member stuff, but remove everything else
                    elif mcmember['status'] == 'unsubscribed':
                        try:
                            client.lists.members.update(list_id=list_id, subscriber_hash=mcmemberid, data={'interests' : mcapi.unsubscribed, 'status' : 'subscribed'})
                            stat.newmemberunsubscribed += 1
                        # MailChimp won't let us resubscribe this member
                        except MailChimpError as e:
                            thislogger.info('member unsubscribed, skipped: {}'.format(clubmember['email']))
                            stat.memberunsubscribedskipped += 1
                    # other statuses are skipped
                    else:
                        thislogger.info('member cleaned, skipped: {}'.format(clubmember['email']))
                        stat.membercleanedskipped += 1;
                # past member, recall what they had set before for the member stuff
                else:
                    pastmemberinterests = merge_dicts({ groups[gname] : mcmember['interests'][shadowgroups[gname]] for gname in list(shadowgroups.keys()) }, 
                                                      { mccurrmembergroup : True })
                    client.lists.members.update(list_id=list_id, subscriber_hash=mcmemberid, data={'interests' : pastmemberinterests})
                    stat.pastmember += 1

        # if club member is missing from mailchimp
        else:
            try:
                client.lists.members.create(list_id=list_id, 
                                            data={
                                                'email_address' : clubmember['email'],
                                                'merge_fields'  : {'FNAME' : clubmember['first'], 'LNAME' : clubmember['last'] },
                                                'interests'     : mcapi.newmember,
                                                'status'        : 'subscribed'
                                            })
                stat.addedtolist += 1

            except MailChimpError as e:
                ed = e.args[0]
                thislogger.warning('MailChimpError {} for {}: {}'.format(ed['title'], clubmember['email'], ed['detail']))
                stat.mailchimperror += 1

    # at this point, mcmembers have only those enrollees who are not in the club
    # loop through each of these and make sure club only interests are removed
    for mcmemberid in mcmembers:
        mcmember = mcmembers[mcmemberid]
        # change required if current member set
        if mcmember['interests'][mccurrmembergroup]: 
            # save member interests for later if they rejoin
            memberinterests = {shadowgroups[gname]:mcmember['interests'][groups[gname]] for gname in shadowgroups}
            client.lists.members.update(list_id=list_id, subscriber_hash=mcmemberid, data={'interests' : merge_dicts(mcapi.nonmember, memberinterests)})
            stat.nonmember += 1

    # optionally log stats
    if stats:
        thislogger.info ( stat )


