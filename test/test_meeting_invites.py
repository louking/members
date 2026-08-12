'''
test_meeting_invites - test members.meeting_invites
=========================================================
'''

# standard
from datetime import date

# pypi
import pytest
from flask import g

# homegrown
from members.meeting_invites import get_invites, ParameterError
from members.model import (
    db, LocalInterest, LocalUser, MeetingType, Meeting, Invite, Tag,
    INVITE_RESPONSE_ATTENDING, INVITE_RESPONSE_NO_RESPONSE,
)
from loutilities.user.model import Interest, User


@pytest.fixture
def invitesetup(bare_dbapp):
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
    tag = Tag(tag='invitees', description='invitees', interest=localinterest)
    tag.meetings.append(meeting)
    tag.users.append(member)
    db.session.add_all([meetingtype, meeting, tag])
    db.session.commit()

    return {'localinterest': localinterest, 'member': member, 'meeting': meeting}


def _request_ctx(bareapp, meeting):
    return bareapp.test_request_context(f'/?meeting_id={meeting.id}')


def test_get_invites_raises_for_missing_meeting(invitesetup, bareapp):
    with _request_ctx(bareapp, invitesetup['meeting']):
        g.interest = 'fsrc'
        with pytest.raises(ParameterError):
            get_invites(999999)


def test_get_invites_no_invite_yet_prompts_to_send(invitesetup, bareapp):
    meeting = invitesetup['meeting']
    with _request_ctx(bareapp, meeting):
        g.interest = 'fsrc'
        invitestates, invites = get_invites(meeting.id)
    assert invitestates == [{'name': 'Jane Doe', 'email': 'jane@example.com', 'state': 'send invitation'}]
    assert invites == [None]


def test_get_invites_pending_invite_shows_sent(invitesetup, bareapp):
    localinterest = invitesetup['localinterest']
    meeting = invitesetup['meeting']
    member = invitesetup['member']
    invite = Invite(interest=localinterest, meeting=meeting, user=member, invitekey='key1',
                    response=INVITE_RESPONSE_NO_RESPONSE, activeinvite=True)
    db.session.add(invite)
    db.session.commit()

    with _request_ctx(bareapp, meeting):
        g.interest = 'fsrc'
        invitestates, invites = get_invites(meeting.id)
    assert invitestates[0]['state'] == 'invitation sent'
    assert invites[0].id == invite.id


def test_get_invites_attending_response_shows_attending(invitesetup, bareapp):
    localinterest = invitesetup['localinterest']
    meeting = invitesetup['meeting']
    member = invitesetup['member']
    invite = Invite(interest=localinterest, meeting=meeting, user=member, invitekey='key1',
                    response=INVITE_RESPONSE_ATTENDING, activeinvite=True)
    db.session.add(invite)
    db.session.commit()

    with _request_ctx(bareapp, meeting):
        g.interest = 'fsrc'
        invitestates, invites = get_invites(meeting.id)
    assert invitestates[0]['state'] == 'attending'
