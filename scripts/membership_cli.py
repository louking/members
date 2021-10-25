"""
membership_cli - cli tasks needed for memberhip management
"""

# standard
from logging import basicConfig, DEBUG, ERROR, INFO, getLogger
from csv import DictReader
from datetime import datetime, timedelta

# pypi
from flask import g, current_app
from flask.cli import with_appcontext
from click import argument, group, option
from loutilities.timeu import asctime
from loutilities.transform import Transform
from running.runsignup import RunSignUp
from sortedcollections import ItemSortedDict
from sortedcontainers import SortedList

# homegrown
from scripts import catch_errors, ParameterError
from members.model import db, Member, Membership
from members.views.admin.viewhelpers import localinterest

# set up database date formatter
isodate = asctime('%Y-%m-%d')
rsudt = asctime('%Y-%m-%d %H:%M:%S')

# set up logging
basicConfig()

def timenow():
    return asctime('%H:%M:%S.%f').dt2asc(datetime.now())

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

    # normal case is download from RunSignUp service
    if not membershipfile:
        # get, check club id
        club_id = linterest.service_id
        if not (linterest.club_service == 'runsignup' and club_id):
            raise ParameterError('interest Club Service must be runsignup, and Service ID must be defined')
        
        # transform from RunSignUp to membershipfile format
        xform = Transform( {
                            'MemberID'       : lambda mem: mem['user']['user_id'],
                            'MembershipID'   : 'membership_id',
                            'MembershipType' : 'club_membership_level_name',
                            'FamilyName'     : lambda mem: mem['user']['last_name'],
                            'GivenName'      : lambda mem: mem['user']['first_name'],
                            'MiddleName'     : lambda mem: mem['user']['middle_name'],
                            'Gender'         : lambda mem: 'Female' if mem['user']['gender'] == 'F' else 'Male',
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
            # get current members from RunSignUp, and put into common format
            rawmemberships = rsu.members(club_id)
            memberships = [doxform(ms) for ms in rawmemberships]
            # for ms in rawmemberships:
            #     membership = {}
            #     xform.transform(ms, membership)
            #     memberships.append(membership)

    # membershipfile supplied
    else:
        with open(membershipfile, 'r') as _MF:
            MF = DictReader(_MF)
            # memberships already in common format
            memberships = [ms for ms in MF]
    
    # sort memberships by member (family_name, given_name, gender, dob), expiration_date
    memberships.sort(key=lambda m: (m['FamilyName'], m['GivenName'], m['Gender'], m['DOB'], m['ExpirationDate']))

    # set up member, membership transforms to create db records
    memxform = Transform({
        'family_name':  'FamilyName',
        'given_name':   'GivenName',
        'middle_name':  'MiddleName',
        'gender':       'Gender',
        'dob':          lambda m: isodate.asc2dt(m['DOB']).date(),
        'hometown':     lambda m: f'{m["City"]}, {m["State"]}' if 'City' in m and 'State' in m else '',
        'email':        'Email',
        'start_date':   lambda m: isodate.asc2dt(m['JoinDate']).date(),
        'end_date':     lambda m: isodate.asc2dt(m['ExpirationDate']).date(),
    }, sourceattr=False, targetattr=True)
    memupdate = Transform({
        'hometown':     'hometown',
        'email':        'email',
    }, sourceattr=True, targetattr=True)
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

    # insert member, membership records
    for m in memberships:
        # need MembershipId to be string for comparison with database key
        m['MembershipID'] = str(m['MembershipID'])

        filtermember ={
            'family_name': m['FamilyName'],
            'given_name':  m['GivenName'],
            'gender':      m['Gender'],
            'dob':         isodate.asc2dt(m['DOB'])
        }

        # get all the memberships for this member
        # note there may currently be more than one member record, as the memberships may be discontiguous
        thesemembers = SortedList(key=lambda m: m.end_date)
        thesemembers.update(Member.query.filter_by(**filtermember).all())

        # if member doesn't exist, create member and membership records
        if len(thesemembers) == 0:
            thismember = Member(interest=localinterest())
            memxform.transform(m, thismember)
            db.session.add(thismember)
            # flush so thismember can be referenced in thismship, and can be found in later processing
            db.session.flush()
            thesemembers.add(thismember)

            thismship = Membership(interest=localinterest(), member=thismember)
            mshipxform.transform(m, thismship)
            db.session.add(thismship)
            # flush so thismship can be found in later processing
            db.session.flush()
            
        # if there are already some memberships for this member, merge with this membership (m)
        else:
            # dbmships is keyed by svc_membership_id, sorted by end_date
            # NOTE: membership id is unique only within a member -- be careful if the use of dbmships changes 
            # to include multiple members
            dbmships = ItemSortedDict(lambda k, v: v.end_date)
            for thismember in thesemembers:
                for mship in thismember.memberships:
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
                # # weirdness if the new membership isn't the same membership id
                # if thismship.svc_membership_id != m.svc_membership_id:
                #     thislogger.error(f"{m['GivenName']} {m['FamilyName']} {m['DOB']} new membership {m['MembershipID']} with same \
                #                      end date but different membership id from {thismship.svc_membership_id}")
            

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
                    thislogger.warn(f'overlap detected for {memberkey}: end={endasc} was start={oldstartasc} now start={newstartasc}')
                    thismship.start_date = newstart

            # update appropriate member record(s), favoring earlier member records
            # NOTE: membership hometown, email get copied into appropriate member records; 
            #   since mship list is sorted, last one remains
            for mshipid in dbmships_keys:
                mship = dbmships[mshipid]
                for nextmndx in range(len(thesemembers)):
                    thismember = thesemembers[nextmndx]

                    # mship causes new member record before this one or after end of thesemembers
                    if (mship.end_date + timedelta(1) < thismember.start_date or
                            (nextmndx == len(thesemembers)-1) and mship.start_date > thismember.end_date + timedelta(1)):
                        newmember = Member(interest=localinterest())
                        # flush so thismember can be referenced in mship, and can be found in later processing
                        db.session.flush()
                        memxform.transform(m, newmember)
                        mship.member = newmember
                        break

                    # mship extends this member record from the beginning
                    if mship.end_date + timedelta(1) == thismember.start_date:
                        thismember.start_date = mship.start_date
                        mship.member = thismember
                        memupdate.transform(mship, thismember)
                        break

                    # mship extends this member from the end
                    if mship.start_date == thismember.end_date + timedelta(1):
                        thismember.end_date = mship.end_date
                        mship.member = thismember
                        memupdate.transform(mship, thismember)
                        break

                    # mship end date was changed
                    if (mship.start_date >=thismember.start_date and mship.start_date <= thismember.end_date 
                            and mship.end_date != thismember.end_date):
                        thismember.end_date = mship.end_date
                        mship.member = thismember
                        memupdate.transform(mship, thismember)
                        break

                    # mship wholly contained within this member
                    if mship.start_date >= thismember.start_date and mship.end_date <= thismember.end_date:
                        mship.member = thismember
                        memupdate.transform(mship, thismember)
                        break
                    
            # delete unused member records
            delmembers = []
            for mndx in range(len(thesemembers)):
                thismember = thesemembers[mndx]
                if len(thismember.memberships) == 0:
                    delmembers.append(thismember)
            for delmember in delmembers:
                db.session.delete(delmember)
                thesemembers.remove(delmember)
            if len(delmembers) > 0:
                db.session.flush()

            # merge member records as appropriate
            thisndx = 0
            delmembers = []
            for nextmndx in range(1, len(thesemembers)):
                thismember = thesemembers[thisndx]
                nextmember = thesemembers[nextmndx]
                if thismember.end_date + timedelta(1) == nextmember.start_date:
                    for mship in nextmember.memberships:
                        mship.member = thismember
                        delmembers.append(nextmember)
                else:
                    thisndx = nextmndx
            for delmember in delmembers:
                db.session.delete(delmember)
            if len(delmembers) > 0:
                db.session.flush()

    # make sure we remember everything we did
    db.session.commit()