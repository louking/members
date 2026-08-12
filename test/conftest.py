import os

import pytest
from flask import Flask

# APP_NAME/APP_VER are normally supplied by Docker Compose's .env; set them here so the
# members package (which reads them at import time) also works for local/CI pytest runs
os.environ.setdefault('APP_NAME', 'members')
os.environ.setdefault('APP_VER', '0.0.0')

from members import create_app
from members.model import db
from members.settings import Testing

# AwardsRace/AwardsEvent/AwardsDivision/AwardsAwardee.update_time columns use a raw
# MySQL-only server_default (`CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`, model.py) --
# SQLite rejects the "ON UPDATE" clause, so a plain db.create_all() against the sqlite
# test database fails as soon as it reaches any of these tables. Exclude them here; add
# a table back to this set's exclusion (or give it a portable Python-side default like the
# other update_time columns in model.py use) before writing tests that need real rows in it.
_SQLITE_INCOMPATIBLE_TABLES = {'awards_race', 'awards_event', 'awards_div', 'awards_awardee'}


def _create_all_sqlite_safe():
    for bind_key, metadata in db.metadatas.items():
        engine = db.engines[bind_key]
        tables = [t for t in metadata.tables.values() if t.name not in _SQLITE_INCOMPATIBLE_TABLES]
        metadata.create_all(bind=engine, tables=tables)


def _drop_all_sqlite_safe():
    for bind_key, metadata in db.metadatas.items():
        engine = db.engines[bind_key]
        tables = [t for t in metadata.tables.values() if t.name not in _SQLITE_INCOMPATIBLE_TABLES]
        metadata.drop_all(bind=engine, tables=tables)


@pytest.fixture
def app():
    """Returns an app fixture with the testing configuration."""
    # init_for_operation=False skips init_uploads() (needs UPLOADED_IMAGES_DEST, not set
    # in Testing) and update_local_tables() -- neither is needed/wanted for tests
    app = create_app(Testing, init_for_operation=False)
    yield app


# executed prior to each test
@pytest.fixture
def dbapp(app):
    _drop_all_sqlite_safe()
    _create_all_sqlite_safe()
    yield app


@pytest.fixture
def client(app):
    client = app.test_client()
    yield client


# deliberately NOT using create_app(): it unconditionally queries the Application table
# (for g.loutility) while creating the app, but the app/dbapp fixtures above build the app
# first, then create tables after -- so that query always hits a table that doesn't exist yet.
# A bare Flask app with just members' db bound is enough for model/free-function-level tests
# that don't need the full app (routing, security, mail, etc); see test_helpers.py.
@pytest.fixture
def bareapp():
    """Minimal Flask app with members' db bound, no blueprints/extensions registered."""
    bareapp = Flask('members')
    bareapp.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    # loutilities.user.model.Application/Interest/User/Role share members' db object via the 'users' bind
    bareapp.config['SQLALCHEMY_BINDS'] = {'users': 'sqlite:///:memory:'}
    bareapp.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    bareapp.config['TESTING'] = True
    db.init_app(bareapp)
    yield bareapp


@pytest.fixture
def bare_dbapp(bareapp):
    """bareapp fixture with a fresh in-memory database created for the test."""
    with bareapp.app_context():
        _drop_all_sqlite_safe()
        _create_all_sqlite_safe()
        yield bareapp
