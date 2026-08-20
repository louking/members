'''
test_viewhelpers - test members.views.admin.viewhelpers
=========================================================
'''

# standard
from datetime import date

# pypi
import pytest

# homegrown
from members.views.admin.viewhelpers import get_tags_positions, _positions_active_from_preloaded
from members.model import db, LocalInterest, LocalUser, Position, Tag, UserPosition


@pytest.fixture
def tagpositionsetup(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    tag = Tag(tag='board', description='board members', interest=interest)
    tag.positions.append(position)
    db.session.add_all([interest, position, tag])
    db.session.commit()
    return {'interest': interest, 'position': position, 'tag': tag}


def test_get_tags_positions_includes_active_position(tagpositionsetup):
    position = tagpositionsetup['position']
    tag = tagpositionsetup['tag']
    assert get_tags_positions([tag]) == {position}


def test_get_tags_positions_excludes_inactive_position(tagpositionsetup):
    position = tagpositionsetup['position']
    tag = tagpositionsetup['tag']
    position.is_active = False
    assert get_tags_positions([tag]) == set()


def test_positions_active_from_preloaded_excludes_inactive_position(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest, is_active=False)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    up = UserPosition(user=member, position=position, interest=interest,
                      startdate=date(2026, 1, 1), finishdate=None)
    db.session.add_all([interest, position, member, up])
    db.session.commit()

    up_by_user = {member.id: [up]}
    assert _positions_active_from_preloaded(member, '2026-03-10', up_by_user) == []


def test_positions_active_from_preloaded_includes_active_position(bare_dbapp):
    interest = LocalInterest(interest_id=1)
    position = Position(position='Treasurer', interest=interest)
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=interest)
    up = UserPosition(user=member, position=position, interest=interest,
                      startdate=date(2026, 1, 1), finishdate=None)
    db.session.add_all([interest, position, member, up])
    db.session.commit()

    up_by_user = {member.id: [up]}
    assert _positions_active_from_preloaded(member, '2026-03-10', up_by_user) == [position]
