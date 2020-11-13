"""
meeting_invites - support for meeting invitation management
====================================================================================
"""
# standard
from uuid import uuid4
from datetime import datetime

# pypi
from flask import g, render_template
from jinja2 import Template

# homegrown
from .model import db
from .model import Meeting, Invite, AgendaItem, ActionItem, EmailTemplate, Email
from .model import INVITE_RESPONSE_ATTENDING, ACTION_STATUS_CLOSED
from .views.admin.viewhelpers import localuser2user, localinterest
from loutilities.flask_helpers.mailer import sendmail
from loutilities.tables import page_url_for

class ParameterError(Exception): pass

MEETING_INVITE_EMAIL = 'meeting-invite-email'


def get_invites(meetingid):
    """
    get the invites for a specified meeting

    :param meetingid: Meeting.id
    :return: list(invitestates.values()), list(invites.values())
    """
    meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()

    if not meeting:
        raise ParameterError('meeting with id "{}" not found'.format(meetingid))

    def get_invite(meeting, localuser):
        """
        get invite for a specific meeting/user combination

        :param meeting: Meeting instance
        :param localuser: LocalUser instance
        :return: localuser.email, invitestate('attending, 'invited', 'send invitation'), Invite instance
        """
        user = localuser2user(localuser)
        email = user.email
        invitestate = {'name': user.name, 'email': email}
        invite = Invite.query.filter_by(interest=localinterest(), meeting=meeting, user=localuser).one_or_none()
        if invite:
            invitestate['state'] = 'attending' if invite.response == INVITE_RESPONSE_ATTENDING else 'invited'
        else:
            invitestate['state'] = 'send invitation'
        return email, invitestate, invite

    # send invitations to all those who are tagged like the meeting
    invitestates = {}
    invites = {}
    for tag in meeting.tags:
        for user in tag.users:
            email, invitestate, invite = get_invite(meeting, user)
            invitestates[email] = invitestate
            invites[email] = invite
        for position in tag.positions:
            for user in position.users:
                email, invitestate, invite = get_invite(meeting, user)
                # may be overwriting but that's ok
                invitestates[email] = invitestate
                invites[email] = invite

    # return the state values to simplify client work, also return the database records
    return list(invitestates.values()), list(invites.values())

def check_add_invite(meeting, localuser, agendaitem):
    """
    check if user invite needs to be added

    :param meeting: Meeting instance
    :param localuser: LocalUser instance
    :param agendaitem: AgendaItem instance for invite to be attached to
    :return: invite (may have been created)
    """
    invite = Invite.query.filter_by(interest=localinterest(), meeting=meeting, user=localuser).one_or_none()
    if not invite:
        # create unique key for invite - uuid4 gives unique key
        invitekey = uuid4().hex
        invite = Invite(
            interest=localinterest(),
            meeting=meeting,
            user=localuser,
            agendaitem=agendaitem,
            invitekey=invitekey,
            activeinvite=True,
            lastreminder=datetime.now(),
        )
        db.session.add(invite)
        db.session.flush()

        # get user's outstanding action items
        actionitems = ActionItem.query.filter_by(interest=localinterest(), assignee=localuser).\
            filter(ActionItem.status != ACTION_STATUS_CLOSED).all()

        # send email to user
        email = Email.query.filter_by(meeting=meeting, type=MEETING_INVITE_EMAIL).one()
        subject = email.subject

        fromlist = email.from_email

        rsvpurl = page_url_for('admin.memberstatusreport', interest=g.interest,
                               urlargs={'invitekey': invitekey},
                               _external=True)
        actionitemurl = page_url_for('admin.myactionitems', interest=g.interest, _external=True)

        context = {
            'meeting': meeting,
            'actionitems': actionitems,
            'rsvpurl': rsvpurl,
            'actionitemurl': actionitemurl,
            'message': email.message,
            'options': email.options,
        }
        html = render_template('meeting-invite-email.jinja2', **context)
        tolist = localuser.email
        cclist = None
        sendmail(subject, fromlist, tolist, html, ccaddr=cclist)

    invite.activeinvite = True
    return invite

def generateinvites(meetingid):
    """
    generate the invitations for a specified meeting; return the agendaitem if created

    :param meetingid: Meeting.id
    :return: AgendaItem
    """
    meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()

    if not meeting:
        raise ParameterError('meeting with id "{}" not found'.format(meetingid))

    # check if agendaitem already exists.
    agendaitem = AgendaItem.query.filter_by(interest=localinterest(), meeting=meeting, is_attendee_only=True).one_or_none()
    if not agendaitem:
        agendaitem = AgendaItem(interest=localinterest(), meeting=meeting, order=1, title='Attendees', agendaitem='',
                                is_attendee_only=True)
        db.session.add(agendaitem)

    # have there been any invites previous to this? used later to deactivate any invites which are not still needed
    # need to check now because check_add_invite may add additional invites
    previnvites = Invite.query.filter_by(interest=localinterest(), meeting=meeting).all()

    # send invitations to all those who are tagged like the meeting [invite] tags
    # track current invitations; make current invitations active
    currinvites = set()
    for tag in meeting.tags:
        for user in tag.users:
            thisinvite = check_add_invite(meeting, user, agendaitem)
            currinvites |= {thisinvite.id}
        for position in tag.positions:
            for user in position.users:
                thisinvite = check_add_invite(meeting, user, agendaitem)
                currinvites |= {thisinvite.id}

    # make invite inactive for anyone who was previously invited, but should not currently be invited
    for invite in previnvites:
        if invite.id not in currinvites:
            invite.activeinvite = False

    # this agendaitem will be added to the displayed table
    db.session.flush()
    return agendaitem

def generatereminder(meetingid, member, positions):
    """
    generate a meeting reminder email to the user

    :param meetingid: id of meeting
    :param member: member to remind
    :param positions: positions for which this reminder is about
    :return: False if new invite sent, True if reminder sent
    """
    # find member's invitation, if it exists
    invite = Invite.query.filter_by(meeting_id=meetingid, user=member).one_or_none()

    # invite already exists, send reminder
    if invite:
        # send reminder email to user
        emailtemplate = EmailTemplate.query.filter_by(templatename='meeting-reminder-email',
                                                      interest=localinterest()).one()

        subject = emailtemplate.subject
        fromlist = localinterest().from_email
        if emailtemplate.from_email:
            fromlist = emailtemplate.from_email
        tolist = member.email
        cclist = None

        # get user's outstanding action items
        actionitems = ActionItem.query.filter_by(interest=localinterest(), assignee=member). \
            filter(ActionItem.status != ACTION_STATUS_CLOSED).all()

        # set up urls for email
        rsvpurl = page_url_for('admin.memberstatusreport', interest=g.interest,
                               urlargs={'invitekey': invite.invitekey},
                               _external=True)
        actionitemurl = page_url_for('admin.myactionitems', interest=g.interest, _external=True)

        # filter positions to those which affect this member
        memberpositions = [p for p in positions if p in member.positions]

        # create and send email
        template = Template(emailtemplate.template)
        context = {
            'meeting': invite.meeting,
            'actionitems': actionitems,
            'rsvpurl': rsvpurl,
            'actionitemurl': actionitemurl,
            'positions': memberpositions,
        }
        html = template.render(**context)

        sendmail(subject, fromlist, tolist, html, ccaddr=cclist)
        invite.lastreminder = datetime.now()
        reminder = True

    # invite doesn't exist yet, create and send invite
    else:
        meeting = Meeting.query.filter_by(id=meetingid).one()
        anyinvite = Invite.query.filter_by(interest=localinterest(), meeting=meeting).first()
        check_add_invite(meeting, member, anyinvite.agendaitem)
        reminder = False

    return reminder

def send_meeting_email(meetingid, subject, message):
    """
    send email to meeting invitees

    :param meetingid: id of meeting
    :param subject: subject for message
    :param message: message in html format
    :return: list of addresses email was sent to
    """
    meeting_id = meetingid
    invites = Invite.query.filter_by(meeting_id=meeting_id).all()

    tolist = ['{} <{}>'.format(i.user.name, i.user.email) for i in invites]

    # use from address configured for meeting invite email if available, else use interest attribute
    emailtemplate = EmailTemplate.query.filter_by(templatename='meeting-invite-email', interest=localinterest()).one()
    fromaddr = localinterest().from_email
    if emailtemplate.from_email:
        fromaddr = emailtemplate.from_email

    result = sendmail(subject, fromaddr, tolist, message)

    return tolist