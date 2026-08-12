'''
test_model - test members.model
=========================================================
'''

# pypi
import pytest
from flask import Flask, g

# homegrown
from members.model import (
    db, LocalUser, LocalInterest, TASKFIELDNAME_LEN,
    update_local_tables, localinterest_query_params, localinterest_viafilter, gen_fieldname,
)
from loutilities.user.model import Interest, Application, User

# same table set bare_dbapp (conftest.py) excludes from create_all() -- see CLAUDE.md
_SQLITE_INCOMPATIBLE_TABLES = {'awards_race', 'awards_event', 'awards_div', 'awards_awardee'}


# ----------------------------------------------------------------------
# gen_fieldname
# ----------------------------------------------------------------------

def test_gen_fieldname_length_and_charset():
    from string import ascii_letters
    name = gen_fieldname()
    assert len(name) == TASKFIELDNAME_LEN
    assert all(c in ascii_letters for c in name)


def test_gen_fieldname_not_constant():
    assert gen_fieldname() != gen_fieldname()


# ----------------------------------------------------------------------
# localinterest_query_params / localinterest_viafilter
# ----------------------------------------------------------------------

@pytest.fixture
def interestsetup(bare_dbapp):
    interest = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest, localinterest])
    db.session.commit()
    localinterest.interest_id = interest.id
    db.session.commit()
    g.interest = 'fsrc'
    return {'interest': interest, 'localinterest': localinterest}


def test_localinterest_query_params_returns_localinterest(interestsetup):
    assert localinterest_query_params() == {'interest': interestsetup['localinterest']}


def test_localinterest_viafilter_returns_interest_id(interestsetup):
    assert localinterest_viafilter() == {'interest_id': interestsetup['interest'].id}


# ----------------------------------------------------------------------
# update_local_tables
# ----------------------------------------------------------------------

# update_local_tables()'s two phases (_updateinterest() then _updateuser_byinterest(),
# loutilities.user.model.ManageLocalTables.update()) are separated only by a flush(), not a
# commit(). Against two separate sqlite ':memory:' engines (default bind for
# LocalInterest/LocalUser, 'users' bind for Interest/User/Application, as bare_dbapp uses),
# a LocalInterest row added and only flushed in phase one is not reliably visible to phase
# two's query of it, once phase two has queried the *other* bind in between -- confirmed
# empirically (querying LocalInterest right after the flush sees the row; after
# _updateuser_byinterest() queries the users bind and then re-queries LocalInterest, it's
# gone) and confirmed to be specific to ':memory:' (switching both binds to file-based
# sqlite databases, same as this fixture does, makes the *exact* same test pass unmodified).
# Not a real bug in update_local_tables()/ManageLocalTables -- production uses real,
# persistent MySQL connections, not two independent ':memory:' engines -- so these tests use
# file-based sqlite instead of bare_dbapp's ':memory:', rather than restructuring the test
# around the quirk or patching loutilities (a shared dependency) for a sqlite-only artifact.

@pytest.fixture
def filedb_app(tmp_path):
    '''like bareapp (conftest.py), but file-based sqlite instead of :memory: -- see comment above'''
    app = Flask('members')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/default.db'
    app.config['SQLALCHEMY_BINDS'] = {'users': f'sqlite:///{tmp_path}/users.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    db.init_app(app)
    with app.app_context():
        for bind_key, metadata in db.metadatas.items():
            engine = db.engines[bind_key]
            tables = [t for t in metadata.tables.values() if t.name not in _SQLITE_INCOMPATIBLE_TABLES]
            metadata.create_all(bind=engine, tables=tables)
        yield app


def test_update_local_tables_creates_localinterest_and_localuser(filedb_app):
    application = Application(application='members')
    interest = Interest(interest='fsrc', description='FSRC', public=True)
    interest.applications.append(application)
    user = User(email='jane@example.com', name='Jane Doe', given_name='Jane', active=True,
               fs_uniquifier='uniq1')
    user.interests.append(interest)
    db.session.add_all([application, interest, user])
    db.session.commit()

    update_local_tables()

    localinterest = LocalInterest.query.filter_by(interest_id=interest.id).one()
    localuser = LocalUser.query.filter_by(user_id=user.id, interest_id=localinterest.id).one()
    assert localuser.email == 'jane@example.com'
    assert localuser.name == 'Jane Doe'
    assert localuser.active is True


def test_update_local_tables_ignores_interest_for_other_application(filedb_app):
    application = Application(application='members')
    other_application = Application(application='contracts')
    interest = Interest(interest='other-app-interest', description='Not members', public=True)
    interest.applications.append(other_application)
    db.session.add_all([application, other_application, interest])
    db.session.commit()

    update_local_tables()

    assert LocalInterest.query.filter_by(interest_id=interest.id).count() == 0


def test_update_local_tables_syncs_user_deactivation(filedb_app):
    '''hasuserinterest=True mode (used here) copies every User onto every one of the app's
    interests regardless of that user's own interests list (see ManageLocalTables docstring)
    -- so what propagates a deactivation is the source User.active flag, not interest
    membership; copy_local_user_attrs copies it on every sync, same as name/email'''
    application = Application(application='members')
    interest = Interest(interest='fsrc', description='FSRC', public=True)
    interest.applications.append(application)
    user = User(email='jane@example.com', name='Jane Doe', given_name='Jane', active=True,
               fs_uniquifier='uniq1')
    user.interests.append(interest)
    db.session.add_all([application, interest, user])
    db.session.commit()
    update_local_tables()

    user.active = False
    db.session.commit()
    update_local_tables()

    localinterest = LocalInterest.query.filter_by(interest_id=interest.id).one()
    localuser = LocalUser.query.filter_by(user_id=user.id, interest_id=localinterest.id).one()
    assert localuser.active is False
