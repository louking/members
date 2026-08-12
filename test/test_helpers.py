'''
test_helpers - test members.helpers
=========================================================
'''

# standard
from datetime import date

# pypi
import pytest
from flask import Flask
from sqlalchemy import inspect

# homegrown
from members.helpers import (
    ParameterError, is_valid_date, to_date, is_userposition_active,
    positions_active, member_position_active, member_positions,
    members_active, members_active_currfuture, member_qualifiers_active,
    memberqualifierstr, all_active_members, get_tags_users, localinterest,
    make_runsignup_client, make_runsignup_fluent_client,
)
from members.model import db, LocalInterest, LocalUser, Position, Tag, UserPosition
from running.runsignup import RunSignUp
from running.runsignup_fluent import RunSignupFluent
from loutilities.user.model import Interest


# ----------------------------------------------------------------------
# make_runsignup_client / make_runsignup_fluent_client
# ----------------------------------------------------------------------

@pytest.fixture
def rsuapp():
    '''minimal Flask app carrying just the RunSignUp config keys'''
    app = Flask(__name__)
    app.config['RSU_KEY'] = 'testkey'
    app.config['RSU_SECRET'] = 'testsecret'
    app.config['RSU_API_REG_TOKEN'] = 'testtoken'
    app.config['RSU_API_REG_SECRET'] = 'testregsecret'
    return app


def test_make_runsignup_client_reads_config(rsuapp):
    with rsuapp.app_context():
        client = make_runsignup_client()

    assert isinstance(client, RunSignUp)
    assert client.key == 'testkey'
    assert client.secret == 'testsecret'
    assert client.api_reg_token == 'testtoken'
    assert client.api_reg_secret == 'testregsecret'


def test_make_runsignup_client_passes_through_kwargs(rsuapp):
    with rsuapp.app_context():
        client = make_runsignup_client(debug=True)

    assert client.debug is True


def test_make_runsignup_client_missing_config_raises(rsuapp):
    del rsuapp.config['RSU_KEY']
    with rsuapp.app_context():
        with pytest.raises(KeyError):
            make_runsignup_client()


def test_make_runsignup_fluent_client_reads_config(rsuapp):
    with rsuapp.app_context():
        client = make_runsignup_fluent_client()

    assert isinstance(client, RunSignupFluent)
    # RunSignupFluent's __getattribute__ is overridden for its fluent request-building
    # API (e.g. client.race._(id).participants.get(...)), so normal attribute access
    # can't be used to inspect its state from outside -- bypass it the same way its own
    # __getattribute__ does internally, via object.__getattribute__(), to confirm
    # _rsu_credentials() actually reached the underlying request params/headers.
    params = object.__getattribute__(client, '_params')
    assert params['api_key'] == 'testkey'
    assert params['api_secret'] == 'testsecret'
    assert params['rsu_api_reg'] == 'testtoken'
    attributes = object.__getattribute__(client, '_attributes')
    assert attributes['headers'] == {'X-RSU-API-REG-SECRET': 'testregsecret'}


def test_make_runsignup_fluent_client_missing_config_raises(rsuapp):
    del rsuapp.config['RSU_KEY']
    with rsuapp.app_context():
        with pytest.raises(KeyError):
            make_runsignup_fluent_client()


# ----------------------------------------------------------------------
# is_valid_date / to_date
# ----------------------------------------------------------------------

def test_is_valid_date_accepts_iso_format():
    assert is_valid_date('2026-03-10') is True


def test_is_valid_date_rejects_bad_month():
    assert is_valid_date('2026-13-10') is False


def test_is_valid_date_rejects_bad_day():
    assert is_valid_date('2026-03-32') is False


def test_is_valid_date_rejects_non_iso_format():
    assert is_valid_date('03/10/2026') is False


def test_to_date_converts_iso_string():
    assert to_date('2026-03-10') == date(2026, 3, 10)


def test_to_date_passes_through_date_instance():
    d = date(2026, 3, 10)
    assert to_date(d) is d


def test_to_date_invalid_string_raises():
    with pytest.raises(ParameterError):
        to_date('not-a-date')


def test_to_date_wrong_type_raises():
    with pytest.raises(ParameterError):
        to_date(12345)


# ----------------------------------------------------------------------
# is_userposition_active
# ----------------------------------------------------------------------

# is_userposition_active always calls sqlalchemy's inspect(userposition), which requires
# a real mapped instance (NoInspectionAvailable otherwise) -- a plain stand-in class won't
# do, but a transient (never added to a session) UserPosition works fine, no db needed.

def test_is_userposition_active_no_dates_is_always_active():
    up = UserPosition()
    assert is_userposition_active(up, '2026-03-10') is True


def test_is_userposition_active_before_startdate_is_inactive():
    up = UserPosition(startdate=date(2026, 6, 1))
    assert is_userposition_active(up, '2026-03-10') is False


def test_is_userposition_active_on_startdate_is_active():
    up = UserPosition(startdate=date(2026, 3, 10))
    assert is_userposition_active(up, '2026-03-10') is True


def test_is_userposition_active_after_finishdate_is_inactive():
    up = UserPosition(finishdate=date(2026, 1, 1))
    assert is_userposition_active(up, '2026-03-10') is False


def test_is_userposition_active_on_finishdate_is_active():
    up = UserPosition(finishdate=date(2026, 3, 10))
    assert is_userposition_active(up, '2026-03-10') is True


def test_is_userposition_active_within_range_is_active():
    up = UserPosition(startdate=date(2026, 1, 1), finishdate=date(2026, 12, 31))
    assert is_userposition_active(up, '2026-03-10') is True


def test_is_userposition_active_pending_delete_is_inactive(userpositionsetup):
    up = userpositionsetup['userposition']
    assert is_userposition_active(up, '2026-03-10') is True

    # a row marked for deletion but not yet committed (e.g. mid-transaction in a view
    # handler) must not be treated as active -- inspect(...).deleted only flips True
    # once the DELETE has actually been flushed, so flush explicitly here
    db.session.delete(up)
    db.session.flush()
    assert inspect(up).deleted is True
    assert is_userposition_active(up, '2026-03-10') is False


# ----------------------------------------------------------------------
# fixtures shared by the db-backed tests below
# ----------------------------------------------------------------------

@pytest.fixture
def userpositionsetup(bare_dbapp):
    '''one LocalInterest / Position / LocalUser / UserPosition, active for all of 2026'''
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    userposition = UserPosition(user=member, position=position, interest=interest,
                                startdate=date(2026, 1, 1), finishdate=date(2026, 12, 31))
    db.session.add_all([interest, position, member, userposition])
    db.session.commit()
    return {'interest': interest, 'position': position, 'member': member, 'userposition': userposition}


# ----------------------------------------------------------------------
# positions_active / member_position_active / member_positions
# ----------------------------------------------------------------------

def test_positions_active_returns_positions_active_on_date(userpositionsetup):
    member = userpositionsetup['member']
    position = userpositionsetup['position']
    assert positions_active(member, '2026-03-10') == [position]


def test_positions_active_excludes_position_not_active_on_date(userpositionsetup):
    member = userpositionsetup['member']
    assert positions_active(member, '2027-03-10') == []


def test_member_position_active_returns_sorted_active_records(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    later = UserPosition(user=member, position=position, interest=interest,
                         startdate=date(2026, 6, 1), finishdate=None)
    earlier = UserPosition(user=member, position=position, interest=interest,
                           startdate=date(2026, 1, 1), finishdate=date(2026, 5, 31))
    db.session.add_all([interest, position, member, later, earlier])
    db.session.commit()

    result = member_position_active(member, position, '2026-03-10')
    assert result == [earlier]


def test_member_positions_sorts_by_startdate_treating_none_as_epoch(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    nostart = UserPosition(user=member, position=position, interest=interest,
                           startdate=None, finishdate=None)
    later = UserPosition(user=member, position=position, interest=interest,
                         startdate=date(2026, 6, 1), finishdate=None)
    db.session.add_all([interest, position, member, later, nostart])
    db.session.commit()

    result = member_positions(member, position)
    assert result == [nostart, later]


def test_member_positions_excludes_records_finished_before_onorafter(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    past = UserPosition(user=member, position=position, interest=interest,
                        startdate=date(2020, 1, 1), finishdate=date(2020, 12, 31))
    current = UserPosition(user=member, position=position, interest=interest,
                           startdate=date(2026, 1, 1), finishdate=None)
    db.session.add_all([interest, position, member, past, current])
    db.session.commit()

    result = member_positions(member, position, onorafter='2026-01-01')
    assert result == [current]


# ----------------------------------------------------------------------
# members_active / members_active_currfuture / member_qualifiers_active / memberqualifierstr
# ----------------------------------------------------------------------

def test_members_active_returns_members_active_on_date(userpositionsetup):
    position = userpositionsetup['position']
    member = userpositionsetup['member']
    assert members_active(position, '2026-03-10') == [member]


def test_members_active_currfuture_includes_future_position(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    future = UserPosition(user=member, position=position, interest=interest,
                          startdate=date(2027, 1, 1), finishdate=None)
    db.session.add_all([interest, position, member, future])
    db.session.commit()

    assert members_active_currfuture(position, onorafter='2026-01-01') == [member]


def test_members_active_currfuture_excludes_past_position(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    past = UserPosition(user=member, position=position, interest=interest,
                        startdate=date(2020, 1, 1), finishdate=date(2020, 12, 31))
    db.session.add_all([interest, position, member, past])
    db.session.commit()

    assert members_active_currfuture(position, onorafter='2026-01-01') == []


def test_member_qualifiers_active_includes_qualifier(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    up = UserPosition(user=member, position=position, interest=interest,
                      startdate=date(2026, 1, 1), finishdate=None, qualifier='interim')
    db.session.add_all([interest, position, member, up])
    db.session.commit()

    result = member_qualifiers_active(position, '2026-03-10')
    assert result == [{'member': member, 'qualifier': 'interim'}]


def test_member_qualifiers_active_dedups_identical_entries(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    up1 = UserPosition(user=member, position=position, interest=interest,
                       startdate=date(2026, 1, 1), finishdate=date(2026, 6, 30))
    up2 = UserPosition(user=member, position=position, interest=interest,
                       startdate=date(2026, 7, 1), finishdate=None)
    db.session.add_all([interest, position, member, up1, up2])
    db.session.commit()

    # both userpositions are active on their own dates and neither has a qualifier,
    # so the two calls below should each report a single (deduped) entry
    assert member_qualifiers_active(position, '2026-03-10') == [{'member': member, 'qualifier': None}]
    assert member_qualifiers_active(position, '2026-08-10') == [{'member': member, 'qualifier': None}]


def test_memberqualifierstr_without_qualifier(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    db.session.add_all([interest, member])
    db.session.commit()

    assert memberqualifierstr({'member': member, 'qualifier': None}) == 'Jane Doe'


def test_memberqualifierstr_with_qualifier(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    db.session.add_all([interest, member])
    db.session.commit()

    assert memberqualifierstr({'member': member, 'qualifier': 'interim'}) == 'Jane Doe (interim)'


# ----------------------------------------------------------------------
# localinterest / all_active_members / get_tags_users
# ----------------------------------------------------------------------

@pytest.fixture
def interestsetup(bare_dbapp):
    '''an Interest ('users' bind) paired with the matching LocalInterest, and g.interest set'''
    from flask import g
    interest = Interest(interest='fsrc', description='FSRC')
    localinterest_row = LocalInterest(interest_id=None)
    db.session.add_all([interest, localinterest_row])
    db.session.commit()
    localinterest_row.interest_id = interest.id
    db.session.commit()
    g.interest = 'fsrc'
    return {'interest': interest, 'localinterest': localinterest_row}


def test_localinterest_resolves_from_g_interest(interestsetup):
    assert localinterest().id == interestsetup['localinterest'].id


def test_all_active_members_returns_only_active_members_for_interest(interestsetup):
    li = interestsetup['localinterest']
    active = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=li)
    inactive = LocalUser(name='John Smith', email='john@example.com', active=False, interest=li)
    db.session.add_all([active, inactive])
    db.session.commit()

    assert all_active_members() == [active]


def test_get_tags_users_collects_users_by_position_and_direct_tag(interestsetup):
    li = interestsetup['localinterest']
    position = Position(position='Treasurer', interest=li)
    viaposition = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=li)
    up = UserPosition(user=viaposition, position=position, interest=li,
                      startdate=date(2026, 1, 1), finishdate=None)
    viatag = LocalUser(name='John Smith', email='john@example.com', active=True, interest=li)
    tag = Tag(tag='board', description='board members', interest=li)
    tag.positions.append(position)
    tag.users.append(viatag)
    db.session.add_all([position, viaposition, up, viatag, tag])
    db.session.commit()

    users = set()
    get_tags_users([tag], users, '2026-03-10')
    assert users == {viaposition, viatag}
