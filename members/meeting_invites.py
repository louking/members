"""
meeting_invites - support for meeting invitation management
====================================================================================
"""
# standard
from uuid import uuid4

# pypi
from flask import g
from jinja2 import Template

# homegrown
from .model import db
from .model import Meeting, Invite, AgendaItem, ActionItem, EmailTemplate
from .model import INVITE_RESPONSE_ATTENDING, ACTION_STATUS_CLOSED
from .views.admin.viewhelpers import localuser2user, localinterest
from loutilities.flask_helpers.mailer import sendmail
from loutilities.tables import page_url_for

class ParameterError(Exception): pass


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

def generateinvites(meetingid):
    """
    generate the invitations for a specified meeting; return the agendaitem if created

    :param meetingid: Meeting.id
    :return: AgendaItem
    """
    meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()

    if not meeting:
        raise ParameterError('meeting with id "{}" not found'.format(meetingid))

    # check if agendaitem already exists. If any invites to the meeting there should already be the agenda item
    # also use this later to deactivate any invites which are not still needed
    previnvites = Invite.query.filter_by(interest=localinterest(), meeting=meeting).all()
    if not previnvites:
        agendaitem = AgendaItem(interest=localinterest(), meeting=meeting, order=1, title='Attendees', agendaitem='',
                                is_attendee_only=True)
        db.session.add(agendaitem)
    # all of the invites should have the same agendaitem, so just use the first
    else:
        agendaitem = previnvites[0].agendaitem

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
            )
            db.session.add(invite)

            # get user's outstanding action items
            actionitems = ActionItem.query.filter_by(interest=localinterest(), assignee=localuser).\
                filter(ActionItem.status != ACTION_STATUS_CLOSED).all()

            # send email to user
            emailtemplate = EmailTemplate.query.filter_by(templatename='meeting-invite-email',
                                                          interest=localinterest()).one()
            template = Template(emailtemplate.template)
            subject = emailtemplate.subject

            rsvpurl = page_url_for('admin.memberstatusreport', interest=g.interest,
                                   urlargs={'invitekey': invitekey},
                                   _external=True)
            actionitemurl = page_url_for('admin.actionitems', interest=g.interest,
                                   urlargs={'member_id': localuser2user(localuser).id},
                                   _external=True)
            context = {
                'meeting': meeting,
                'actionitems': actionitems,
                'rsvpurl': rsvpurl,
                'actionitemurl': actionitemurl
            }
            html = template.render(**context)
            tolist = localuser.email
            fromlist = localinterest().from_email
            cclist = None
            sendmail(subject, fromlist, tolist, html, ccaddr=cclist)

        invite.activeinvite = True
        return invite

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

