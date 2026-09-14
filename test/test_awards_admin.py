'''
test_awards_admin - test members.views.admin.awards_admin
=========================================================
'''

# standard
from datetime import datetime, timedelta
from urllib.parse import urlencode

# pypi
import pytest
from flask import Flask, current_app, g

# homegrown
from members.views.admin import awards_admin
from members.views.admin.awards_admin import AwardRaceView, RaceAwardsApi, AwardPickUpApi, AwardNotesApi
from members.model import db, LocalInterest, AwardsRace, AwardsEvent, AwardsDivision, AwardsAwardee
from loutilities.user.model import Interest
from loutilities.user.roles import ROLE_SUPER_ADMIN
from fakecurrentuser import FakeCurrentUser

_AWARDS_TABLES_MODELS = [AwardsRace, AwardsEvent, AwardsDivision, AwardsAwardee]


@pytest.fixture
def awards_dbapp(tmp_path):
    '''bare app with a real sqlite database including the awards_* tables.

    AwardsRace/Event/Division/Awardee.update_time use a raw MySQL-only server_default
    (CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, model.py) that SQLite's DDL parser
    rejects outright (near "ON": syntax error) -- see CLAUDE.md. bare_dbapp (conftest.py)
    works around this by excluding these four tables from create_all() entirely, which is
    fine for tests that never touch them, but this fixture actually needs real rows in
    them. Instead of excluding the tables, temporarily null out just the update_time
    columns' server_default/server_onupdate on the live Table objects for the duration of
    create_all() -- this doesn't touch model.py, and the value is restored immediately
    after (these are shared, module-level SQLAlchemy Table objects, so leaving the override
    in place would affect every other test in the session that touches these tables).
    '''
    app = Flask('members')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/default.db'
    app.config['SQLALCHEMY_BINDS'] = {'users': f'sqlite:///{tmp_path}/users.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    db.init_app(app)

    saved = [(m.__table__.c.update_time.server_default, m.__table__.c.update_time.server_onupdate)
             for m in _AWARDS_TABLES_MODELS]
    for m in _AWARDS_TABLES_MODELS:
        m.__table__.c.update_time.server_default = None
        m.__table__.c.update_time.server_onupdate = None
    try:
        with app.app_context():
            for bind_key, metadata in db.metadatas.items():
                engine = db.engines[bind_key]
                metadata.create_all(bind=engine)
            yield app
    finally:
        for m, (server_default, server_onupdate) in zip(_AWARDS_TABLES_MODELS, saved):
            m.__table__.c.update_time.server_default = server_default
            m.__table__.c.update_time.server_onupdate = server_onupdate


@pytest.fixture
def awardssetup(awards_dbapp):
    with awards_dbapp.app_context():
        interest_row = Interest(interest='fsrc', description='FSRC')
        localinterest = LocalInterest(interest_id=None)
        db.session.add_all([interest_row, localinterest])
        db.session.commit()
        localinterest.interest_id = interest_row.id
        db.session.commit()
        g.interest = 'fsrc'

        race = AwardsRace(interest=localinterest, name='Grand Prix Race', rsu_race_id=100)
        event = AwardsEvent(interest=localinterest, race=race, rsu_event_id=200, name='5K', date='2026-03-10')
        division = AwardsDivision(interest=localinterest, event=event, rsu_div_id=1, priority=1,
                                  name='Male Open', shortname='MOpen', num_awards=3)
        db.session.add_all([race, event, division])
        db.session.commit()

        yield {'localinterest': localinterest, 'race': race, 'event': event, 'division': division}


def _grant(monkeypatch, roles=(ROLE_SUPER_ADMIN,)):
    monkeypatch.setattr(awards_admin, 'current_user', FakeCurrentUser(roles))


def _result(order, first_name, last_name, result_id, bib, rsu_div_id=1):
    return {
        f'division-{rsu_div_id}-placement': order,
        'first_name': first_name,
        'last_name': last_name,
        'result_id': result_id,
        'bib': bib,
    }


class _FakeRsu:
    def __init__(self, results):
        '''
        :param results: a results list (returned every call), or a list of results lists to
            return in sequence -- the latter lets a test simulate update_event_awards()'s
            re-fetch after assign_race_divisions()/recalc_division_placements() seeing a
            different (updated) result set than the initial fetch
        '''
        if results and isinstance(results[0], list):
            self._results_sequence = list(results)
        else:
            self._results_sequence = [results]

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def geteventresults(self, race_id, event_id, individual_result_set_id, **kwargs):
        results = self._results_sequence.pop(0) if len(self._results_sequence) > 1 else self._results_sequence[0]
        return {'results': results, 'headers': {}}


def _fake_rsu_client(results):
    def make_client(**kwargs):
        return _FakeRsu(results)
    return make_client


def _participant(registration_id, bib_num, gender, age):
    return {'registration_id': registration_id, 'bib_num': bib_num, 'age': age, 'user': {'gender': gender}}


def _with_default_placement(result):
    '''
    awardssetup's fixture always creates a division with rsu_div_id=1 in the same event, so
    update_event_awards()'s loop looks up 'division-1-placement' on every result regardless of
    what other division a test is targeting -- default it to None (not awarded) unless a test
    constructs it explicitly
    '''
    result.setdefault('division-1-placement', None)
    return result


# ----------------------------------------------------------------------
# RaceAwardsApi.update_event_awards()
# ----------------------------------------------------------------------

def test_update_event_awards_creates_new_awardee(awardssetup, monkeypatch):
    event = awardssetup['event']
    results = [_result(1, 'Jane', 'Doe', 5001, 42)]
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client(results))

    RaceAwardsApi().update_event_awards(event)

    awardee = AwardsAwardee.query.filter_by(event_id=event.id).one()
    assert awardee.awardee_name == 'Jane Doe'
    assert awardee.awardee_bib == 42
    assert awardee.rsu_result_id == 5001
    assert awardee.order == 1
    assert awardee.active is True
    assert awardee.prev_awardee is None


def test_update_event_awards_ignores_placement_beyond_num_awards(awardssetup, monkeypatch):
    event = awardssetup['event']
    # division only has num_awards=3, so 4th place shouldn't get an awardee
    results = [_result(4, 'Nobody', 'Special', 5002, 99)]
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client(results))

    RaceAwardsApi().update_event_awards(event)

    assert AwardsAwardee.query.filter_by(event_id=event.id).count() == 0


def test_update_event_awards_same_bib_updates_result_id_in_place(awardssetup, monkeypatch):
    event = awardssetup['event']
    division = awardssetup['division']
    existing = AwardsAwardee(interest=awardssetup['localinterest'], div=division, event_id=event.id,
                             order=1, active=True, awardee_name='Jane Doe', awardee_bib=42,
                             rsu_result_id=5001)
    db.session.add(existing)
    db.session.commit()
    existing_id = existing.id

    # same person, same bib, but a new result_id (e.g. RSU recomputed results)
    results = [_result(1, 'Jane', 'Doe', 5099, 42)]
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client(results))

    RaceAwardsApi().update_event_awards(event)

    assert AwardsAwardee.query.filter_by(event_id=event.id).count() == 1
    updated = db.session.get(AwardsAwardee, existing_id)
    assert updated.rsu_result_id == 5099
    assert updated.active is True


def test_update_event_awards_bib_change_after_pickup_links_prev_awardee(awardssetup, monkeypatch):
    event = awardssetup['event']
    division = awardssetup['division']
    existing = AwardsAwardee(interest=awardssetup['localinterest'], div=division, event_id=event.id,
                             order=1, active=True, awardee_name='Jane Doe', awardee_bib=42,
                             rsu_result_id=5001, picked_up=True)
    db.session.add(existing)
    db.session.commit()
    existing_id = existing.id

    # bib number changed for the 1st place result -- different physical award
    results = [_result(1, 'Jo', 'Runner', 5099, 77)]
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client(results))

    RaceAwardsApi().update_event_awards(event)

    old = db.session.get(AwardsAwardee, existing_id)
    assert old.active is False

    new = AwardsAwardee.query.filter_by(event_id=event.id, active=True).one()
    assert new.awardee_name == 'Jo Runner'
    assert new.awardee_bib == 77

    # AwardsAwardee.prev_awardee (model.py) is deliberately declared without remote_side,
    # which makes SQLAlchemy infer the relationship backwards: the FK actually persists on
    # the OLD row (old.prev_awardee_id = new.id), not new.prev_awardee_id as the column name
    # would suggest -- see the comment on the relationship for why this is intentional (fixing
    # it would silently break every award pair already in the database, with no migration to
    # backfill them). What matters behaviorally is what RaceAwardsApi.get() actually reads:
    # new.prev_awardee resolving back to the old (picked-up) awardee, which is what drives the
    # admin UI's "already picked up" warning cell -- confirmed field-working in production.
    assert new.prev_awardee_id is None
    assert old.prev_awardee_id == new.id
    assert new.prev_awardee is not None
    assert new.prev_awardee.id == old.id
    assert new.prev_awardee.picked_up is True


# ----------------------------------------------------------------------
# RaceAwardsApi.update_event_awards() -- non-binary division assign+recalc (#723)
# ----------------------------------------------------------------------

def _nonbinary_division(awardssetup, rsu_div_id=2, min_age=None, max_age=None, num_awards=1):
    division = AwardsDivision(interest=awardssetup['localinterest'], event=awardssetup['event'],
                              rsu_div_id=rsu_div_id, priority=1, name='Non-Binary Overall',
                              shortname='NB', num_awards=num_awards, gender='X',
                              min_age=min_age, max_age=max_age)
    db.session.add(division)
    db.session.commit()
    return division


def _patch_assign_recalc(monkeypatch, participants):
    '''
    monkeypatch get_race_participants() to return a fixed participant list, and
    assign_race_divisions()/recalc_division_placements() to no-op while recording their
    calls, so a test can assert exactly when/how they were invoked
    '''
    calls = {'assign': [], 'recalc': []}
    monkeypatch.setattr(awards_admin, 'get_race_participants', lambda rsu, race_id, event_id: participants)
    monkeypatch.setattr(awards_admin, 'assign_race_divisions',
                        lambda rsu, race_id, event_id, assignments: calls['assign'].append(assignments))
    monkeypatch.setattr(awards_admin, 'recalc_division_placements',
                        lambda rsu, race_id, event_id: calls['recalc'].append(True))
    return calls


def test_update_event_awards_nonbinary_noop_when_already_placed(awardssetup, monkeypatch):
    '''
    if the division's placement is already populated for a non-binary registrant (e.g.
    another integrator like RaceDay Scoring already assigned+computed it), update_event_awards()
    must not call assign_race_divisions()/recalc_division_placements() at all -- the gate that
    makes this work regardless of which timing vendor produced the race's results (#723)
    '''
    event = awardssetup['event']
    division = _nonbinary_division(awardssetup)
    results = [_with_default_placement(_result(1, 'Alex', 'Runner', 6001, 55, rsu_div_id=division.rsu_div_id))]
    participants = [_participant(registration_id=900, bib_num=55, gender='X', age=30)]
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client(results))
    calls = _patch_assign_recalc(monkeypatch, participants)

    RaceAwardsApi().update_event_awards(event)

    assert calls['assign'] == []
    assert calls['recalc'] == []
    awardee = AwardsAwardee.query.filter_by(event_id=event.id, div=division).one()
    assert awardee.awardee_bib == 55


def test_update_event_awards_nonbinary_assigns_and_recalcs_when_placement_missing(awardssetup, monkeypatch):
    '''
    a non-binary registrant with no placement yet in the division gets assigned via
    assign_race_divisions(), followed by recalc_division_placements(), and the re-fetched
    (post-recalc) results are what actually create the awardee -- see #723
    '''
    event = awardssetup['event']
    division = _nonbinary_division(awardssetup)
    before = [_with_default_placement(_result(None, 'Alex', 'Runner', 6001, 55, rsu_div_id=division.rsu_div_id))]
    after = [_with_default_placement(_result(1, 'Alex', 'Runner', 6001, 55, rsu_div_id=division.rsu_div_id))]
    participants = [_participant(registration_id=900, bib_num=55, gender='X', age=30)]
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client([before, after]))
    calls = _patch_assign_recalc(monkeypatch, participants)

    RaceAwardsApi().update_event_awards(event)

    assert calls['assign'] == [[{'registration_id': 900, 'race_division_ids': [division.rsu_div_id]}]]
    assert len(calls['recalc']) == 1
    awardee = AwardsAwardee.query.filter_by(event_id=event.id, div=division).one()
    assert awardee.awardee_bib == 55


def test_update_event_awards_nonbinary_preserves_existing_membership_in_other_division(awardssetup, monkeypatch):
    '''
    assign-divisions completely REPLACES a registrant's manual-division memberships, it
    doesn't add to them. A registrant already correctly placed in one flagged division who
    becomes newly eligible for a SECOND flagged division must not lose the first membership --
    the assignment call has to include every division they're eligible for, not just the one
    missing a placement. Confirmed live: an assignment call listing only the new division
    silently wiped out the registrant's already-correct placement in the other one. See #723.
    '''
    event = awardssetup['event']
    division_a = _nonbinary_division(awardssetup, rsu_div_id=2)  # already has a placement
    division_b = _nonbinary_division(awardssetup, rsu_div_id=3, min_age=40)  # newly eligible, missing

    result = _with_default_placement(_result(1, 'Alex', 'Runner', 6001, 55, rsu_div_id=division_a.rsu_div_id))
    result[f'division-{division_b.rsu_div_id}-placement'] = None
    participants = [_participant(registration_id=900, bib_num=55, gender='X', age=45)]
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client([result]))
    calls = _patch_assign_recalc(monkeypatch, participants)

    RaceAwardsApi().update_event_awards(event)

    assert len(calls['assign']) == 1
    assert len(calls['assign'][0]) == 1
    assignment = calls['assign'][0][0]
    assert assignment['registration_id'] == 900
    assert set(assignment['race_division_ids']) == {division_a.rsu_div_id, division_b.rsu_div_id}


def test_update_event_awards_nonbinary_respects_age_range(awardssetup, monkeypatch):
    '''
    a non-binary registrant outside the division's admin-entered age range is never included
    in the assignment, even though they're gender == 'X'
    '''
    event = awardssetup['event']
    division = _nonbinary_division(awardssetup, min_age=40, max_age=None)
    results = [_with_default_placement(_result(None, 'Young', 'Runner', 6002, 56, rsu_div_id=division.rsu_div_id))]
    participants = [_participant(registration_id=901, bib_num=56, gender='X', age=25)]  # too young for 40+
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client(results))
    calls = _patch_assign_recalc(monkeypatch, participants)

    RaceAwardsApi().update_event_awards(event)

    assert calls['assign'] == []
    assert calls['recalc'] == []
    assert AwardsAwardee.query.filter_by(event_id=event.id, div=division).count() == 0


def test_update_event_awards_nonbinary_ignores_binary_gender_participants(awardssetup, monkeypatch):
    '''
    a Male/Female registrant is never assigned to a non-binary division, regardless of age
    fit -- guards the exclusion this whole workaround depends on
    '''
    event = awardssetup['event']
    division = _nonbinary_division(awardssetup)
    results = [_with_default_placement(_result(None, 'Some', 'Body', 6003, 57, rsu_div_id=division.rsu_div_id))]
    participants = [_participant(registration_id=902, bib_num=57, gender='M', age=30)]
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client(results))
    calls = _patch_assign_recalc(monkeypatch, participants)

    RaceAwardsApi().update_event_awards(event)

    assert calls['assign'] == []
    assert calls['recalc'] == []


def test_update_event_awards_no_nonbinary_divisions_skips_participant_fetch(awardssetup, monkeypatch):
    '''
    an event with no gender=='X' division never calls get_race_participants()/assign/recalc
    at all -- the common case (most events have no non-binary division) shouldn't cost any
    extra API calls
    '''
    event = awardssetup['event']  # awardssetup's division has gender=None, not 'X'
    results = [_result(1, 'Jane', 'Doe', 5001, 42)]
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_client(results))
    fetch_calls = []
    monkeypatch.setattr(awards_admin, 'get_race_participants',
                        lambda rsu, race_id, event_id: fetch_calls.append(True))

    RaceAwardsApi().update_event_awards(event)

    assert fetch_calls == []


# ----------------------------------------------------------------------
# AwardRaceView.update_divisions()
# ----------------------------------------------------------------------
# update_divisions() never references self, so it's called unbound (self=None),
# matching the "standalone algorithm" pattern already used for update_event_awards()
# above -- no need to construct a real AwardRaceView, which requires the full
# DbCrudApiInterestsRolePermissions constructor (columns, dbmapping, app blueprint, etc.)

_EVENT_START = '03/10/2026 08:00'  # matches rsudt format ('%m/%d/%Y %H:%M') in awards_admin.py


def _rsu_event(event_id=200, name='5K', start_time=_EVENT_START):
    return {'event_id': event_id, 'name': name, 'start_time': start_time}


def _rsu_division(rsu_division_id=1, name='Female Open', shortname='FOpen', priority=1,
                   num_awards=3, criteria='present'):
    '''
    criteria: 'present' includes auto_selection_criteria (gender='F', no age bounds);
    'none' includes auto_selection_criteria with no gender restriction; 'missing' omits
    the key entirely (RunSignUp's signature for a division it can't auto-place, e.g. a
    non-binary division -- see #723)
    '''
    division = {
        'race_division_id': rsu_division_id,
        'division_name': name,
        'division_short_name': shortname,
        'division_priority': priority,
        'show_top_num': num_awards,
    }
    if criteria == 'present':
        division['auto_selection_criteria'] = {'min_age': None, 'max_age': None, 'gender': 'F'}
    elif criteria == 'none':
        division['auto_selection_criteria'] = {'min_age': None, 'max_age': None, 'gender': None}
    # else 'missing': leave auto_selection_criteria out entirely
    return division


class _FakeRsuDivisions:
    def __init__(self, divisions_by_event):
        self._divisions_by_event = divisions_by_event

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def getracedivisions(self, race_id, event_id):
        return self._divisions_by_event.get(event_id, [])


def _fake_rsu_divisions_client(divisions_by_event):
    def make_client(**kwargs):
        return _FakeRsuDivisions(divisions_by_event)
    return make_client


def test_update_divisions_creates_new_event_and_gendered_division(awardssetup, monkeypatch):
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 3650

    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=300)]}
    divisions = {300: [_rsu_division(rsu_division_id=10, criteria='present')]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))

    AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    event = AwardsEvent.query.filter_by(race_id=race_row.id, rsu_event_id=300).one()
    assert event.name == '5K'
    division = AwardsDivision.query.filter_by(event_id=event.id, rsu_div_id=10).one()
    assert division.name == 'Female Open'
    assert division.num_awards == 3
    assert division.gender == 'F'
    assert division.min_age is None
    assert division.max_age is None
    assert division.auto_placed is True


def test_update_divisions_ungendered_computed_division_unaffected(awardssetup, monkeypatch):
    '''
    a division RunSignUp genuinely computes but leaves ungendered (criteria present,
    gender=None) is unaffected by the #723 fix -- still synced from RunSignUp every time
    '''
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 3650

    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=301)]}
    divisions = {301: [_rsu_division(rsu_division_id=11, name='Combined Open', criteria='none')]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))

    AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    event = AwardsEvent.query.filter_by(race_id=race_row.id, rsu_event_id=301).one()
    computed = AwardsDivision.query.filter_by(event_id=event.id, rsu_div_id=11).one()
    assert computed.gender is None
    assert computed.min_age is None
    assert computed.max_age is None


def test_update_divisions_defaults_gender_x_for_new_nonbinary_named_division(awardssetup, monkeypatch):
    '''
    a new division RunSignUp can't auto-place (criteria missing) defaults to gender='X'
    when its name matches a non-binary pattern -- see #723. min_age/max_age are left None;
    an admin fills those in via the UI once the division shows up. update_divisions() also
    returns a description of any such new division, so createrow()/updaterow() can surface it
    to the client via the DataTables Editor JSON response (self.responsekeys) for a
    submitSuccess alert -- not flash(), since this page is an AJAX-driven DataTables Editor
    flow with no full page render per action for a session-backed flash to surface on.
    '''
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 3650

    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=302)]}
    divisions = {302: [_rsu_division(rsu_division_id=12, name='Non-Binary Overall', criteria='missing')]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))

    new_divisions = AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    assert new_divisions == ['Non-Binary Overall (5K)']
    event = AwardsEvent.query.filter_by(race_id=race_row.id, rsu_event_id=302).one()
    division = AwardsDivision.query.filter_by(event_id=event.id, rsu_div_id=12).one()
    assert division.gender == 'X'
    assert division.min_age is None
    assert division.max_age is None
    assert division.auto_placed is False


def test_update_divisions_leaves_gender_none_for_uncomputed_division_not_named_nonbinary(awardssetup, monkeypatch):
    '''
    a criteria-less division that ISN'T named like a non-binary one (e.g. some other
    manually-curated combined award) is left gender=None -- the name match only defaults
    gender for divisions that look non-binary, not every criteria-less division
    '''
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 3650

    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=303)]}
    divisions = {303: [_rsu_division(rsu_division_id=13, name='Team Captain Award', criteria='missing')]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))

    new_divisions = AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    assert new_divisions == []
    event = AwardsEvent.query.filter_by(race_id=race_row.id, rsu_event_id=303).one()
    division = AwardsDivision.query.filter_by(event_id=event.id, rsu_div_id=13).one()
    assert division.gender is None


def test_update_divisions_preserves_admin_edits_across_resync(awardssetup, monkeypatch):
    '''
    once a division RunSignUp can't auto-place has admin-entered gender/min_age/max_age
    (whether from the create-time default above or a later admin edit), re-syncing must not
    clobber them back to None -- RunSignUp has nothing meaningful to offer for these fields
    on such a division. priority/name/num_awards should still update normally from RunSignUp.
    '''
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 3650
    event_row = AwardsEvent(interest=awardssetup['localinterest'], race=race_row, rsu_event_id=304,
                            name='Mile', date='2026-03-10')
    db.session.add(event_row)
    db.session.commit()
    division_row = AwardsDivision(interest=awardssetup['localinterest'], event=event_row, rsu_div_id=14,
                                  priority=5, name='Non-Binary Overall', shortname='NB', num_awards=1,
                                  gender='X', min_age=18, max_age=39)
    db.session.add(division_row)
    db.session.commit()

    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=304)]}
    divisions = {304: [_rsu_division(rsu_division_id=14, name='Non-Binary Overall', priority=1,
                                     num_awards=2, criteria='missing')]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))

    AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    db.session.refresh(division_row)
    assert division_row.gender == 'X'
    assert division_row.min_age == 18
    assert division_row.max_age == 39
    assert division_row.priority == 1  # still synced from RunSignUp
    assert division_row.num_awards == 2  # still synced from RunSignUp
    assert division_row.auto_placed is False


def test_update_divisions_auto_placed_flips_true_when_rsu_adds_criteria(awardssetup, monkeypatch):
    '''
    auto_placed reflects the CURRENT sync's finding unconditionally, unlike gender/min_age/
    max_age -- if RunSignUp later adds real auto-select criteria to a division it previously
    couldn't place (e.g. an RD fixes the division's setup in RunSignUp), the next sync should
    flip auto_placed to True and resume syncing gender/min_age/max_age from RunSignUp again.
    This transition also triggers a recalc: a division whose criteria just changed may have
    placements RunSignUp computed under the OLD criteria still sitting in its results (removing/
    adding criteria doesn't retroactively clear or recompute them) -- confirmed live, a division
    fixed from leaky age-only criteria to no criteria kept a stale, contaminated "winner" until
    an explicit recalc was issued. See #723.
    '''
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 3650
    event_row = AwardsEvent(interest=awardssetup['localinterest'], race=race_row, rsu_event_id=305,
                            name='Mile', date='2026-03-10')
    db.session.add(event_row)
    db.session.commit()
    division_row = AwardsDivision(interest=awardssetup['localinterest'], event=event_row, rsu_div_id=15,
                                  priority=5, name='Female Open', shortname='FOpen', num_awards=1,
                                  gender='X', min_age=18, max_age=39, auto_placed=False)
    db.session.add(division_row)
    db.session.commit()

    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=305)]}
    divisions = {305: [_rsu_division(rsu_division_id=15, name='Female Open', criteria='present')]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))
    recalc_calls = []
    monkeypatch.setattr(awards_admin, 'recalc_division_placements',
                        lambda rsu, race_id, event_id: recalc_calls.append((race_id, event_id)))

    AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    db.session.refresh(division_row)
    assert division_row.auto_placed is True
    assert division_row.gender == 'F'
    assert division_row.min_age is None
    assert division_row.max_age is None
    assert recalc_calls == [(race_row.rsu_race_id, 305)]


def test_update_divisions_no_criteria_change_skips_recalc(awardssetup, monkeypatch):
    '''
    a division whose auto_placed value is unchanged from the prior sync doesn't trigger a
    recalc -- only an actual transition (criteria added or removed) does
    '''
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 3650
    event_row = AwardsEvent(interest=awardssetup['localinterest'], race=race_row, rsu_event_id=306,
                            name='Mile', date='2026-03-10')
    db.session.add(event_row)
    db.session.commit()
    division_row = AwardsDivision(interest=awardssetup['localinterest'], event=event_row, rsu_div_id=16,
                                  priority=1, name='Female Open', shortname='FOpen', num_awards=1,
                                  gender='F', auto_placed=True)
    db.session.add(division_row)
    db.session.commit()

    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=306)]}
    divisions = {306: [_rsu_division(rsu_division_id=16, name='Female Open', criteria='present')]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))
    recalc_calls = []
    monkeypatch.setattr(awards_admin, 'recalc_division_placements',
                        lambda rsu, race_id, event_id: recalc_calls.append((race_id, event_id)))

    AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    assert recalc_calls == []


def test_update_divisions_skips_event_with_no_divisions(awardssetup, monkeypatch):
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 3650

    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=302)]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client({302: []}))

    AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    assert AwardsEvent.query.filter_by(race_id=race_row.id, rsu_event_id=302).first() is None


def test_update_divisions_skips_event_outside_awards_window(awardssetup, monkeypatch):
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 7

    old_start = (datetime.now() - timedelta(days=365)).strftime('%m/%d/%Y %H:%M')
    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=303, start_time=old_start)]}
    divisions = {303: [_rsu_division(rsu_division_id=13, criteria='present')]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))

    AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    assert AwardsEvent.query.filter_by(race_id=race_row.id, rsu_event_id=303).first() is None


def test_update_divisions_reduces_num_awards_deactivates_awardees(awardssetup, monkeypatch):
    event_row = awardssetup['event']
    division_row = awardssetup['division']  # rsu_div_id=1, num_awards=3 (see awardssetup fixture)
    current_app.config['AWARDS_WINDOW'] = 3650

    awardees = [
        AwardsAwardee(interest=awardssetup['localinterest'], div=division_row, event_id=event_row.id,
                      order=n, active=True, awardee_name=f'Runner {n}', awardee_bib=100 + n)
        for n in (1, 2, 3)
    ]
    db.session.add_all(awardees)
    db.session.commit()

    rsu_race = {'race_id': awardssetup['race'].rsu_race_id, 'events': [_rsu_event(event_id=event_row.rsu_event_id)]}
    divisions = {event_row.rsu_event_id: [
        _rsu_division(rsu_division_id=division_row.rsu_div_id, num_awards=1, criteria='present'),
    ]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))

    AwardRaceView.update_divisions(None, awardssetup['race'].id, rsu_race)

    db.session.refresh(division_row)
    assert division_row.num_awards == 1
    active_orders = {a.order for a in AwardsAwardee.query.filter_by(div=division_row, active=True).all()}
    assert active_orders == {1}
    inactive_orders = {a.order for a in AwardsAwardee.query.filter_by(div=division_row, active=False).all()}
    assert inactive_orders == {2, 3}


def test_update_divisions_deletes_removed_events_and_divisions(awardssetup, monkeypatch):
    event_row = awardssetup['event']
    current_app.config['AWARDS_WINDOW'] = 3650
    event_id = event_row.id
    division_id = awardssetup['division'].id

    # RunSignUp no longer returns this event at all (e.g. it was deleted upstream)
    rsu_race = {'race_id': awardssetup['race'].rsu_race_id, 'events': []}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client({}))

    AwardRaceView.update_divisions(None, awardssetup['race'].id, rsu_race)
    # update_divisions() never commits itself (same as production: the DbCrudApi Editor
    # framework commits after createrow()/updaterow() returns) -- commit here to match that
    db.session.commit()

    assert db.session.get(AwardsEvent, event_id) is None
    assert db.session.get(AwardsDivision, division_id) is None


# ----------------------------------------------------------------------
# AwardPickUpApi.post() / AwardNotesApi.get()/post()
# ----------------------------------------------------------------------

def _api_ctx(app, path_args):
    qs = urlencode(path_args)
    return app.test_request_context(f'/?{qs}', method='POST')


def test_awardpickupapi_toggles_picked_up(awardssetup, awards_dbapp, monkeypatch):
    division = awardssetup['division']
    awardee = AwardsAwardee(interest=awardssetup['localinterest'], div=division,
                            event_id=awardssetup['event'].id, order=1, active=True,
                            awardee_name='Jane Doe', awardee_bib=42, picked_up=False)
    db.session.add(awardee)
    db.session.commit()

    _grant(monkeypatch)
    with _api_ctx(awards_dbapp, {'race_id': awardssetup['race'].id, 'event_id': awardssetup['event'].id,
                                 'awardee_id': awardee.id, 'was_picked_up': 'false'}):
        g.interest = 'fsrc'
        resp = AwardPickUpApi().post()
    assert resp.json == {'status': 'success', 'picked_up': True, 'prev_picked_up': False}
    assert db.session.get(AwardsAwardee, awardee.id).picked_up is True


def test_awardnotesapi_sets_and_gets_notes(awardssetup, awards_dbapp, monkeypatch):
    division = awardssetup['division']
    awardee = AwardsAwardee(interest=awardssetup['localinterest'], div=division,
                            event_id=awardssetup['event'].id, order=1, active=True,
                            awardee_name='Jane Doe', awardee_bib=42)
    db.session.add(awardee)
    db.session.commit()

    _grant(monkeypatch)
    with _api_ctx(awards_dbapp, {'race_id': awardssetup['race'].id, 'event_id': awardssetup['event'].id,
                                 'awardee_id': awardee.id, 'notes': 'left at front desk'}):
        g.interest = 'fsrc'
        post_resp = AwardNotesApi().post()
    assert post_resp.json == {'status': 'success', 'notes': 'left at front desk'}

    with _api_ctx(awards_dbapp, {'race_id': awardssetup['race'].id, 'event_id': awardssetup['event'].id,
                                 'awardee_id': awardee.id}):
        g.interest = 'fsrc'
        get_resp = AwardNotesApi().get()
    assert get_resp.json == {'status': 'success', 'notes': 'left at front desk'}
