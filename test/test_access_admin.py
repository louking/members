'''
test_access_admin - test members.views.admin.access_admin
=========================================================
'''

# standard
from datetime import date, datetime, timezone

# pypi
import pytest
from flask import g

# homegrown
from members.views.admin.access_admin import systemaccesslevel_validate, accesstype_view, positionaccessnotice_validate
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
    '''
    calls the hooks in the same order the framework actually does -- prehook, then the edit
    itself, then posthook, then a single commit -- and confirms the notice survives a
    subsequent rollback (i.e. was truly committed, not merely flushed-and-visible within the
    same still-open session). See the equivalent PositionView test in
    test_organization_admin.py for why this ordering matters: an earlier version of this test
    committed the accesstype edit *before* calling the hook, which passed even though the real
    admin UI created zero PositionAccessNotice rows in production (#720's original fix put the
    sync call in editor_method_postcommit, which runs after the framework's own commit with
    no further commit -- so the row was only ever pending, never persisted)
    '''
    accesstype = accesstypesetup['accesstype']
    level = accesstypesetup['level']
    member = accesstypesetup['member']

    accesstype_view.action = 'edit'
    with bare_dbapp.test_request_context(f'/rest/{accesstype.id}'):
        accesstype_view.editor_method_prehook({})
        accesstype.access = [level]
        accesstype_view.editor_method_posthook({})
        db.session.commit()

    db.session.rollback()
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
        accesstype_view.editor_method_posthook({})
        db.session.commit()

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
        accesstype_view.editor_method_posthook({})
        db.session.commit()

    assert PositionAccessNotice.query.filter_by(user=member).count() == 0


# ----------------------------------------------------------------------
# PositionAccessNoticeView -- only Resolved should be editable. Confirmed live: 'type':
# 'readonly' on a relationship-treatment clientcolumn (user/system/accesslevel/
# reason_position) is purely cosmetic in loutilities.tables -- the constructor unconditionally
# makes it writable server-side regardless, so without the dbmapping patch in access_admin.py,
# an admin could reassign a notice's Member/System/Access Level/Position via the edit modal
# and have it silently persist. See louking/loutilities#109
# ----------------------------------------------------------------------

@pytest.fixture
def noticesetup(bare_dbapp):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()
    g.interest = 'fsrc'

    system1 = System(name='MailChimp', slug='mailchimp', interest=localinterest)
    system2 = System(name='RunSignUp', slug='runsignup', interest=localinterest)
    level1 = SystemAccessLevel(system=system1, name='Admin', slug='admin', interest=localinterest)
    level2 = SystemAccessLevel(system=system2, name='Admin', slug='admin', interest=localinterest)
    position1 = Position(position='Race Director', interest=localinterest)
    position2 = Position(position='Membership Chair', interest=localinterest)
    member1 = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=localinterest)
    member2 = LocalUser(name='John Smith', email='john@example.com', active=True, interest=localinterest)
    db.session.add_all([system1, system2, level1, level2, position1, position2, member1, member2])
    db.session.commit()

    notice = PositionAccessNotice(
        interest=localinterest, user=member1, system=system1, accesslevel=level1,
        action=POSITIONACCESSNOTICE_ACTION_GRANT, reason_position=position1,
        effective_date=date(2026, 1, 1), detected_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(notice)
    db.session.commit()

    # positionaccessnotice_validate() reads request.view_args['thisid'] for edit actions,
    # which only gets populated by real route matching
    bare_dbapp.add_url_rule('/rest/<thisid>', endpoint='dummy_notice_rest', view_func=lambda **kw: '')

    return {
        'localinterest': localinterest, 'notice': notice, 'member1': member1, 'member2': member2,
        'system1': system1, 'system2': system2, 'level1': level1, 'level2': level2,
        'position1': position1, 'position2': position2,
    }


def test_edit_rejects_reassigned_relationship_fields(noticesetup, bare_dbapp):
    notice = noticesetup['notice']

    # exactly what the edit modal in the screenshots submitted: a different member, system,
    # access level, and position, alongside a legitimate resolved_at change
    formdata = {
        'user': {'id': str(noticesetup['member2'].id)},
        'system': {'id': str(noticesetup['system2'].id)},
        'accesslevel': {'id': str(noticesetup['level2'].id)},
        'reason_position': {'id': str(noticesetup['position2'].id)},
        'resolved_at': '2026-09-08',
    }
    with bare_dbapp.test_request_context(f'/rest/{notice.id}'):
        results = positionaccessnotice_validate('edit', formdata)

    fields_flagged = {r['name'] for r in results}
    # '.id' suffix matches Editor's own field name for a relationship column (valuefield
    # defaults to 'id') -- a bare 'user' fieldError isn't a field Editor's client-side code
    # recognizes and throws "Uncaught Error: Unknown field: user" trying to process it
    assert fields_flagged == {'user.id', 'system.id', 'accesslevel.id', 'reason_position.id'}


def test_edit_allows_resolved_at_only_change(noticesetup, bare_dbapp):
    notice = noticesetup['notice']

    # unchanged relationship fields (matching current values) plus a legitimate resolved_at
    # edit -- the only kind of edit this view should actually accept
    formdata = {
        'user': {'id': str(noticesetup['member1'].id)},
        'system': {'id': str(noticesetup['system1'].id)},
        'accesslevel': {'id': str(noticesetup['level1'].id)},
        'reason_position': {'id': str(noticesetup['position1'].id)},
        'resolved_at': '2026-09-08',
    }
    with bare_dbapp.test_request_context(f'/rest/{notice.id}'):
        results = positionaccessnotice_validate('edit', formdata)

    assert results == []


def test_validate_noop_on_create(noticesetup, bare_dbapp):
    with bare_dbapp.test_request_context('/'):
        results = positionaccessnotice_validate('create', {})
    assert results == []
