'''
test_access_admin - test members.views.admin.access_admin
=========================================================
'''

# standard
from datetime import date

# pypi
import pytest
from flask import g

# homegrown
from members.views.admin.access_admin import systemaccesslevel_validate, accesstype_view
from members.model import db, LocalInterest, LocalUser, Position, UserPosition, System, SystemAccessLevel, AccessType
from members.model import PositionAccessNotice, POSITIONACCESSNOTICE_ACTION_GRANT, POSITIONACCESSNOTICE_ACTION_REVOKE
from loutilities.user.model import Interest


@pytest.fixture
def levelsetup(bare_dbapp):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()
    g.interest = 'fsrc'

    system1 = System(name='MailChimp', slug='mailchimp', interest=localinterest)
    system2 = System(name='RunSignUp', slug='runsignup', interest=localinterest)
    existing = SystemAccessLevel(system=system1, name='Admin', slug='admin', interest=localinterest)
    db.session.add_all([system1, system2, existing])
    db.session.commit()

    # editor_method_prehook/systemaccesslevel_validate read request.view_args['thisid'] for
    # edit actions, which only gets populated by real route matching -- register the same
    # /rest/<thisid> shape the real Editor PUT route uses
    bare_dbapp.add_url_rule('/rest/<thisid>', endpoint='dummy', view_func=lambda **kw: '')

    return {'localinterest': localinterest, 'system1': system1, 'system2': system2, 'existing': existing}


def _formdata(system_id, slug):
    return {'system': {'id': str(system_id)}, 'slug': slug}


def test_create_rejects_duplicate_slug_within_same_system(levelsetup, bare_dbapp):
    with bare_dbapp.test_request_context('/'):
        results = systemaccesslevel_validate('create', _formdata(levelsetup['system1'].id, 'admin'))
    assert len(results) == 1
    assert results[0]['name'] == 'slug'


def test_create_allows_same_slug_on_different_system(levelsetup, bare_dbapp):
    with bare_dbapp.test_request_context('/'):
        results = systemaccesslevel_validate('create', _formdata(levelsetup['system2'].id, 'admin'))
    assert results == []


def test_create_allows_unique_slug(levelsetup, bare_dbapp):
    with bare_dbapp.test_request_context('/'):
        results = systemaccesslevel_validate('create', _formdata(levelsetup['system1'].id, 'viewer'))
    assert results == []


def test_edit_rejects_duplicate_slug_from_another_row(levelsetup, bare_dbapp):
    # a second row on system1, being edited to collide with 'existing's slug
    other = SystemAccessLevel(system=levelsetup['system1'], name='Viewer', slug='viewer',
                              interest=levelsetup['localinterest'])
    db.session.add(other)
    db.session.commit()

    with bare_dbapp.test_request_context(f'/rest/{other.id}'):
        results = systemaccesslevel_validate('edit', _formdata(levelsetup['system1'].id, 'admin'))
    assert len(results) == 1
    assert results[0]['name'] == 'slug'


def test_edit_allows_keeping_own_slug(levelsetup, bare_dbapp):
    existing = levelsetup['existing']
    with bare_dbapp.test_request_context(f'/rest/{existing.id}'):
        results = systemaccesslevel_validate('edit', _formdata(levelsetup['system1'].id, 'admin'))
    assert results == []


def test_validate_noop_on_refresh(levelsetup, bare_dbapp):
    with bare_dbapp.test_request_context('/'):
        results = systemaccesslevel_validate('refresh', _formdata(levelsetup['system1'].id, 'admin'))
    assert results == []


# ----------------------------------------------------------------------
# AccessTypeView -- access checklist reacts to an access type's own
# access members changing, for every position/holder that uses it
# (see #720)
# ----------------------------------------------------------------------

@pytest.fixture
def accesstypesetup(bare_dbapp):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()
    g.interest = 'fsrc'

    system = System(name='MailChimp', slug='mailchimp', interest=localinterest)
    level = SystemAccessLevel(system=system, name='Admin', slug='admin', interest=localinterest)
    accesstype = AccessType(name='RD Bundle', slug='rd-bundle', interest=localinterest)
    position = Position(position='Race Director', interest=localinterest, accesstypes=[accesstype])
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=localinterest)
    db.session.add_all([system, level, accesstype, position, member])
    up = UserPosition(user=member, position=position, interest=localinterest,
                      startdate=date(2026, 1, 1), finishdate=None)
    db.session.add(up)
    db.session.commit()

    bare_dbapp.add_url_rule('/rest/<thisid>', endpoint='dummy_accesstype_rest', view_func=lambda **kw: '')

    return {'localinterest': localinterest, 'system': system, 'level': level, 'accesstype': accesstype,
            'position': position, 'member': member}


def test_accesstypeview_edit_creates_grant_notice_for_holders(accesstypesetup, bare_dbapp):
    accesstype = accesstypesetup['accesstype']
    level = accesstypesetup['level']
    member = accesstypesetup['member']

    accesstype_view.action = 'edit'
    with bare_dbapp.test_request_context(f'/rest/{accesstype.id}'):
        accesstype_view.editor_method_prehook({})
        accesstype.access = [level]
        db.session.commit()
        accesstype_view.editor_method_postcommit({})

    notices = PositionAccessNotice.query.filter_by(user=member).all()
    assert len(notices) == 1
    assert notices[0].action == POSITIONACCESSNOTICE_ACTION_GRANT


def test_accesstypeview_edit_creates_revoke_notice_for_holders(accesstypesetup, bare_dbapp):
    accesstype = accesstypesetup['accesstype']
    level = accesstypesetup['level']
    member = accesstypesetup['member']
    accesstype.access = [level]
    db.session.commit()

    accesstype_view.action = 'edit'
    with bare_dbapp.test_request_context(f'/rest/{accesstype.id}'):
        accesstype_view.editor_method_prehook({})
        accesstype.access = []
        db.session.commit()
        accesstype_view.editor_method_postcommit({})

    notices = PositionAccessNotice.query.filter_by(user=member).all()
    assert len(notices) == 1
    assert notices[0].action == POSITIONACCESSNOTICE_ACTION_REVOKE


def test_accesstypeview_edit_no_notice_when_access_unaffected(accesstypesetup, bare_dbapp):
    accesstype = accesstypesetup['accesstype']
    level = accesstypesetup['level']
    member = accesstypesetup['member']
    accesstype.access = [level]
    db.session.commit()

    accesstype_view.action = 'edit'
    with bare_dbapp.test_request_context(f'/rest/{accesstype.id}'):
        accesstype_view.editor_method_prehook({})
        accesstype.description = 'updated description'
        db.session.commit()
        accesstype_view.editor_method_postcommit({})

    assert PositionAccessNotice.query.filter_by(user=member).count() == 0
