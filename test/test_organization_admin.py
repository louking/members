'''
test_organization_admin - test members.views.admin.organization_admin
=========================================================
'''

# standard
from datetime import date
from urllib.parse import urlencode

# pypi
import pytest
from flask import g

# homegrown
from members.views.admin import organization_admin
from members.views.admin.organization_admin import PositionWizardApi, PositionsPicker
from members.model import db, LocalInterest, LocalUser, Position, UserPosition
from loutilities.user.model import Interest
from loutilities.user.roles import ROLE_SUPER_ADMIN
from fakecurrentuser import FakeCurrentUser


@pytest.fixture
def positionsetup(bare_dbapp):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()
    g.interest = 'fsrc'

    position = Position(position='Treasurer', interest=localinterest)
    member1 = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=localinterest)
    member2 = LocalUser(name='John Smith', email='john@example.com', active=True, interest=localinterest)
    db.session.add_all([position, member1, member2])
    db.session.commit()

    return {'localinterest': localinterest, 'position': position, 'member1': member1, 'member2': member2}


def _grant(monkeypatch, roles=(ROLE_SUPER_ADMIN,)):
    monkeypatch.setattr(organization_admin, 'current_user', FakeCurrentUser(roles))


# ----------------------------------------------------------------------
# permission()
# ----------------------------------------------------------------------

def test_permission_false_without_position_id(positionsetup, monkeypatch):
    _grant(monkeypatch)
    assert PositionWizardApi().permission(False) is False


def test_permission_false_when_position_not_found(positionsetup, monkeypatch):
    _grant(monkeypatch)
    assert PositionWizardApi().permission(999999) is False


def test_permission_false_when_user_lacks_accepted_role(positionsetup, monkeypatch):
    _grant(monkeypatch, roles=())
    assert PositionWizardApi().permission(positionsetup['position'].id) is False


def test_permission_true_when_user_has_accepted_role(positionsetup, monkeypatch):
    _grant(monkeypatch)
    assert PositionWizardApi().permission(positionsetup['position'].id) is True


# ----------------------------------------------------------------------
# get()
# ----------------------------------------------------------------------

def _get_ctx(bareapp, **values):
    qs = urlencode({f'values[{k}]': v for k, v in values.items()})
    return bareapp.test_request_context(f'/?{qs}')


def test_get_denied_without_permission(positionsetup, bareapp, monkeypatch):
    _grant(monkeypatch, roles=())
    with _get_ctx(bareapp, position_id=positionsetup['position'].id):
        g.interest = 'fsrc'
        resp = PositionWizardApi().get()
    assert resp.json == {'error': 'operation not permitted for user'}


def test_get_no_effective_date_returns_empty_options(positionsetup, bareapp, monkeypatch):
    _grant(monkeypatch)
    with _get_ctx(bareapp, position_id=positionsetup['position'].id):
        g.interest = 'fsrc'
        resp = PositionWizardApi().get()
    assert resp.json == {'options': {'members': []}, 'values': {'members': [], 'qualifier': ''}}


def test_get_with_effective_date_returns_members_and_current_holder(positionsetup, bareapp, monkeypatch):
    localinterest = positionsetup['localinterest']
    position = positionsetup['position']
    member1 = positionsetup['member1']
    up = UserPosition(user=member1, position=position, interest=localinterest,
                      startdate=date(2026, 1, 1), finishdate=None, qualifier='interim')
    db.session.add(up)
    db.session.commit()

    _grant(monkeypatch)
    with _get_ctx(bareapp, position_id=position.id, effective='2026-03-10'):
        g.interest = 'fsrc'
        resp = PositionWizardApi().get()

    data = resp.json
    assert {'label': 'Jane Doe', 'value': member1.id} in data['options']['members']
    assert {'label': 'John Smith', 'value': positionsetup['member2'].id} in data['options']['members']
    assert data['values']['members'] == [member1.id]
    assert data['values']['qualifier'] == 'interim'


# ----------------------------------------------------------------------
# post()
# ----------------------------------------------------------------------

def _post_ctx(bareapp, position_id, effective, members='', qualifier=''):
    form = {
        'data[keyless][position_id]': str(position_id),
        'data[keyless][effective]': effective,
        'data[keyless][qualifier]': qualifier,
        'data[keyless][members]': members,
    }
    return bareapp.test_request_context('/', method='POST', data=form)


def test_post_denied_without_permission(positionsetup, bareapp, monkeypatch):
    _grant(monkeypatch, roles=())
    with _post_ctx(bareapp, positionsetup['position'].id, '2026-03-10'):
        g.interest = 'fsrc'
        resp = PositionWizardApi().post()
    assert resp.json == {'error': 'operation not permitted for user'}


def test_post_creates_new_userposition_for_empty_position(positionsetup, bareapp, monkeypatch):
    position = positionsetup['position']
    member1 = positionsetup['member1']

    _grant(monkeypatch)
    with _post_ctx(bareapp, position.id, '2026-03-10', members=str(member1.id)):
        g.interest = 'fsrc'
        resp = PositionWizardApi().post()

    assert resp.json == {'status': 'success'}
    ups = UserPosition.query.filter_by(position=position, user=member1).all()
    assert len(ups) == 1
    assert ups[0].startdate == date(2026, 3, 10)
    assert ups[0].finishdate is None


def test_post_replaces_current_holder_with_new_member(positionsetup, bareapp, monkeypatch):
    localinterest = positionsetup['localinterest']
    position = positionsetup['position']
    member1 = positionsetup['member1']
    member2 = positionsetup['member2']
    existing = UserPosition(user=member1, position=position, interest=localinterest,
                            startdate=date(2026, 1, 1), finishdate=None)
    db.session.add(existing)
    db.session.commit()

    _grant(monkeypatch)
    with _post_ctx(bareapp, position.id, '2026-06-01', members=str(member2.id)):
        g.interest = 'fsrc'
        resp = PositionWizardApi().post()

    assert resp.json == {'status': 'success'}
    db.session.refresh(existing)
    assert existing.finishdate == date(2026, 5, 31)
    new_ups = UserPosition.query.filter_by(position=position, user=member2).one()
    assert new_ups.startdate == date(2026, 6, 1)
    assert new_ups.finishdate is None


def test_post_overlap_detected_returns_error_without_crashing(positionsetup, bareapp, monkeypatch):
    localinterest = positionsetup['localinterest']
    position = positionsetup['position']
    member1 = positionsetup['member1']
    # data-error scenario: two overlapping active records for the same member/position
    up1 = UserPosition(user=member1, position=position, interest=localinterest,
                       startdate=date(2026, 1, 1), finishdate=None)
    up2 = UserPosition(user=member1, position=position, interest=localinterest,
                       startdate=date(2026, 2, 1), finishdate=None)
    db.session.add_all([up1, up2])
    db.session.commit()

    # the overlap error message links to admin.positiondates via page_url_for(), which needs
    # the endpoint registered to resolve -- bareapp has no blueprint routes, so register just
    # this one under the same endpoint name a full create_app() would use
    bareapp.add_url_rule('/<interest>/positiondates', endpoint='admin.positiondates', view_func=lambda **kw: '')

    _grant(monkeypatch)
    with _post_ctx(bareapp, position.id, '2026-03-10', members=str(member1.id)):
        g.interest = 'fsrc'
        resp = PositionWizardApi().post()

    assert 'error' in resp.json
    assert 'overlap' in resp.json['error']


# ----------------------------------------------------------------------
# PositionsPicker.options()
# ----------------------------------------------------------------------

def test_positionspicker_options_excludes_inactive_position(positionsetup, bareapp):
    inactive = Position(position='Retired Role', interest=positionsetup['localinterest'], is_active=False)
    db.session.add(inactive)
    db.session.commit()

    with bareapp.test_request_context('/'):
        g.interest = 'fsrc'
        options = PositionsPicker().options()

    labels = {o['label'] for o in options}
    assert labels == {'Treasurer'}
