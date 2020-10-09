"""
reports - generate reports
====================================================================================
"""

# standard
from tempfile import TemporaryDirectory
from shutil import rmtree
from os.path import join as pathjoin
from copy import copy

# pypi
from flask import current_app
from jinja2 import Environment
from slugify import slugify
from dominate.tags import p

# homegrown
from .model import Meeting, ActionItem, AgendaItem, StatusReport, Position, DiscussionItem, MemberStatusReport
from .model import Motion, MotionVote, motionvote_all, MOTIONVOTE_STATUS_NOVOTE, Invite
from .views.admin.viewhelpers import localinterest
from loutilities.googleauth import GoogleAuthService
from loutilities.nesteddict import obj2dict

# must match doc keys in meeting_gen_reports(), and names attrs in beforedatatables.js: meeting_generate_docs()
meeting_reports = ['agenda', 'status-report', 'minutes']
meeting_reports_premeeting = ['agenda', 'status-report']
meeting_report_attrs = ['gs_agenda', 'gs_status', 'gs_minutes']
meeting_report2attr = dict(zip(meeting_reports, meeting_report_attrs))

def meeting_gen_reports(meeting_id, reports):
    """
    generate reports for a meeting

    :param meeting_id: Meeting.id
    :param reports: list of reports needed, subset of meeting_reports
    :return: list of reports generated
    """

    interest = localinterest()
    themeeting = Meeting.query.filter_by(id=meeting_id).one()

    def meeting_agenda_context():
        actionitems = ActionItem.query.filter_by(interest=interest).filter(
            ActionItem.update_time >= themeeting.show_actions_since).all()
        for ai in actionitems:
            # pull in assignee due to lazy loading
            garbage = ai.assignee
        agendaitems = AgendaItem.query.filter_by(meeting_id=themeeting.id, is_hidden=False).order_by(
            AgendaItem.order).all()
        for ai in agendaitems:
            # pull in agendaheading due to lazy loading
            garbage = ai.agendaheading

        return {
            'meeting': obj2dict(themeeting),
            'actionitems': [obj2dict(ai) for ai in actionitems],
            'agendaitems': [obj2dict(ai) for ai in agendaitems],
        }

    def meeting_statusreport_context():
        # get all the status reports and discussion items written to date, and positions in alphabetical order
        statusreports = StatusReport.query.filter_by(meeting_id=themeeting.id).all()
        discussions = DiscussionItem.query.filter_by(meeting_id=themeeting.id).all()
        # need to pull in discussion agenda item due to lazy loading
        for discussion in discussions:
            garbage = discussion.agendaitem
        positions = Position.query.filter_by(interest=interest, has_status_report=True).order_by(Position.position).all()

        # this is a little klunky, but we need to weed out any RSVP status reports
        rsvp_statusreport_ids = [m.content.id
                                 for m in MemberStatusReport.query.filter_by(meeting_id=themeeting.id, is_rsvp=True).all()]
        statusreports = [sr for sr in statusreports if sr.id not in rsvp_statusreport_ids]

        # associate status reports to a position. remaining are not in srhandled
        pos2sr = {}
        srhandled = []
        for sr in statusreports:
            if sr.position:
                pos2sr[sr.position_id] = sr
                srhandled.append(sr)

        # associate discussion items to status reports
        sr2di = {}
        for di in discussions:
            sr2di.setdefault(di.statusreport.id, [])
            sr2di[di.statusreport.id].append(di)

        # finally we can determine the context
        context = {'meeting': obj2dict(themeeting), 'reports': []}
        for position in positions:
            # if the position has an agenda heading configured, use that for the title, else use the name of the position
            heading = position.agendaheading.heading if position.agendaheading else position.position

            sr = pos2sr.get(position.id, None)

            # default status report if none found or none within status report record
            status = p('No status report submitted').render()

            # status report record for position found
            if sr:
                # normally there was a status report in the status report record, else we'll use the default
                if sr.statusreport:
                    status = sr.statusreport
                report = {
                    'title': '{} - {}'.format(heading, ', '.join([u.name for u in position.users])),
                    'statusreport': status,
                    'discussions': [obj2dict(d) for d in discussions if d.statusreport_id == sr.id]
                }

            # status report for position not found
            else:
                report = {
                    'title': '{} - {}'.format(heading, ', '.join([u.name for u in position.users])),
                    'statusreport': status,
                }

            context['reports'].append(report)

        # sort reports by heading (title)
        context['reports'] = sorted(context['reports'], key=lambda item: item['title'])

        # remove all the status reports which are handled by position, leaving only "unpositioned" status reports
        for sr in srhandled:
            statusreports.remove(sr)

        # sort additional status reports by title
        statusreports = sorted(statusreports, key=lambda item: item.title)

        # add remaining status reports, which weren't by position, and which have content
        for sr in statusreports:
            # not quite sure how this can happen, but during development saw RSVPs which were unattached to MemberStatusReport
            # in any case, seems safe to skip status reports which have no content
            if not sr.statusreport and not sr.discussionitems:
                continue

            report = {
                'title': sr.title,
                'statusreport': obj2dict(sr.statusreport),
                'discussions': [obj2dict(d) for d in discussions if d.statusreport_id == sr.id]
            }
            context['reports'].append(report)

        return context

    def meeting_minutes_context():
        # create action item data structures,
        # including summary (actionitems) and mapping from agenda item to action item (agenda2action)
        dbactionitems = ActionItem.query.filter_by(interest=interest).filter(
            ActionItem.update_time >= themeeting.show_actions_since).all()
        actionitems = []
        agenda2action = {}
        for dbactionitem in dbactionitems:
            actionitem = {}
            for field in ['agendaitem_id', 'action', 'status', 'comments']:
                actionitem[field] = getattr(dbactionitem, field)
            actionitem['assignee'] = dbactionitem.assignee.name
            actionitems.append(actionitem)
            agendaitem_id = dbactionitem.agendaitem_id
            agenda2action.setdefault(agendaitem_id, [])
            agenda2action[agendaitem_id].append(actionitem)

        # create motion data structures,
        # including summary (motions) and mapping from agenda item to motion (agenda2motion)
        dbmotions = Motion.query.filter_by(meeting_id=themeeting.id).all()
        motions = []
        agenda2motion = {}
        ## show all but novote, which means the person wasn't at the meeting during the vote
        ## don't remove novote from the master copy, though
        motionvoteshow = copy(motionvote_all)
        motionvoteshow.remove(MOTIONVOTE_STATUS_NOVOTE)
        for dbmotion in dbmotions:
            motion = {}
            for field in ['agendaitem_id', 'motion', 'status', 'comments']:
                motion[field] = getattr(dbmotion, field)
            # use motionvotes_all for order to display
            motion['mover'] = dbmotion.mover.name if dbmotion.mover else None
            motion['seconder'] = dbmotion.seconder.name if dbmotion.seconder else None
            motion['votes'] = []
            for mv in motionvoteshow:
                votes = [{'member': v.user.name, 'vote': v.vote}
                         for v in MotionVote.query.filter_by(motion_id=dbmotion.id, vote=mv).all()]
                votes.sort(key=lambda item: item['member'])
                motion['votes'] += votes
            motions.append(motion)
            agendaitem_id = dbmotion.agendaitem_id
            agenda2motion.setdefault(agendaitem_id, [])
            agenda2motion[agendaitem_id].append(motion)

        # create agenda item data structure
        dbagendaitems = AgendaItem.query.filter_by(
            meeting_id=themeeting.id,
            is_hidden=False,
            is_attendee_only=False,
            is_action_only=False
        ).order_by(AgendaItem.order).all()
        rawagendaitems = []
        for dbagendaitem in dbagendaitems:
            agendaitem = {}
            for field in ['id', 'title', 'agendaitem', 'discussion']:
                agendaitem[field] = getattr(dbagendaitem, field)
            agendaitem['heading'] = dbagendaitem.agendaheading.heading if dbagendaitem.agendaheading else None
            if dbagendaitem.id in agenda2action:
                agendaitem['actionitems'] = agenda2action[dbagendaitem.id]
            if dbagendaitem.id in agenda2motion:
                agendaitem['motions'] = agenda2motion[dbagendaitem.id]
            rawagendaitems.append(agendaitem)
        # postprocess raw agenda items to insert headings
        agendaitems = []
        iteritems = iter(rawagendaitems)
        item = next(iteritems)
        heading = item.pop('heading')
        try:
            while True:
                if not heading:
                    agendaitems.append(item)
                    item = next(iteritems)
                    heading = item.pop('heading')
                else:
                    currheading = heading
                    subitem = {'heading': heading, 'agendaitems': []}
                    agendaitems.append(subitem)
                    while heading == currheading:
                        subitem['agendaitems'].append(item)
                        item = next(iteritems)
                        heading = item.pop('heading')
        except StopIteration:
            pass

        # create attendees data structure
        dbattendees = Invite.query.filter_by(meeting_id=themeeting.id, attended=True).all()
        attendees = []
        for dbattendee in dbattendees:
            # can this attendee vote?
            voting = False
            for vt in themeeting.votetags:
                # if any of the user positions are a votetag position
                if set(dbattendee.user.positions) & set(vt.positions):
                    voting = True
                    break
            attendee = {
                'member': dbattendee.user.name,
                'positions': [p.position for p in dbattendee.user.positions],
                'voting': voting
            }
            attendees.append(attendee)


        context = {
            'meeting': obj2dict(themeeting),
            'attendees': attendees,
            'actionitems': actionitems,
            'agendaitems': agendaitems,
            'motions': motions,
        }

        # maybe attendee agenda item has additional information, if so include that in the context
        if dbattendees:
            attendee_agendaitem = dbattendees[0].agendaitem
            attendeeaddl = ''
            if attendee_agendaitem.agendaitem:
                attendeeaddl += attendee_agendaitem.agendaitem
            if attendee_agendaitem.discussion:
                attendeeaddl += attendee_agendaitem.discussion
            if attendeeaddl:
                context['attendeeaddl'] = attendeeaddl

        return context


    doc = {
        'agenda': {
            'contents': 'meeting-agenda-report.jinja2',
            'docname': '{{ date }} {{ purpose }} Agenda',
            'context': meeting_agenda_context,
            'gs_fdr': interest.gs_agenda_fdr,
        },
        'status-report': {
            'contents': 'meeting-status-report.jinja2',
            'docname': '{{ date }} {{ purpose }} Status Report',
            'context': meeting_statusreport_context,
            'gs_fdr': interest.gs_status_fdr,
        },
        'minutes': {
            'contents': 'meeting-minutes-report.jinja2',
            'docname': '{{ date }} {{ purpose }} Minutes',
            'context': meeting_minutes_context,
            'gs_fdr': interest.gs_minutes_fdr,
        }

    }

    # todo: #244 work to do if g suite not being used, but this is good enough for initial service launch
    # if using g suite, create GoogleAuthService instance
    usegsuite = False
    for thetype in reports:
        if doc[thetype]['gs_fdr']:
            usegsuite = True
            break
    if usegsuite:
        gs = GoogleAuthService(current_app.config['GSUITE_SERVICE_KEY_FILE'], current_app.config['GSUITE_SCOPES'])

    tmpdir = TemporaryDirectory(prefix='mbr')
    reportenv = Environment(loader=current_app.jinja_loader)
    for thetype in reports:
        nametemplate = reportenv.from_string(doc[thetype]['docname'])
        docname = nametemplate.render(obj2dict(themeeting))
        docpath = pathjoin(tmpdir.name, '{}.html'.format(slugify(docname)))
        with open(docpath, 'w') as docfp:
            doctemplate = reportenv.get_template(doc[thetype]['contents'])
            context = doc[thetype]['context']()
            dochtml = doctemplate.render(context)
            docfp.write(dochtml)

        # create gsuite file if it hasn't been created, else update it
        fileidattr = meeting_report2attr[thetype]
        fileid = getattr(themeeting, fileidattr)
        folder = doc[thetype]['gs_fdr']
        if not getattr(themeeting, fileidattr):
            fileid = gs.create_file(folder, docname, docpath, doctype='html')
            setattr(themeeting, fileidattr, fileid)
        else:
            gs.update_file(fileid, docpath, filename=docname, doctype='html')

    # tmpdir and contents are deleted
    try:
        rmtree(tmpdir.name)
    except:
        pass

