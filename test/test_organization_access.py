'''
test_organization_access - test members.organization_access
=========================================================
'''

# standard
from datetime import date

# pypi
import pytest
from flask import g

# homegrown
from members.model import db, LocalInterest, LocalUser, Position, UserPosition
from members.model import System, SystemAccessLevel, AccessType, PositionAccessNotice
from members.model import POSITIONACCESSNOTICE_ACTION_GRANT, POSITIONACCESSNOTICE_ACTION_REVOKE
from members.organization_access import compute_required_access, sync_access_notices
from loutilities.user.model import Interest


@pytest.fixture
def accesssetup(bare_dbapp):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()
    g.interest = 'fsrc'

    system = System(name='MailChimp', interest=localinterest)
    level = SystemAccessLevel(system=system, name='Admin', interest=localinterest)
    db.session.add_all([system, level])
    db.session.commit()

    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=localinterest)
    positiona = Position(position='Race Director', interest=localinterest, direct_access=[level])
    positionb = Position(position='Assistant Race Director', interest=localinterest, direct_access=[level])
    db.session.add_all([member, positiona, positionb])
    db.session.commit()

    return {
        'localinterest': localinterest, 'system': system, 'level': level, 'member': member,
        'positiona': positiona, 'positionb': positionb,
    }


def _hold(member, position, localinterest, startdate=date(2026, 1, 1), finishdate=None):
    up = UserPosition(user=member, position=position, interest=localinterest,
                       startdate=startdate, finishdate=finishdate)
    db.session.add(up)
    db.session.commit()
    return up


# ----------------------------------------------------------------------
# compute_required_access()
# ----------------------------------------------------------------------

def test_compute_required_access_empty_when_no_positions(accesssetup):
    assert compute_required_access(accesssetup['member']) == set()


def test_compute_required_access_includes_direct_access(accesssetup):
    member = accesssetup['member']
    _hold(member, accesssetup['positiona'], accesssetup['localinterest'])
    required = compute_required_access(member)
    assert required == {(accesssetup['system'].id, accesssetup['level'].id)}


def test_compute_required_access_includes_accesstype_access(accesssetup):
    member = accesssetup['member']
    localinterest = accesssetup['localinterest']
    system2 = System(name='Canva', interest=localinterest)
    level2 = SystemAccessLevel(system=system2, name='Access', interest=localinterest)
    accesstype = AccessType(name='Officer Bundle', interest=localinterest, access=[level2])
    position = Position(position='Officer', interest=localinterest, accesstypes=[accesstype])
    db.session.add_all([system2, level2, accesstype, position])
    db.session.commit()

    _hold(member, position, localinterest)
    required = compute_required_access(member)
    assert required == {(system2.id, level2.id)}


def test_compute_required_access_excludes_finished_position(accesssetup):
    member = accesssetup['member']
    _hold(member, accesssetup['positiona'], accesssetup['localinterest'],
          startdate=date(2020, 1, 1), finishdate=date(2020, 12, 31))
    assert compute_required_access(member, thisdate=date(2026, 1, 1)) == set()


# ----------------------------------------------------------------------
# sync_access_notices()
# ----------------------------------------------------------------------

def test_sync_creates_grant_notice_when_access_newly_required(accesssetup):
    member = accesssetup['member']
    localinterest = accesssetup['localinterest']
    before = compute_required_access(member)
    _hold(member, accesssetup['positiona'], localinterest)

    sync_access_notices(localinterest, member, before)

    notices = PositionAccessNotice.query.filter_by(user=member).all()
    assert len(notices) == 1
    assert notices[0].action == POSITIONACCESSNOTICE_ACTION_GRANT
    assert notices[0].system == accesssetup['system']
    assert notices[0].accesslevel == accesssetup['level']
    assert notices[0].resolved_at is None


def test_sync_creates_revoke_notice_when_access_no_longer_required(accesssetup):
    member = accesssetup['member']
    localinterest = accesssetup['localinterest']
    up = _hold(member, accesssetup['positiona'], localinterest)
    before = compute_required_access(member)

    up.finishdate = date(2026, 1, 15)
    db.session.commit()

    sync_access_notices(localinterest, member, before, effective_date=date(2026, 1, 16))

    notices = PositionAccessNotice.query.filter_by(user=member).all()
    assert len(notices) == 1
    assert notices[0].action == POSITIONACCESSNOTICE_ACTION_REVOKE


def test_sync_no_notice_when_access_still_covered_by_another_position(accesssetup):
    '''
    the case the issue calls out explicitly: losing one position shouldn't trigger a
    revoke reminder if another held position still requires the same access
    '''
    member = accesssetup['member']
    localinterest = accesssetup['localinterest']
    upa = _hold(member, accesssetup['positiona'], localinterest)
    _hold(member, accesssetup['positionb'], localinterest)
    before = compute_required_access(member)

    upa.finishdate = date(2026, 1, 15)
    db.session.commit()

    sync_access_notices(localinterest, member, before, effective_date=date(2026, 1, 16))

    assert PositionAccessNotice.query.filter_by(user=member).count() == 0


def test_sync_does_not_duplicate_unresolved_notice(accesssetup):
    member = accesssetup['member']
    localinterest = accesssetup['localinterest']
    before = compute_required_access(member)
    _hold(member, accesssetup['positiona'], localinterest)

    sync_access_notices(localinterest, member, before)
    # simulate a second, redundant call with the same before/after diff (e.g. the wizard
    # ran again before anyone resolved the first notice)
    sync_access_notices(localinterest, member, before)

    assert PositionAccessNotice.query.filter_by(user=member).count() == 1


def test_sync_clears_stale_opposite_notice_on_flip_back(accesssetup):
    member = accesssetup['member']
    localinterest = accesssetup['localinterest']
    up = _hold(member, accesssetup['positiona'], localinterest)
    before_revoke = compute_required_access(member)
    up.finishdate = date(2026, 1, 15)
    db.session.commit()
    sync_access_notices(localinterest, member, before_revoke, effective_date=date(2026, 1, 16))
    assert PositionAccessNotice.query.filter_by(
        user=member, action=POSITIONACCESSNOTICE_ACTION_REVOKE, resolved_at=None).count() == 1

    # access required again before anyone resolved the revoke notice
    before_grant = compute_required_access(member)
    up.finishdate = None
    db.session.commit()
    sync_access_notices(localinterest, member, before_grant, effective_date=date(2026, 2, 1))

    assert PositionAccessNotice.query.filter_by(
        user=member, action=POSITIONACCESSNOTICE_ACTION_REVOKE, resolved_at=None).count() == 0
    assert PositionAccessNotice.query.filter_by(
        user=member, action=POSITIONACCESSNOTICE_ACTION_GRANT, resolved_at=None).count() == 1


def test_sync_noop_when_before_equals_after(accesssetup):
    member = accesssetup['member']
    localinterest = accesssetup['localinterest']
    before = compute_required_access(member)

    sync_access_notices(localinterest, member, before)

    assert PositionAccessNotice.query.filter_by(user=member).count() == 0
