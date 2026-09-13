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
        self._results = results

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def geteventresults(self, race_id, event_id, individual_result_set_id):
        return {'results': self._results, 'headers': {}}


def _fake_rsu_client(results):
    def make_client(**kwargs):
        return _FakeRsu(results)
    return make_client


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


def test_update_divisions_no_criteria_division_currently_collapses_to_none(awardssetup, monkeypatch):
    '''
    documents CURRENT (pre-#723-fix) behavior: a division RunSignUp never auto-places
    (auto_selection_criteria missing entirely) is stored identically to a division RunSignUp
    computes but genuinely leaves ungendered (criteria present, gender=None) -- both collapse
    to gender=None/min_age=None/max_age=None. This is exactly the ambiguity #723's fix needs to
    resolve (by flagging "criteria missing" distinctly) -- once that lands, this test's
    expectations should change to assert the two cases are distinguishable.
    '''
    race_row = awardssetup['race']
    current_app.config['AWARDS_WINDOW'] = 3650

    rsu_race = {'race_id': race_row.rsu_race_id, 'events': [_rsu_event(event_id=301)]}
    divisions = {301: [
        _rsu_division(rsu_division_id=11, name='Ungendered (computed)', criteria='none'),
        _rsu_division(rsu_division_id=12, name='Non-Binary (uncomputed)', criteria='missing'),
    ]}
    monkeypatch.setattr(awards_admin, 'make_runsignup_client', _fake_rsu_divisions_client(divisions))

    AwardRaceView.update_divisions(None, race_row.id, rsu_race)

    event = AwardsEvent.query.filter_by(race_id=race_row.id, rsu_event_id=301).one()
    computed = AwardsDivision.query.filter_by(event_id=event.id, rsu_div_id=11).one()
    uncomputed = AwardsDivision.query.filter_by(event_id=event.id, rsu_div_id=12).one()
    assert computed.gender is None
    assert uncomputed.gender is None  # indistinguishable from `computed` today -- the #723 gap


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
