"""
meeting_cli - background tasks needed for meeting management
"""

# standard
from re import match
from datetime import date, timedelta, datetime

# pypi
from flask import g
from flask.cli import with_appcontext
from click import argument, group

# homegrown
from scripts import catch_errors, ParameterError
from members.model import db, Meeting, Invite, StatusReport, DiscussionItem, localinterest_query_params
from members.meeting_invites import generateinvites
from members.reports import meeting_gen_reports, meeting_reports_nightly, meeting_reports_status, meeting_report2attr
from loutilities.timeu import asctime


# set up datatabase date formatter
dbdate = asctime('%Y-%m-%d')

# debug
debug = False

# needs to be before any commands
@group()
def meetings():
    """Perform meeting module tasks"""
    pass

def getstartenddates(startdate, enddate, endwindow):
    """
    calculate start and end date window from arguments

    :param startdate: startdate argument or auto
    :param enddate: enddate argument or auto
    :param endwindow: if enddate = auto, number of days it should be from startdate
    :return: start, end
    """
    if startdate == 'auto' and enddate == 'auto':
        # calculate start and end date window
        start = dbdate.dt2asc(date.today())
        end = dbdate.dt2asc(date.today() + timedelta(endwindow))

    # verify both dates are present, check user input format is yyyy-mm-dd
    else:
        if startdate == 'auto' or enddate == 'auto':
            print('ERROR: startdate and enddate must both be specified')
            return

        if (not match(r'^(19[0-9]{2}|2[0-9]{3})-(0[1-9]|1[012])-([123]0|[012][1-9]|31)$', startdate) or
                not match(r'^(19[0-9]{2}|2[0-9]{3})-(0[1-9]|1[012])-([123]0|[012][1-9]|31)$', enddate)):
            raise ParameterError('ERROR: startdate and enddate must be in yyyy-mm-dd format')

        # cli specified dates format is fine, and both dates specified
        start = startdate
        end = enddate

    return start, end

def getstartdate(startdate):
    """
    calculate start from arguments

    :param startdate: startdate argument or auto
    :return: start
    """
    if startdate == 'auto':
        # calculate start and end date window
        start = dbdate.dt2asc(date.today())

    # verify both dates are present, check user input format is yyyy-mm-dd
    else:
        if (not match(r'^(19[0-9]{2}|2[0-9]{3})-(0[1-9]|1[012])-([123]0|[012][1-9]|31)$', startdate)):
            raise ParameterError('ERROR: startdate must be in yyyy-mm-dd format')

        # cli specified date format is fine
        start = startdate

    return start

@meetings.command()
@argument('interest')
@argument('startdate', default='auto')
@with_appcontext
@catch_errors
def updateinvites(interest, startdate):
    """
    for all future meetings, if invites have been sent, update the invite list as appropriate
    """
    # calculate start date
    start = getstartdate(startdate)

    # set local interest
    g.interest = interest

    # for all the meetings after or equal to start, generate invites, but only if there were already invitations sent
    themeetings = Meeting.query.filter_by(**localinterest_query_params()).filter(Meeting.date >= start).all()
    for meeting in themeetings:
        invitequery = localinterest_query_params()
        invitequery['meeting'] = meeting
        invites = Invite.query.filter_by(**invitequery).all()
        if len(invites) > 0:
            generateinvites(meeting.id)
            # commit after each meeting to save new invitations
            db.session.commit()

@meetings.command()
@argument('interest')
@argument('startdate', default='auto')
@with_appcontext
@catch_errors
def nightlyreports(interest, startdate):
    """
    for all future meetings, regenerate reports
    """
    # calculate start date
    start = getstartdate(startdate)

    # set local interest
    g.interest = interest

    # for all the meetings after or equal to start, generate reports, but only if the report has been previously generated
    futuremeetings = Meeting.query.filter_by(**localinterest_query_params()).filter(Meeting.date >= start).all()
    for meeting in futuremeetings:

        # determine which reports have been generated already
        # we're only regenerating reports which happen nightly
        reports = []
        for report in meeting_reports_nightly:
            if getattr(meeting, meeting_report2attr[report]):
                reports.append(report)

        if reports:
            reportsgenned = meeting_gen_reports(meeting.id, reports)

        # this actually shouldn't be required, but shouldn't hurt
        db.session.commit()

@meetings.command()
@argument('interest')
@argument('startdate', default='auto')
@with_appcontext
@catch_errors
def continuousreports(interest, startdate):
    """
    for up to the minute reports (status report), (re)generate reports if needed
    """
    # calculate start date
    start = getstartdate(startdate)

    # set local interest
    g.interest = interest

    # for all the meetings after or equal to start, generate reports
    futuremeetings = Meeting.query.filter_by(**localinterest_query_params()).filter(Meeting.date >= start).all()
    for meeting in futuremeetings:

        # we're (re)generating reports which happen continuously
        # but we may not need to, so that's the default unless proven otherwise
        reports = []

        # if report has been generated, regenerate if any status reports or discussion items have been updated
        # since the last time the report was generated
        if meeting.last_status_gen:
            statussince = StatusReport.query.filter(StatusReport.update_time >= meeting.last_status_gen).all()
            discusssince = DiscussionItem.query.filter(DiscussionItem.update_time >= meeting.last_status_gen).all()
            if statussince or discusssince:
                reports = [meeting_reports_status]

        # else no report generated yet, so generate for the first time
        else:
            reports = [meeting_reports_status]

        if reports:
            reportsgenned = meeting_gen_reports(meeting.id, reports)
            meeting.last_status_gen = datetime.now()

        # we may have updated meeting
        db.session.commit()

