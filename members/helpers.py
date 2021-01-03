'''
helpers - commonly needed utilities
====================================================================================
'''
# standard
from re import compile
from datetime import date

# homegrown
from loutilities.timeu import asctime
dtrender = asctime('%Y-%m-%d')

class ParameterError(Exception):
    '''
    raised for invalid parameters, etc
    '''

def is_valid_date(thisdate):
    '''
    check for valid ISO thisdate format
    :param thisdate: date string should be in ISO format yyyy-mm-dd
    :return: True if format is good, else false
    '''
    # check if ISO thisdate https://regexr.com/37l5c
    pattern = compile('(19|20)\d\d-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])')
    if pattern.fullmatch(thisdate):
        return True
    else:
        return False

def is_userposition_active(userposition, thisdate):
    '''
    check if user was in position on a specific date

    :param userposition: UserPosition record
    :param thisdate: date to check if user was actively in position (datetime.date or ISO date string)
    :return: True if active on that date, otherwise false
    '''
    if isinstance(thisdate, str):
        if not is_valid_date(thisdate):
            raise ParameterError('not a valid ISO thisdate: {}'.format(thisdate))
        thisdate = dtrender.asc2dt(thisdate)

    elif not isinstance(thisdate, date):
        raise ParameterError('date needs to be datetime.date or ISO date string: {}'.format(thisdate))

    is_active = False
    if ((userposition.startdate == None or thisdate >= userposition.startdate)
            and (userposition.finishdate == None or thisdate <= userposition.finishdate)):
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