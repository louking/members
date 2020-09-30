"""
reports - generate reports
====================================================================================
"""

# standard
from tempfile import TemporaryDirectory
from shutil import rmtree
from os.path import join as pathjoin

# pypi
from flask import current_app
from jinja2 import Environment
from slugify import slugify

# homegrown
from .model import Meeting, ActionItem, AgendaItem, DocTemplate
from .views.admin.viewhelpers import localinterest
from loutilities.googleauth import GoogleAuthService
from loutilities.nesteddict import obj2dict

# must match doc keys in meeting_gen_reports(), and names attrs in beforedatatables.js: meeting_generate_docs()
meeting_reports = ['agenda', 'status-report', 'minutes']
meeting_reports_premeeting = ['agenda', 'status-report']
meeting_report_attrs = ['gs_agenda', 'gs_status', 'gs_minutes']
meeting_report2attr = dict(zip(meeting_reports, meeting_report_attrs))

def meeting_agenda_context(meeting, actionitems, agendaitems):
    return {
        'meeting': obj2dict(meeting),
        'actionitems': [obj2dict(ai) for ai in actionitems],
        'agendaitems': [obj2dict(ai) for ai in agendaitems],
    }

def meeting_gen_reports(meeting_id, reports):
    """
    generate reports for a meeting

    :param meeting_id: Meeting.id
    :param reports: list of reports needed, subset of meeting_reports
    :return: list of reports generated
    """
    interest = localinterest()
    themeeting = Meeting.query.filter_by(id=meeting_id).one()
    actionitems = ActionItem.query.filter_by(interest=interest).filter(
        ActionItem.update_time >= themeeting.show_actions_since).all()
    for ai in actionitems:
        # pull in assignee due to lazy loading
        garbage = ai.assignee
    agendaitems = AgendaItem.query.filter_by(meeting_id=themeeting.id, is_hidden=False).order_by(AgendaItem.order).all()
    for ai in agendaitems:
        # pull in agendaheading due to lazy loading
        garbage = ai.agendaheading

    doc = {
        'agenda': {
            'contents': DocTemplate.query.filter_by(interest=interest, templatename='meeting-agenda-report').one().template,
            'docname': '{{ date }} {{ purpose }} Agenda',
            'context': meeting_agenda_context(themeeting, actionitems, agendaitems),
            'gs_fdr': interest.gs_agenda_fdr,
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
            doctemplate = reportenv.from_string(doc[thetype]['contents'])
            dochtml = doctemplate.render(doc[thetype]['context'])
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

