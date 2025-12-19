'''
helpers - commonly needed utilities
====================================================================================
'''
# standard
from re import compile
from datetime import date

# pypi
from flask import g
from sqlalchemy import inspect

# homegrown
from .model import LocalUser, LocalInterest
from loutilities.user.model import Interest

from loutilities.timeu import asctime
dtrender = asctime('%Y-%m-%d')

class ParameterError(Exception):
    '''
    raised for invalid parameters, etc
    '''

def localinterest():
    interest = Interest.query.filter_by(interest=g.interest).one()
    return LocalInterest.query.filter_by(interest_id=interest.id).one()

def is_valid_date(thisdate):
    '''
    check for valid ISO thisdate format
    :param thisdate: date string should be in ISO format yyyy-mm-dd
    :return: True if format is good, else false
    '''
    # check if ISO thisdate https://regexr.com/37l5c
    pattern = compile('(19|20)\\d\\d-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])')
    if pattern.fullmatch(thisdate):
        return True
    else:
        return False

def to_date(thisdate):
    '''
    convert ISO date to datetime.date

    :param thisdate: date in ISO string or datetime.date format
    :return: date in datetime.date format
    '''
    if isinstance(thisdate, str):
        if not is_valid_date(thisdate):
            raise ParameterError('not a valid ISO date: {}'.format(thisdate))
        thisdate = dtrender.asc2dt(thisdate).date()

    elif not isinstance(thisdate, date):
        raise ParameterError('date needs to be datetime.date or ISO date string: {}'.format(thisdate))

    return thisdate

def is_userposition_active(userposition, thisdate):
    '''
    check if user was in position on a specific date

    :param userposition: UserPosition record
    :param thisdate: date to check if user was actively in position (datetime.date or ISO date string)
    :return: True if active on that date, otherwise false
    '''
    thisdate = to_date(thisdate)

    is_active = False
    if ((userposition.startdate == None or thisdate >= userposition.startdate)
            and (userposition.finishdate == None or thisdate <= userposition.finishdate)
            and not inspect(userposition).deleted):
        is_active = True

    return is_active

def positions_active(member, thisdate):
    '''
    return the list of currently active positions for a given member on a specified date

    :param member: LocalUser instance
    :param thisdate: date to check if user was actively in position (datetime.date or ISO date string)
    :return: [position, position, ...]
    '''
    positions = set()
    for userposition in member.userpositions:
        if is_userposition_active(userposition, thisdate):
            positions.add(userposition.position)
    return list(positions)

def member_position_active(member, position, thisdate):
    '''
    return list of active userposition records for this member/position

    ..note::
        should have single record, but allowing for more in case of data error

    :param member: LocalUser record
    :param position: Position record
    :param thisdate: date to check (ISO date or datetime.date)
    :return: [userposition], but if error [userposition, userposition, ...]
    '''
    # get all userposition records for this member for this position, sorted by start date
    ups = [up for up in member.userpositions if up.position == position and is_userposition_active(up, thisdate)]
    ups.sort(key=lambda i: i.startdate)
    return ups

def member_positions(member, position, onorafter='1970-01-01'):
    '''
    return list of userposition records for this member/position, on or after a date

    ..note::
        should have single record, but allowing for more in case of data error

    :param member: LocalUser record
    :param position: Position record
    :param onorafter: (optional) date to check for positions on or after (ISO date string or datetime.date) (default all)
    :return: [userposition, userposition, ...], sorted by startdate
    '''
    onorafter = to_date(onorafter)

    # get all userposition records for member / position
    # special case for deleted but not committed due to (at least) use within organization_admin.PositionWizardApi.post()
    allups = [up for up in member.userpositions if up.position == position and not inspect(up).deleted]

    # filter out any from before onorafter
    ups = []
    for up in allups:
        if up.finishdate == None or up.finishdate >= onorafter:
            ups.append(up)

    # sort by startdate, empty start date is equivalent to 1 Jan 1970
    ups.sort(key=lambda i: i.startdate if i.startdate else dtrender.asc2dt('1970-01-01').date())
    return ups

def members_active(position, thisdate):
    '''
    return the list of currently active members for a given position on a specified date

    :param position: Position instance
    :param thisdate: date to check if user was actively in position (datetime.date or ISO date string)
    :return: [member, member, ...]
    '''
    members = set()
    for userposition in position.userpositions:
        if is_userposition_active(userposition, thisdate):
            members.add(userposition.user)
    return list(members)

def members_active_currfuture(position, onorafter='1970-01-01'):
    '''
    return the list of current and future active members for a given position on a specified date

    :param position: Position instance
    :param onorafter: date to check if user is in position or will be in this position (datetime.date or ISO date string)
    :return: [member, member, ...]
    '''
    onorafter = to_date(onorafter)
    members = set()
    for up in position.userpositions:
        if (up.finishdate == None or up.finishdate >= onorafter) and not inspect(up).deleted:
            members.add(up.user)
    return list(members)

def member_qualifiers_active(position, thisdate):
    '''
    return the list of currently active members for a given position on a specified date, with qualifier

    :param position: Position instance
    :param thisdate: date to check if user was actively in position (datetime.date or ISO date string)
    :return: [{'member': member, 'qualifier': qualifier}, {'member': member, 'qualifier': qualifier}, ...]
    '''
    memberqualifiers = []
    for userposition in position.userpositions:
        memberqualifier = {'member': userposition.user, 'qualifier': userposition.qualifier}
        if is_userposition_active(userposition, thisdate) and memberqualifier not in memberqualifiers:
            memberqualifiers.append(memberqualifier)
    return memberqualifiers

def memberqualifierstr(member_qualifier):
    '''
    turn member_qualifier into string for display
    
    :param member_qualifier: item in list returned by member_qualifiers_active()
    :rtype: "name (qualifier)" if qualifier, else "name"
    '''
    name = member_qualifier['member'].name
    if member_qualifier['qualifier']:
        name += f' ({member_qualifier["qualifier"]})'
    return name

def all_active_members():
    '''
    return the list of all active members for the 'members' application

    :return: [member, member, ...]
    '''
    return LocalUser.query.filter_by(active=True, interest=localinterest()).all()

def get_tags_users(tags, users, ondate):
    '''
    get users which have specified tags (following position)

    :param tags: list of tags to search for
    :param users: input and output set of localusers
    :param ondate: date for which positions are effective for this member
    :return: None
    '''

    # collect all the users which have the indicated tags
    for tag in tags:
        for position in tag.positions:
            for member in members_active(position, ondate):
                users.add(member)
        for user in tag.users:
            users.add(user)
