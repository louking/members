"""
meeting_evotes - support for meeting motion evote management
====================================================================================
"""
# pypi
from flask import render_template, g

# homegrown
from .model import Motion, MotionVote
from .views.admin.viewhelpers import localuser2user, localinterest
from .helpers import members_active
from loutilities.tables import page_url_for
from loutilities.flask_helpers.mailer import sendmail

class ParameterError(Exception): pass

def send_evote_req(motion, localuser, from_addr, subject, message):
    """
    send user evote request

    :param motion: Motion instance
    :param localuser: LocalUser instance
    :param from_addr: from address for email
    :param subject: subject for email
    :param message: message for email
    :return: MotionVote instance
    """
    evote = MotionVote.query.filter_by(interest=localinterest(), motion=motion, user=localuser).one_or_none()
    if not evote:
        raise ParameterError('motion vote for motion {}, user {} not found'.format(motion.id, localuser.email))

    evoteurl = page_url_for('admin.motionvote', interest=g.interest,
                           urlargs={'motionvotekey': evote.motionvotekey},
                           _external=True)

    context = {
        'motion': motion,
        'meeting': motion.meeting,
        'evoteurl': evoteurl,
        'message': message,
    }

    html = render_template('motion-evote-email.jinja2', **context)
    tolist = localuser.email
    cclist = None
    sendmail(subject, from_addr, tolist, html, ccaddr=cclist)

    return evote

def get_evotes(motionid):
    """
    get the evotes for a specified motion

    :param motionid: Motion.id
    :return: list(evotes.values())
    """
    motion = Motion.query.filter_by(id=motionid, interest_id=localinterest().id).one_or_none()

    if not motion:
        raise ParameterError('motion with id "{}" not found'.format(motionid))

    def get_evote(motion, localuser):
        """
        get evote for a specific motion/user combination

        :param motion: Motion instance
        :param localuser: LocalUser instance
        :return: localuser.email, MotionVote instance
        """
        user = localuser2user(localuser)
        email = user.email
        evote = MotionVote.query.filter_by(interest=localinterest(), motion=motion, user=localuser).one()
        if not evote:
            raise ParameterError('motion vote for motion {}, user {} not found'.format(motionid, email))
        return email, evote

    # send evotes to all those who are tagged like the meeting's vote tag(s)
    evotes = {}
    for tag in motion.meeting.votetags:
        for member in tag.users:
            email, evote = get_evote(motion, member)
            evotes[email] = '{} ({})'.format(member.name, member.email)
        for position in tag.positions:
            for member in members_active(position, motion.meeting.date):
                email, evote = get_evote(motion, member)
                # may be overwriting but that's ok
                evotes[email] = '{} ({})'.format(member.name, member.email)

    # return the state values to simplify client work, also return the database records
    return list(evotes.values())

def generateevotes(motionid, from_addr, subject, message):
    """
    generate the evote requests for a specified motion

    :param motionid: Motion.id
    :param from_addr: from address for email
    :param subject: subject for email
    :param message: message for email
    """
    motion = Motion.query.filter_by(id=motionid, interest_id=localinterest().id).one_or_none()

    if not motion:
        raise ParameterError('motion with id "{}" not found'.format(motionid))

    # send evote requests to all those who are tagged like the meeting voting tags
    currevotes = set()
    members = set()
    for tag in motion.meeting.votetags:
        for member in tag.users:
            members |= {member}
        for position in tag.positions:
            for member in members_active(position, motion.meeting.date):
                members |= {member}
    for member in members:
        thisevote = send_evote_req(motion, member, from_addr, subject, message)
        currevotes |= {thisevote.id}
