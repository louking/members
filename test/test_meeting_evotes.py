'''
test_meeting_evotes - test members.meeting_evotes
=========================================================
'''

# standard
from datetime import date

# pypi
import pytest
from flask import g

# homegrown
from members.meeting_evotes import get_evotes, ParameterError
from members.model import (
    db, LocalInterest, LocalUser, MeetingType, Meeting, Motion, MotionVote, Tag,
)
from loutilities.user.model import Interest, User


@pytest.fixture
def evotesetup(bare_dbapp):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()
    g.interest = 'fsrc'

    user = User(email='jane@example.com', name='Jane Doe', given_name='Jane', active=True,
               fs_uniquifier='u1')
    db.session.add(user)
    db.session.commit()
    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True,
                       interest=localinterest, user_id=user.id)
    db.session.add(member)
    db.session.commit()

    meetingtype = MeetingType(interest=localinterest, meetingtype='Board', options='',
                              meetingwording='meeting', statusreportwording='status report',
                              invitewording='invitation')
    meeting = Meeting(interest=localinterest, meetingtype=meetingtype, date=date(2026, 3, 10))
    motion = Motion(interest=localinterest, meeting=meeting, motion='approve budget')
    tag = Tag(tag='voters', description='voters', interest=localinterest)
    tag.meetingvotes.append(meeting)
    tag.users.append(member)
    motionvote = MotionVote(interest=localinterest, meeting=meeting, motion=motion, user=member,
                            vote=None, motionvotekey='key1')
    db.session.add_all([meetingtype, meeting, motion, tag, motionvote])
    db.session.commit()

    return {'localinterest': localinterest, 'member': member, 'meeting': meeting, 'motion': motion}


def test_get_evotes_raises_for_missing_motion(evotesetup):
    with pytest.raises(ParameterError):
        get_evotes(999999)


def test_get_evotes_returns_tagged_users_via_direct_tag(evotesetup):
    result = get_evotes(evotesetup['motion'].id)
    assert result == ['Jane Doe (jane@example.com)']


def test_get_evotes_includes_users_via_tagged_position(evotesetup):
    from members.model import Position, UserPosition
    localinterest = evotesetup['localinterest']
    motion = evotesetup['motion']
    meeting = evotesetup['meeting']

    user2 = User(email='john@example.com', name='John Smith', given_name='John', active=True,
                fs_uniquifier='u2')
    db.session.add(user2)
    db.session.commit()
    member2 = LocalUser(name='John Smith', email='john@example.com', active=True,
                        interest=localinterest, user_id=user2.id)
    position = Position(position='Treasurer', interest=localinterest)
    up = UserPosition(user=member2, position=position, interest=localinterest,
                      startdate=date(2026, 1, 1), finishdate=None)
    motionvote2 = MotionVote(interest=localinterest, meeting=meeting, motion=motion, user=member2,
                             vote=None, motionvotekey='key2')
    db.session.add_all([member2, position, up, motionvote2])
    db.session.commit()

    tag = Tag.query.filter_by(tag='voters').one()
    tag.positions.append(position)
    db.session.commit()

    result = get_evotes(motion.id)
    assert set(result) == {'Jane Doe (jane@example.com)', 'John Smith (john@example.com)'}
