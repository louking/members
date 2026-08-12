'''
test_awards_admin - test members.views.admin.awards_admin
=========================================================
'''

# standard
from urllib.parse import urlencode

# pypi
import pytest
from flask import Flask, g

# homegrown
from members.views.admin import awards_admin
from members.views.admin.awards_admin import RaceAwardsApi, AwardPickUpApi, AwardNotesApi
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
