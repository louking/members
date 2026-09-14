'''
helpers - commonly needed utilities
====================================================================================
'''
# standard
from json import dumps
from re import compile
from datetime import date

# pypi
from flask import g, current_app
from sqlalchemy import inspect
from running.runsignup import RunSignUp
from running.runsignup_fluent import RunSignupFluent

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

def _rsu_credentials():
    '''
    RunSignUp API credentials from app config, shared by make_runsignup_client()
    and make_runsignup_fluent_client()

    expects the following to be set in config: RSU_KEY, RSU_SECRET, RSU_API_REG_TOKEN, RSU_API_REG_SECRET
    '''
    return dict(
        key=current_app.config['RSU_KEY'],
        secret=current_app.config['RSU_SECRET'],
        api_reg_token=current_app.config['RSU_API_REG_TOKEN'],
        api_reg_secret=current_app.config['RSU_API_REG_SECRET'],
    )

def make_runsignup_client(**kwargs):
    '''
    create a running.runsignup.RunSignUp client (context manager style) configured from app config

    :param kwargs: additional RunSignUp() arguments, e.g. debug=True
    '''
    return RunSignUp(**_rsu_credentials(), **kwargs)

def make_runsignup_fluent_client(**kwargs):
    '''
    create a running.runsignup.RunSignupFluent client configured from app config

    :param kwargs: additional RunSignupFluent() arguments, e.g. debug=True
    '''
    return RunSignupFluent(**_rsu_credentials(), **kwargs)

def get_race_participants(rsu, race_id, event_id):
    '''
    fetch race participants for an event, with non-binary ('X') gender exposed -- RunSignUp
    nulls out a registrant's gender for an 'X' (non-binary) registration unless the
    undocumented-in-the-summary-docs `supports_nb` parameter is passed. See #723.

    :param rsu: open running.runsignup.RunSignUp client (make_runsignup_client())
    :param race_id: RunSignUp race id
    :param event_id: RunSignUp event id
    :return: [participant, participant, ...] (one page only -- fine for a small club race;
        see RunSignUp's "Get Race Participants" API for the full participant shape)
    '''
    data = rsu._rsuget(f'https://api.runsignup.com/rest/race/{race_id}/participants',
                        event_id=event_id, results_per_page=250, supports_nb='T')
    return data[0]['participants'] if data else []

def assign_race_divisions(rsu, race_id, event_id, assignments):
    '''
    explicitly assign registrants to race divisions RunSignUp has no auto-select criteria
    for (RunSignUp only allows this for such divisions -- see #723). This completely
    replaces each registrant's existing manually-assigned divisions, so `assignments`
    should include every division-less-criteria membership a registrant should have, not
    just the one being added.

    :param rsu: open running.runsignup.RunSignUp client (make_runsignup_client())
    :param race_id: RunSignUp race id
    :param event_id: RunSignUp event id
    :param assignments: [{'registration_id': int, 'race_division_ids': [int, ...]}, ...]
    '''
    creds = rsu.client_credentials.copy()
    creds.update({'event_id': event_id, 'format': 'json'})
    resp = rsu.session.post(
        f'https://api.runsignup.com/rest/race/{race_id}/divisions/assign-divisions',
        params=creds,
        data={'request_format': 'json', 'request': dumps({'assignments': assignments})},
    )
    data = resp.json()
    if not data.get('success'):
        raise RuntimeError(f'assign-divisions failed for race {race_id} event {event_id}: {data}')

def recalc_division_placements(rsu, race_id, event_id):
    '''
    ask RunSignUp to recompute division placements for an event's result set. Needed once,
    right after assign_race_divisions() gives a criteria-less division its first membership
    (RunSignUp doesn't compute a placement from the assignment alone) -- after that, RunSignUp
    recomputes it automatically whenever new results are posted, same as any other division.
    Safe/idempotent to call repeatedly. See #723.

    :param rsu: open running.runsignup.RunSignUp client (make_runsignup_client())
    :param race_id: RunSignUp race id
    :param event_id: RunSignUp event id
    '''
    creds = rsu.client_credentials.copy()
    creds.update({'event_id': event_id, 'format': 'json'})
    resp = rsu.session.post(
        f'https://api.runsignup.com/rest/race/{race_id}/results/recalc-division-placements',
        params=creds,
        data={'request_format': 'json'},
    )
    data = resp.json()
    if not data.get('success'):
        raise RuntimeError(f'recalc-division-placements failed for race {race_id} event {event_id}: {data}')

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
            and not inspect(userposition).deleted
            and (userposition.position is None or userposition.position.is_active)):
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
        if ((up.finishdate == None or up.finishdate >= onorafter)
                and not inspect(up).deleted
                and up.position.is_active):
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
