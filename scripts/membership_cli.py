"""
membership_cli - cli tasks needed for memberhip management
"""

# standard
from logging import basicConfig, DEBUG, INFO, getLogger
from csv import DictReader
from datetime import timedelta, datetime
from os import mkdir
from os.path import join, exists

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
                        thislogger.warn(f'overlap detected for {memberkey}: end={endasc} was start={oldstartasc} now start={newstartasc}')
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