"""
meetings_admin - administrative task handling for meetings admin
====================================================================================
"""
# standard
from datetime import datetime, date
from traceback import format_exception_only, format_exc
from uuid import uuid4

# pypi
from flask import g, request, jsonify, current_app, url_for
from flask.views import MethodView
from flask_security import current_user
from dominate.tags import h1, div, label, input, select, option, script, dd, p, b
from dominate.util import text, raw
from sqlalchemy import func
from sqlalchemy.orm import aliased
from loutilities.nesteddict import obj2dict
from jinja2 import Environment

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Tag, MeetingType
from ...model import Meeting, Invite, AgendaItem, Motion, MotionVote, AgendaHeading, Position, StatusReport
from ...model import Email
from ...model import localinterest_query_params
from ...model import invite_response_all
from ...model import MOTIONVOTE_STATUS_APPROVED, MOTIONVOTE_STATUS_NOVOTE
from ...helpers import positions_active, members_active
from ...meeting_invites import generateinvites, get_invites, generatereminder, send_meeting_email, send_discuss_email
from ...meeting_invites import MEETING_INVITE_EMAIL, MEETING_REMINDER_EMAIL, MEETING_EMAIL
from ...model import MEETING_OPTIONS, MEETING_OPTION_SEPARATOR, MEETING_OPTION_RSVP, MEETING_OPTION_ONLINEMOTIONS
from ...model import MEETING_OPTION_SHOWACTIONITEMS, MEETING_OPTION_TIME, MEETING_OPTION_LOCATION
from .meetings_common import MemberStatusReportBase, ActionItemsBase, MotionVotesBase, MotionsBase
from .meetings_common import motions_childelementargs, adminguide
from .meetings_common import custom_meeting, custom_invitation, custom_invitations, custom_statusreport, invite_statusreport
from .meetings_common import meeting_has_option, meeting_has_button
from .viewhelpers import dtrender, localinterest, localuser2user, user2localuser, get_tags_users, get_tags_positions
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption
from members.reports import meeting_gen_reports, meeting_reports

from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.tables import _editormethod, get_request_data, rest_url_for, CHILDROW_TYPE_TABLE

from loutilities.timeu import asctime
isodate = asctime('%Y-%m-%d')

class ParameterError(Exception): pass

debug = False


##########################################################################################
# meetings endpoint
###########################################################################################

meetings_dbattrs = 'id,interest_id,date,purpose,show_actions_since,tags,votetags,statusreporttags,' \
                   'time,location,meetingtype,gs_agenda,gs_status,gs_minutes,organizer,meetingtype.statusreportwording'.split(',')
meetings_formfields = 'rowid,interest_id,date,purpose,show_actions_since,tags,votetags,statusreporttags,' \
                      'time,location,meetingtype,gs_agenda,gs_status,gs_minutes,organizer,statusreportwording'.split(',')
meetings_dbmapping = dict(zip(meetings_dbattrs, meetings_formfields))
meetings_formmapping = dict(zip(meetings_formfields, meetings_dbattrs))
meetings_dbmapping['date'] = lambda formrow: dtrender.asc2dt(formrow['date'])
meetings_formmapping['date'] = lambda dbrow: dtrender.dt2asc(dbrow.date)
meetings_dbmapping['show_actions_since'] = lambda formrow: dtrender.asc2dt(formrow['show_actions_since']) if formrow['show_actions_since'] else None
meetings_formmapping['show_actions_since'] = lambda dbrow: dtrender.dt2asc(dbrow.show_actions_since) if dbrow.show_actions_since else ''

def meetingcreatefieldvals():
    interest = localinterest()
    return {
        'tags.id': [t.id for t in interest.interestmeetingtags],
        'votetags.id': [t.id for t in interest.interestmeetingvotetags],
        'organizer.id': user2localuser(current_user).id
    }

class MeetingsView(DbCrudApiInterestsRolePermissions):
    def createrow(self, formdata):
        """
        create the meeting, adding an agenda item for outstanding action items

        :param formdata: form from user
        :return: output for create row response
        """
        output = super().createrow(formdata)
        themeeting = Meeting.query.filter_by(id=self.created_id).one()

        # special processing for action items agenda
        if meeting_has_option(themeeting, MEETING_OPTION_SHOWACTIONITEMS):
            agendaitem = AgendaItem(interest=localinterest(), meeting=themeeting, order=2, title='Action Items', agendaitem='',
                                    is_action_only=True)
            db.session.add(agendaitem)

        # special processing if autoagendatitle is specified, run the template engine to do any translation
        if themeeting.meetingtype.autoagendatitle:
            garbage = themeeting.meetingtype # because of lazy loading
            meetingdict = obj2dict(themeeting)
            agitemtemp = Environment().from_string(themeeting.meetingtype.autoagendatitle)
            agendatitle = agitemtemp.render(meetingdict)
            agendaitem = AgendaItem(interest=localinterest(), meeting=themeeting, order=3, title=agendatitle, agendaitem='',
                                    is_action_only=False)
            db.session.add(agendaitem)

        return output

def meetings_validate(action, formdata):
    results = []

    # need meetingtype to determine what fields are required
    meetingtype_id = formdata['meetingtype']['id']
    meetingtype = MeetingType.query.filter_by(id=meetingtype_id).one_or_none()

    if meetingtype:
        optionfields = {
            MEETING_OPTION_SHOWACTIONITEMS: 'show_actions_since',
            MEETING_OPTION_TIME: 'time',
            MEETING_OPTION_LOCATION: 'location',
        }
        for option in optionfields:
            if option in meetingtype.options and not formdata[optionfields[option]]:
                results.append({'name': optionfields[option], 'status': 'please supply'})

    else:
        results.append({'name': 'meetingtype.id', 'status': 'please supply'})

    return results

meetings_view = MeetingsView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Meeting,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Meetings',
    endpoint='admin.meetings',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/meetings',
    dbmapping=meetings_dbmapping,
    formmapping=meetings_formmapping,
    checkrequired=True,
    createfieldvals=meetingcreatefieldvals,
    validate=meetings_validate,
    clientcolumns=[
        {'data': 'purpose', 'name': 'purpose', 'label': 'Purpose',
         'className': 'field_req',
         },
        {'data': 'meetingtype', 'name': 'meetingtype', 'label': 'Meeting Type',
         'className': 'field_req',
         '_treatment': {
             'relationship': {'fieldmodel': MeetingType, 'labelfield': 'meetingtype', 'formfield': 'meetingtype',
                              'dbfield': 'meetingtype', 'uselist': False,
                              'queryparams': localinterest_query_params,
                              'sortkey': lambda row: row.order
                              }}
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'datetime',
         'className': 'field_req',
         },
        {'data': 'time', 'name': 'time', 'label': 'Time',
         # see meetings_validate(), field_req class marked in afterdatatables.js
         },
        {'data': 'location', 'name': 'location', 'label': 'Location',
         'type': 'textarea',
         # see meetings_validate(), field_req class marked in afterdatatables.js
         },
        {'data': 'show_actions_since', 'name': 'show_actions_since', 'label': 'Show Actions Since',
         'type': 'datetime',
         # see meetings_validate(), field_req class marked in afterdatatables.js
         },
        {'data': 'organizer', 'name': 'organizer', 'label': 'Organizer',
         'className': 'field_req',
         '_treatment': {
             'relationship': {'fieldmodel': LocalUser, 'labelfield': 'name',
                              'formfield': 'organizer', 'dbfield': 'organizer',
                              'queryparams': lambda: {'active':True, 'interest':localinterest_query_params()['interest']},
                              'searchbox': True,
                              'uselist': False}}
         },
        {'data': 'tags', 'name': 'tags', 'label': 'Invite Tags',
         'fieldInfo': 'members who have these tags via position, will be invited to the meeting',
         '_treatment': {
             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag', 'formfield': 'tags',
                              'dbfield': 'tags', 'uselist': True,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'votetags', 'name': 'votetags', 'label': 'Vote Tags',
         'fieldInfo': 'members who have these tags via position, can vote on motions',
         '_treatment': {
             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag', 'formfield': 'votetags',
                              'dbfield': 'votetags', 'uselist': True,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'statusreporttags', 'name': 'statusreporttags', 'label': 'Status Report Tags',
         'fieldInfo': 'members who have these tags via position, are prompted to provide position status reports',
         '_treatment': {
             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag', 'formfield': 'statusreporttags',
                              'dbfield': 'statusreporttags', 'uselist': True,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'gs_agenda', 'name': 'gs_agenda', 'label': 'Agenda',
         'type': 'googledoc', 'opts': {'text': 'Agenda'},
         'render': {'eval': '$.fn.dataTable.render.googledoc( "Agenda" )'},
         },
        {'data': 'gs_status', 'name': 'gs_status', 'label': 'Report',
         # todo: 'text': 'Status Report' appears to drive what is shown on Edit view, dangling from #375
         'type': 'googledoc', 'opts': {'text': 'Status Report'},
         'render': {'eval': '$.fn.dataTable.render.googledoc( meetings_statusreportwording )'},
         },
        {'data': 'gs_minutes', 'name': 'gs_minutes_fdr', 'label': 'Minutes',
         'type': 'googledoc', 'opts': {'text': 'Minutes'},
         'render': {'eval': '$.fn.dataTable.render.googledoc( "Minutes" )'},
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=[
        'create',
        'editRefresh',
        'remove',
        'csv',
        {
            'extend': 'edit',
            'text': 'View Meeting',
            'action': {'eval': 'meetings_details'}
        },
        {
            'extend': 'edit',
            'text': 'Meeting Status',
            'action': {'eval': 'meetings_status'}
        },
        {
            'extend': 'edit',
            'text': 'Their Status Report',
            'action': {'eval': 'meetings_theirstatusreport'}
        },
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [['date:name','desc']],
    },
)
meetings_view.register()

##########################################################################################
# invites endpoint
###########################################################################################

invites_dbattrs = 'id,interest_id,meeting.purpose,meeting.date,user.name,user.email,agendaitem.agendaitem,invitekey,response,attended,activeinvite'.split(',')
invites_formfields = 'rowid,interest_id,purpose,date,name,email,agendaitem,invitekey,response,attended,activeinvite'.split(',')
invites_dbmapping = dict(zip(invites_dbattrs, invites_formfields))
invites_formmapping = dict(zip(invites_formfields, invites_dbattrs))
# invites_formmapping['date'] = lambda dbrow: isodate.dt2asc(dbrow.meeting.date)

# need aliased because LocalUser referenced twice within motions
# https://stackoverflow.com/questions/46800183/using-sqlalchemy-datatables-with-multiple-relationships-between-the-same-tables
# need to use single variable with onclause so duplicate join checking in tables.DbCrudApi.__init__() doesn't duplicate join
localuser_invites_alias = aliased(LocalUser)
localuser_invites_onclause = localuser_invites_alias.id == Invite.user_id


class InvitesView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()

        # add meeting_id to filters if requested
        self.queryparams['meeting_id'] = request.args.get('meeting_id', None)
        self.queryparams['activeinvite'] = True

        # remove empty parameters from query filters
        delfields = []
        for field in self.queryparams:
            if self.queryparams[field] == None:
                delfields.append(field)
        for field in delfields:
            del self.queryparams[field]

invites_filters = filtercontainerdiv()
invites_filters += filterdiv('invites-external-filter-date', 'Date')
invites_filters += filterdiv('invites-external-filter-name', 'Name')
invites_filters += filterdiv('invites-external-filter-attended', 'Attended')

invites_yadcf_options = [
    yadcfoption('date:name', 'invites-external-filter-date', 'range_date'),
    yadcfoption('name:name', 'invites-external-filter-name', 'multi_select', placeholder='Select names', width='200px'),
    yadcfoption('attended:name', 'invites-external-filter-attended', 'select', placeholder='Select', width='100px'),
]

invites_view = InvitesView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Invite,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pretablehtml=invites_filters.render(),
    yadcfoptions=invites_yadcf_options,
    pagename='Invites',
    endpoint='admin.invites',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/invites',
    dbmapping=invites_dbmapping,
    formmapping=invites_formmapping,
    checkrequired=True,
    tableidcontext=lambda row: {
        'agendaitem_id': row['agendaitem_id'],
    },
    tableidtemplate ='invites-{{ agendaitem_id }}',
    clientcolumns=[
        {'data': 'purpose', 'name': 'purpose', 'label': 'Meeting',
         'type': 'readonly',
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'readonly',
         '_ColumnDT_args' :
             {'sqla_expr': func.date_format(Meeting.date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'},
         },
        {'data': 'name', 'name': 'name', 'label': 'Name',
         'type': 'readonly',
         '_ColumnDT_args' :
             {'sqla_expr': localuser_invites_alias.name},
         'aliased': localuser_invites_alias,
         'onclause': localuser_invites_onclause,
         },
        {'data': 'email', 'name': 'email', 'label': 'Email',
         'type': 'readonly',
         '_ColumnDT_args' :
             {'sqla_expr': localuser_invites_alias.email},
         'aliased': localuser_invites_alias,
         'onclause': localuser_invites_onclause,
         },
        {'data': 'attended', 'name': 'attended', 'label': 'Attended',
         'className': 'TextCenter',
         '_treatment': {'boolean': {'formfield': 'attended', 'dbfield': 'attended'}},
         'ed': {'def': 'no'},
         },
        {'data': 'response', 'name': 'response', 'label': 'RSVP',
         'type': 'select2',
         'options': invite_response_all,
         },
        {'data': 'activeinvite', 'name': 'activeinvite', 'label': 'Invited',
         'className': 'TextCenter',
         '_treatment': {'boolean': {'formfield': 'activeinvite', 'dbfield': 'activeinvite'}},
         'ed': {'def': 'no'},
         },
    ],
    serverside=True,
    idSrc='rowid',
    buttons=[
        'editRefresh',
        'csv'
    ],
    dtoptions={
        'order': [['date:name','desc'], ['name:name','asc']],
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
invites_view.register()

##########################################################################################
# actionitems endpoint
###########################################################################################

class ActionItemsView(ActionItemsBase):
    def _get_localuser(self):
        return LocalUser.query.filter_by(user_id=current_user.id, interest=localinterest()).one()

    def log_update(self, formdata):
        formdata['updated_by'] = self._get_localuser().id
        formdata['update_time'] = datetime.now()

    def createrow(self, formdata):
        self.log_update(formdata)
        return super().createrow(formdata)

    def updaterow(self, thisid, formdata):
        self.log_update(formdata)
        return super().updaterow(thisid, formdata)

actionitems_view = ActionItemsView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    pagename='Action Items',
    templateargs={'adminguide': adminguide},
    endpoint='admin.actionitems',
    rule='/<interest>/actionitems',
    buttons=[
        'create',
        'editChildRowRefresh',
        'csv'
    ],
)
actionitems_view.register()

##########################################################################################
# motionsvotes endpoint
###########################################################################################

class MotionVotesView(MotionVotesBase):
    pass

motionvotes_view = MotionVotesView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    pagename='Motion Votes',
    templateargs={'adminguide': adminguide},
    endpoint='admin.motionvotes',
    rule='/<interest>/motionvotes',
    buttons=[
        'create',
        'editRefresh',
        'csv'
    ],
)
motionvotes_view.register()

##########################################################################################
# motions endpoint
###########################################################################################

class MotionsView(MotionsBase):
    def setbuttons(self):
        # standard buttons
        buttons = [
                      'editChildRowRefresh',
                      'csv'
                  ]

        # special button if meeting has online motion voting
        meeting_id = request.args.get('meeting_id', None)
        if meeting_id:
            # create only if in meeting
            buttons.insert(0, 'create')
            meeting = Meeting.query.filter_by(id=meeting_id).one()
            if meeting_has_option(meeting, MEETING_OPTION_ONLINEMOTIONS):
                buttons.append({
                    'extend': 'selected',
                    'text': 'Send eVote Requests',
                    'name': 'send-evote-req',
                    'editor': {'eval': 'motion_evote_saeditor.saeditor'},
                    'url': url_for('admin._motionvote', interest=g.interest),
                    'action': {
                        'eval': 'motion_send_evote_req("{}")'.format(rest_url_for('admin._motionvote',
                                                                                      interest=g.interest))
                    },
                },
                )

        return buttons

    def editor_method_postcommit(self, form):
        # this is here in case invites changed during edit action
        # self.updateinvites()
        self.postprocessrows(self._responsedata)

    def deleterow(self, thisid):
        MotionVote.query.filter_by(motion_id=thisid).delete()
        return super().deleterow(thisid)

    def createrow(self, formdata):
        meeting_id = formdata['meeting_id']
        output = super().createrow(formdata)

        # create motionvotes records
        ## first figure out who is allowed to vote for this meeting
        meeting = Meeting.query.filter_by(id=meeting_id).one()
        users = set()
        get_tags_users(meeting.votetags, users, meeting.date)

        ## retrieve the motion we've just created
        motion = Motion.query.filter_by(id=self.created_id).one()

        ## for each user, create a voting record
        for user in users:
            invite = Invite.query.filter_by(meeting=meeting, user=user).one_or_none()

            # this user wasn't invited to the meeting
            if not invite: continue

            vote = MotionVote(interest=localinterest(), meeting=meeting, motion=motion, user=user,
                              motionvotekey=uuid4().hex)

            # if user is attending the meeting, assume they approve, otherwise no vote
            if invite.attended:
                vote.vote = MOTIONVOTE_STATUS_APPROVED
            else:
                vote.vote = MOTIONVOTE_STATUS_NOVOTE
            db.session.add(vote)
        # db.session.commit()

        return output

motions_view = MotionsView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    pagename='Motions',
    templateargs={'adminguide': adminguide},
    endpoint='admin.motions',
    rule='/<interest>/motions',
    buttons=lambda: motions_view.setbuttons(),
    childrowoptions={
        'template': 'motion-child-row.njk',
        'showeditor': True,
        'group': 'interest',
        'groupselector': '#metanav-select-interest',
        'childelementargs': motions_childelementargs.get_childelementargs({
            'motionvotes': motionvotes_view,
        }),
    },
)
motions_view.register()

##########################################################################################
# meeting endpoint
###########################################################################################

MEETING_BUTTON_OPTION_SEND_INVITES = 'send_invitations'
MEETING_BUTTON_OPTION_DISCUSSION_REQ = 'send_discussion_req'
MEETING_BUTTON_OPTION_GEN_DOCS = 'generate_docs'
MEETING_BUTTON_OPTION_SEND_EMAIL = 'send_email'
# note config property is lambda function, else exception raised for working outside of application context
MEETING_BUTTON_OPTIONS = [
    {
        'option': {
            'value': MEETING_BUTTON_OPTION_SEND_INVITES, 'label': 'Send Invitations',
            'attr': {'title': 'add "invites" and send individual emails with link to rsvp/status page'}
        },
        'config': lambda: {
            'text': 'Send {}'.format(custom_invitations()).title(),
            'name': 'send-invites',
            'editor': {'eval': 'meeting_invites_editor'},
            'url': url_for('admin._meetinginvite', interest=g.interest),
            'action': {
                'eval': 'meeting_sendinvites("{}")'.format(rest_url_for('admin._meetinginvite',
                                                                        interest=g.interest))
            }
        },

    },
    {
        'option': {
            'value': MEETING_BUTTON_OPTION_DISCUSSION_REQ, 'label': 'Send Discussion Request',
            'attr': {'title': 'add "invites" and send group email with open To: list'}
        },
        'config': lambda: {
            'text': 'Send Discussion Request',
            'action': {
                'eval': 'meeting_send_discussion_req("{}")'.format(rest_url_for('admin._meetinginvitediscuss',
                                                                                interest=g.interest))
            }
        }
    },
    {
        'option': {
            'value': MEETING_BUTTON_OPTION_GEN_DOCS, 'label': 'Generate Docs',
            'attr': {'title': 'generate agenda and/or minutes documents'}
        },
        'config': lambda: {
            'text': 'Generate Docs',
            'action': {
                'eval': 'meeting_generate_docs("{}")'.format(rest_url_for('admin._meetinggendocs',
                                                                          interest=g.interest))
            }
        },

    },
    {
        'option': {
            'value': MEETING_BUTTON_OPTION_SEND_EMAIL, 'label': 'Send Email',
            'attr': {'title': 'send group email'}
        },
        'config': lambda: {
            'text': 'Send Email',
            'action': {
                'eval': 'meeting_send_email("{}")'.format(rest_url_for('admin._meetingsendemail',
                                                                       interest=g.interest))
            }
        },
    },
]

meeting_dbattrs = 'id,interest_id,meeting_id,order,title,agendaitem,discussion,is_attendee_only,is_action_only,'\
                  'is_hidden,hidden_reason,agendaheading'.split(',')
meeting_formfields = 'rowid,interest_id,meeting_id,order,title,agendaitem,discussion,is_attendee_only,is_action_only,'\
                     'is_hidden,hidden_reason,agendaheading'.split(',')
meeting_dbmapping = dict(zip(meeting_dbattrs, meeting_formfields))
meeting_formmapping = dict(zip(meeting_formfields, meeting_dbattrs))

def meeting_validate(action, formdata):
    results = []

    # if both of these are set, they will conflict with each other
    if formdata['is_hidden'] == 'yes' and not formdata['hidden_reason']:
        results.append({'name': 'hidden_reason', 'status': 'reason required when hiding agenda item'})

    return results

class MeetingView(DbCrudApiInterestsRolePermissions):

    def setbuttons(self):
        buttons = [
            'create',
            'editChildRowRefresh',
            'remove'
        ]
        meetingid = request.args['meeting_id']
        meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()
        for buttonoption in MEETING_BUTTON_OPTIONS:
            if meeting_has_button(meeting, buttonoption['option']['value']):
                buttons.append(buttonoption['config']())

        return buttons

    def permission(self):
        '''
        verify meetingid arg

        :return: boolean
        '''
        if 'meeting_id' not in request.args:
            return False
        meetingid = request.args['meeting_id']
        meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()
        if not meeting:
            return False
        return super().permission()

    def updateinvites(self):
        invites = Invite.query.filter_by(**self.queryparams).all()
        self.responsekeys['invites'] = []
        for invite in invites:
            thisinvite = {}
            user = localuser2user(invite.user)
            thisinvite['name'] = user.name
            thisinvite['email'] = user.email
            for k in ['response', 'attended', 'activeinvite']:
                thisinvite[k] = getattr(invite, k)
            self.responsekeys['invites'].append(thisinvite)

    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()
        self.queryparams['meeting_id'] = request.args['meeting_id']

        # should we display hidden agendaitems?
        show_hidden = request.args.get('show_hidden', False)
        if isinstance(show_hidden, str):
            show_hidden = show_hidden != 'false'
        if show_hidden:
            self.queryparams.pop('is_hidden', None)
        else:
            self.queryparams['is_hidden'] = False

    def postprocessrows(self, rows):
        for row in rows:
            if row['is_hidden'] == 'yes':
                row['DT_RowClass'] = 'hidden-row'
            tables = []
            context = {
                'meeting_id': request.args['meeting_id'],
                'agendaitem_id': row['rowid']
            }
            if row['is_attendee_only'] == 'yes':
                tablename = 'invites'
                tables.append({
                    'name': tablename,
                    'label': 'Invites',
                    'url': rest_url_for('admin.invites', interest=g.interest, urlargs=context),
                    'tableid': self.childtables[tablename]['table'].tableid(**context)
                })

            elif row['is_action_only'] == 'yes':
                tablename = 'actionitems'
                meeting = Meeting.query.filter_by(id=context['meeting_id']).one()
                # don't use context for url query, as we want action items from all meetings
                actionscontext = {'show_actions_since': meeting.show_actions_since}
                tables.append({
                    'name': tablename,
                    'label': 'Updated Action Items',
                    'url': rest_url_for('admin.actionitems', interest=g.interest, urlargs=actionscontext),
                    # but use context for table id for uniqueness
                    'tableid': self.childtables[tablename]['table'].tableid(**context)
                })

            else:
                tablename = 'actionitems'
                tables.append({
                    'name': tablename,
                    'label': 'Action Items',
                    'url': rest_url_for('admin.actionitems', interest=g.interest, urlargs=context),
                    'createfieldvals': context,
                    'tableid': self.childtables[tablename]['table'].tableid(**context)
                })
                tablename = 'motions'
                tables.append({
                    'name': tablename,
                    'label': 'Motions',
                    'url': rest_url_for('admin.motions', interest=g.interest, urlargs=context),
                    'createfieldvals': context,
                    'tableid': self.childtables[tablename]['table'].tableid(**context)
                })

            if tables:
                row['tables'] = tables

    def editor_method_postcommit(self, form):
        # # this is here in case invites changed during edit action
        # self.updateinvites()
        self.postprocessrows(self._responsedata)

    def open(self):
        super().open()
        self.postprocessrows(self.output_result['data'])

    def createrow(self, formdata):
        formdata['meeting_id'] = request.args['meeting_id']
        max = db.session.query(func.max(AgendaItem.order)).filter_by(**self.queryparams).filter(*self.queryfilters).one()
        if max[0]:
            formdata['order'] = max[0] + 1
        else:
            formdata['order'] = 1
        output = super().createrow(formdata)
        return output

    def deleterow(self, thisid):
        """
        check deletion is allowed

        :param thisid: id for row
        :return: empty list
        """
        agendaitem = AgendaItem.query.filter_by(id=thisid).one()

        # no deletions allowed after meeting
        today = date.today()
        if agendaitem.meeting.date < today:
            self._error = 'Cannot delete agenda item after meeting is over'
            raise ParameterError(self._error)

        # cannot delete an agenda item which came from a status report
        if agendaitem.statusreport:
            self._error = 'Cannot delete agenda item which came from a status report. Edit and set \'hide\' to \'yes\' instead'
            raise ParameterError(self._error)

        return super().deleterow(thisid)

def meeting_pretablehtml():
    meetingid = request.args['meeting_id']
    meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()
    pretablehtml = div()
    with pretablehtml:
        # meeting header
        h1('{} - {}'.format(meeting.date, meeting.purpose), _class='TextCenter')

        # hide / show hidden rows
        hiddenfilter = div(_class='checkbox-filter FloatRight')
        with hiddenfilter:
            input(type='checkbox', id='show-hidden-status', name='show-hidden-status', value='show-hidden')
            label('Show hidden items', _for='show-hidden-status')

        # table variables - don't display, used by beforedatatables.js meeting_send_email()
        with div(style='display: none;'):
            div(meeting.date.isoformat(), id='meeting_date')
            div(meeting.purpose, id='meeting_purpose')

        # make dom repository for Editor send invites standalone form
        with div(style='display: none;'):
            dd(**{'data-editor-field': 'invitestates'})
            dd(**{'data-editor-field': 'from_email'})
            dd(**{'data-editor-field': 'subject'})
            dd(**{'data-editor-field': 'message'})
            dd(**{'data-editor-field': 'options'})

        with script():
            raw('var invitations_text = "{}";\n'.format(custom_invitations().title()))
            raw('var invitation_text = "{}";\n'.format(custom_invitation().title()))

    return pretablehtml.render()


# for parent / child editing see
#   https://datatables.net/blog/2019-01-11#DataTables-Javascript
#   http://live.datatables.net/bihawepu/1/edit
meeting_view = MeetingView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=AgendaItem,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename=custom_meeting,
    endpoint='admin.meeting',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/meeting',
    dbmapping=meeting_dbmapping,
    formmapping=meeting_formmapping,
    checkrequired=True,
    tableidtemplate='meeting-{{ meeting_id }}-{{ agendaitem_id }}',
    pretablehtml=meeting_pretablehtml,
    validate=meeting_validate,
    clientcolumns=[
        {'data': '', # needs to be '' else get exception converting options from meetings render_template
                    # TypeError: '<' not supported between instances of 'str' and 'NoneType'
         'name':'details-control',
         'className': 'details-control shrink-to-fit',
         'orderable': False,
         'defaultContent': '',
         'label': '',
         'type': 'hidden',  # only affects editor modal
         'title': '<i class="fa fa-plus-square" aria-hidden="true"></i>',
         'render': {'eval':'render_plus'},
         },
        {'data': 'order', 'name': 'order', 'label': 'Reorder',
         'type': 'hidden',
         'className': 'reorder shrink-to-fit',
         'render': {'eval':'render_grip'},
         },
        {'data': 'title', 'name': 'title', 'label': 'Title',
         'className': 'field_req',
         },
        {'data': 'is_attendee_only', 'name': 'is_attendee_only', 'label': 'Attendee Only',
         'type': 'hidden',
         '_treatment': {'boolean': {'formfield': 'is_attendee_only', 'dbfield': 'is_attendee_only'}},
         'ed': {'type': 'hidden'},  # applied after _treatment
         'visible': False,
         },
        {'data': 'is_action_only', 'name': 'is_action_only', 'label': 'Action Only',
         '_treatment': {'boolean': {'formfield': 'is_action_only', 'dbfield': 'is_action_only'}},
         'ed': {'type': 'hidden'},  # applied after _treatment
         'visible': False,
         },
        {'data': 'agendaitem', 'name': 'agendaitem', 'label': 'Summary',
         'type': 'ckeditorClassic',
         'visible': False,
         'fieldInfo': 'this comes from the person who wrote the status report',
         },
        {'data': 'discussion', 'name': 'discussion', 'label': 'Discussion',
         'type': 'ckeditorClassic',
         'visible': False,
         'fieldInfo': 'this is to record any discussion held at the meeting',
         },
        {'data': 'agendaheading', 'name': 'agendaheading', 'label': 'Agenda Heading',
         'fieldInfo': 'heading under which this agenda item is shown in agenda',
         '_treatment': {
             'relationship': {'fieldmodel': AgendaHeading, 'labelfield': 'heading', 'formfield': 'agendaheading',
                              'dbfield': 'agendaheading', 'uselist': False,
                              'queryparams': localinterest_query_params,
                              'searchbox': True,
                              'nullable': True,
                              }}
         },
        {'data': 'is_hidden', 'name': 'is_hidden', 'label': 'Hide',
         '_treatment': {'boolean': {'formfield': 'is_hidden', 'dbfield': 'is_hidden'}},
         'visible': False,
         'ed': {'def': 'no'},
         },
        {'data': 'hidden_reason', 'name': 'hidden_reason', 'label': 'Reason for Hiding',
         'type': 'textarea',
         'visible': False,
         },
    ],
    childrowoptions= {
        'template': 'meeting-child-row.njk',
        'showeditor': True,
        'group': 'interest',
        'groupselector': '#metanav-select-interest',
        'childelementargs': [
            {'name':'invites', 'type':CHILDROW_TYPE_TABLE, 'table':invites_view,
             'tableidtemplate': 'invites-{{ parentid }}',
             'args':{
                     'buttons': [],
                     'columns': {
                         'datatable': {
                             # uses data field as key
                             'date': {'visible': False}, 'purpose': {'visible': False},
                             'activeinvite': {'visible': False}
                         },
                         'editor': {
                             # uses name field as key
                             'date': {'type': 'hidden'}, 'purpose': {'type': 'hidden'},
                             'response': {'type': 'hidden'}, 'activeinvite': {'type': 'hidden'}
                         },
                     },
                     'inline' : {
                         # uses name field as key; value is used for editor.inline() options
                         'attended': {'submitOnBlur': True}
                     },
                     'updatedtopts': {
                         'dom': 'Bfrt',
                         'paging': False,
                     }
                 }
             },
            {'name': 'actionitems', 'type': CHILDROW_TYPE_TABLE, 'table': actionitems_view,
             # rowid is of parent row
             'tableidtemplate': 'actionitems-{{ parentid }}',
             'args': {
                 'buttons': ['create', 'editChildRowRefresh', 'remove'],
                 'columns': {
                     'datatable': {
                         # uses data field as key
                         'date': {'visible': False}, 'purpose': {'visible': False},
                     },
                     'editor': {
                         # uses name field as key
                         'date': {'type': 'hidden'}, 'purpose': {'type': 'hidden'},
                     },
                 },
                 'updatedtopts': {
                     'dom': 'Bfrt',
                     'paging': False,
                 }
             }
             },
            {'name': 'motions', 'type': CHILDROW_TYPE_TABLE, 'table': motions_view,
             'tableidtemplate': 'motions-{{ parentid }}',
             'args': {
                 # 'buttons': is motions_view.setbuttons(), [don't override]
                 'columns': {
                     'datatable': {
                         # uses data field as key
                         'date': {'visible': False}, 'purpose': {'visible': False},
                     },
                     'editor': {
                         # uses name field as key
                         'date': {'type': 'hidden'}, 'purpose': {'type': 'hidden'},
                     },
                 },
                 'updatedtopts': {
                     'dom': 'Bfrt',
                     'paging': False,
                 }
             }
             },
        ],
    },
    serverside=True,
    idSrc='rowid',
    buttons=lambda: meeting_view.setbuttons(),
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [['order:name','asc']],
        'paging': False,
        'rowReorder': {
            'dataSrc': 'order',
            'selector': 'td.reorder',
            'snapX': True,
        },

},
)
meeting_view.register()

##########################################################################################
# theirstatusreport endpoint
##########################################################################################

class TheirStatusReportView(MemberStatusReportBase):
    def permission(self):
        invitekey = request.args.get('invitekey', None)
        meeting_id = request.args.get('meeting_id', None)
        if not invitekey and not meeting_id:
            return False
        return super().permission()

    def beforequery(self):
        super().beforequery()
        invitekey = request.args.get('invitekey', None)
        meeting_id = request.args.get('meeting_id', None)
        self.theuser = None
        # set user based on invite key
        if invitekey:
            invite = self.get_invite()
            self.theuser = localuser2user(invite.user)
            self.meeting = self.get_meeting()
            self.queryparams['invite_id'] = invite.id
        # if no invitekey, there's no query. See self.open()

    def get_invite(self):
        invitekey = request.args.get('invitekey')
        invite = Invite.query.filter_by(invitekey=invitekey).one()
        return invite

    def format_pretablehtml(self):
        # for some reason self.theuser doesn't exist within this instance when called, maybe because of the way
        # pluggable views works. Recalculate theuser
        theuser = None
        invitekey = request.args.get('invitekey', None)
        if invitekey:
            invite = Invite.query.filter_by(invitekey=invitekey).one()
            theuser = invite.user

        meeting = self.get_meeting()
        html = div()
        with html:
            self.instructions()
            self.custom_wording()
            with h1(_class='TextCenter'):
                text('{} - {} - '.format(meeting.date, meeting.purpose))
                invites = Invite.query.filter_by(meeting=meeting).all()
                invites.sort(key=lambda item: item.user.name)
                with select(id='user-select', _class='h1-select', style='width: 20em;'):
                    option()
                    for invite in invites:
                        option(invite.user.name, value=invite.invitekey, selected=(invite.user==theuser))
            with script():
                text(
                    'var userselect = $(\'#user-select\');\n'
                    'userselect.select2({\n'
                    '   dropdownAutoWidth: true,\n'
                    '   placeholder: \'select a member\',\n'
                    '   allowClear: true,\n'
                    '});\n'
                    'userselect.change(function() {\n'
                )
                raw('   window.location.href = \'{}?meeting_id={}&invitekey=\' + userselect.val() ;\n'.format(
                    url_for('admin.theirstatusreport', interest=g.interest), meeting.id
                ))
                text('});')
        return html.render()

    def open(self):
        # if user is known, do the normal processing
        if self.theuser:
            super().open()

        # if user isn't known, this is a no-op
        else:
            self.rows = iter([])

theirstatusreport_view = TheirStatusReportView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    templateargs={'adminguide': adminguide},
    pagename=lambda: 'Their {}'.format(invite_statusreport().title()),
    endpoint='admin.theirstatusreport',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/theirstatusreport',
)
theirstatusreport_view.register()

##########################################################################################
# meetinggendocs api endpoint
##########################################################################################

class MeetingGenDocsApi(MethodView):

    def __init__(self):
        self.roles_accepted = [ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN]

    def permission(self):
        '''
        determine if current user is permitted to use the view
        '''
        # adapted from loutilities.tables.DbCrudApiRolePermissions
        allowed = False

        # must have meeting_id query arg
        if request.args.get('meeting_id', False):
            for role in self.roles_accepted:
                if current_user.has_role(role):
                    allowed = True
                    break

        return allowed

    def post(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            reports = []
            for report in meeting_reports:
                if request.form.get(report, 'false') == 'true':
                    reports.append(report)

            successful = meeting_gen_reports(request.args['meeting_id'], reports)

            output_result = {'status' : 'success'}

            db.session.commit()
            return jsonify(output_result)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_meetinggendocs/rest', view_func=MeetingGenDocsApi.as_view('_meetinggendocs'), methods=['POST'])

#########################################################################################
# meeting api base
#########################################################################################

class MeetingApiBase(MethodView):

    def __init__(self):
        self.roles_accepted = [ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN]


    def permission(self):
        '''
        determine if current user is permitted to use the view
        '''
        # adapted from loutilities.tables.DbCrudApiRolePermissions
        allowed = False

        # must have meeting_id query arg
        if request.args.get('meeting_id', False):
            for role in self.roles_accepted:
                if current_user.has_role(role):
                    allowed = True
                    break

        return allowed


##########################################################################################
# meetingemail api endpoint
##########################################################################################

class MeetingEmailApi(MeetingApiBase):

    def get(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            meeting_id = request.args['meeting_id']
            invitestates, invites = get_invites(meeting_id)

            # set defaults
            meeting = Meeting.query.filter_by(id=meeting_id).one()
            from_email = meeting.organizer.email
            subject = '[{} {}] '.format(meeting.purpose, meeting.date)
            message = ''

            # pick up from address used in invite
            email = Email.query.filter_by(meeting_id=meeting.id, type=MEETING_INVITE_EMAIL).one_or_none()
            if email:
                from_email = email.from_email

            # if mail has previously been sent, pick up from address used prior (may have overridden invite from_email)
            email = Email.query.filter_by(meeting_id=meeting.id, type=MEETING_EMAIL).one_or_none()
            if email:
                from_email = email.from_email

            return jsonify(from_email=from_email, subject=subject, message=message,
                           invitestates=invitestates)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status': 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

    def post(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            # there should be one 'id' in this form data, 'keyless'
            requestdata = get_request_data(request.form)
            meeting_id = request.args['meeting_id']
            from_email = requestdata['keyless']['from_email']
            subject = requestdata['keyless']['subject']
            message = requestdata['keyless']['message']

            email = Email.query.filter_by(meeting_id=meeting_id, type=MEETING_EMAIL).one_or_none()
            if not email:
                email = Email(interest=localinterest(), meeting_id=meeting_id, type=MEETING_EMAIL)
                db.session.add(email)

            email.from_email = from_email
            db.session.flush()

            tolist = send_meeting_email(meeting_id, subject, message)

            output_result = {'status' : 'success', 'sent_to': tolist}

            db.session.commit()
            return jsonify(output_result)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_meetingsendemail/rest', view_func=MeetingEmailApi.as_view('_meetingsendemail'),
                methods=['GET', 'POST'])


#########################################################################################
# meetinginvite api endpoint
#########################################################################################

class MeetingInviteApi(MeetingApiBase):

    def get(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            meeting_id = request.args['meeting_id']
            invitestates, invites = get_invites(meeting_id)

            # set defaults
            meeting = Meeting.query.filter_by(id=meeting_id).one()
            from_email = meeting.organizer.email
            rsvp_text = ''
            if meeting_has_option(meeting, MEETING_OPTION_RSVP):
                rsvp_text = 'RSVP and '
            subject = '[{} {}] {} -- {}{} Request'.format(
                meeting.purpose, meeting.date, custom_invitation().title(), rsvp_text, custom_statusreport().title())
            message = ''

            # if mail has previously been sent, pick up values used prior
            email = Email.query.filter_by(meeting_id=meeting.id, type=MEETING_INVITE_EMAIL).one_or_none()
            if email:
                from_email = email.from_email
                subject = email.subject
                message = email.message

            return jsonify(from_email=from_email, subject=subject, message=message,
                           invitestates=invitestates)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status': 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

    def post(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            # there should be one 'id' in this form data, 'keyless'
            requestdata = get_request_data(request.form)
            meeting_id = request.args['meeting_id']
            from_email = requestdata['keyless']['from_email']
            subject = requestdata['keyless']['subject']
            message = requestdata['keyless']['message']
            # options = requestdata['keyless']['options']

            email = Email.query.filter_by(meeting_id=meeting_id, type=MEETING_INVITE_EMAIL).one_or_none()
            if not email:
                email = Email(interest=localinterest(), type=MEETING_INVITE_EMAIL, meeting_id=meeting_id)
                db.session.add(email)

            # save updates, used by generateinvites()
            email.from_email = from_email
            email.subject = subject
            email.message = message
            # email.options = options
            db.session.flush()

            agendaitem = generateinvites(meeting_id)

            # if attendees agendaitem was created, return it to caller
            if agendaitem:
                # use meeting view's dte to get the response data
                thisrow = meeting_view.dte.get_response_data(agendaitem)
                self._responsedata = [thisrow]
            # if attendees agendaitem wasn't created, return empty response
            else:
                self._responsedata = []

            db.session.commit()
            return jsonify(self._responsedata)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_meetinginvite/rest', view_func=MeetingInviteApi.as_view('_meetinginvite'),
                methods=['GET', 'POST'])


#########################################################################################
# meetingdiscuss api endpoint
#########################################################################################

class MeetingDiscussApi(MeetingApiBase):

    def get(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            meeting_id = request.args['meeting_id']
            invitestates, invites = get_invites(meeting_id)

            # set defaults
            meeting = Meeting.query.filter_by(id=meeting_id).one()
            from_email = meeting.organizer.email
            subject = '[{} {}] Discussion Request'.format(
                meeting.purpose, meeting.date)
            message = ''

            # if mail has previously been sent, pick up values used prior
            email = Email.query.filter_by(meeting_id=meeting.id, type=MEETING_INVITE_EMAIL).one_or_none()
            if email:
                from_email = email.from_email
                subject = email.subject
                message = email.message
                options = email.options

            return jsonify(from_email=from_email, subject=subject, message=message, invitestates=invitestates)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status': 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

    def post(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            # there should be one 'id' in this form data, 'keyless'
            requestdata = get_request_data(request.form)
            meeting_id = request.args['meeting_id']
            from_email = requestdata['keyless']['from_email']
            subject = requestdata['keyless']['subject']
            message = requestdata['keyless']['message']
            # options = requestdata['keyless']['options']

            email = Email.query.filter_by(meeting_id=meeting_id, type=MEETING_INVITE_EMAIL).one_or_none()
            if not email:
                email = Email(interest=localinterest(), type=MEETING_INVITE_EMAIL, meeting_id=meeting_id)
                db.session.add(email)

            # save updates, used by generateinvites()
            email.from_email = from_email
            email.subject = subject
            email.message = message
            db.session.flush()

            generateinvites(meeting_id, sendemail=False, agendatitle=None)
            send_discuss_email(meeting_id)

            self._responsedata = []

            db.session.commit()
            return jsonify(self._responsedata)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_meetinginvitediscuss/rest', view_func=MeetingDiscussApi.as_view('_meetinginvitediscuss'),
                methods=['GET', 'POST'])


##########################################################################################
# meetingstatus endpoint
###########################################################################################

class MeetingStatusView(DbCrudApiInterestsRolePermissions):
    def open(self):
        '''
        retrieve all the positions which have status reports for this meeting
        '''
        meeting_id = request.args['meeting_id']
        meeting = Meeting.query.filter_by(id=meeting_id).one()

        # assumes self.serverside = False
        # self.rows will be handled in nexttablerow()
        rows = get_tags_positions(meeting.statusreporttags)
        self.rows = iter(rows)

    @_editormethod(checkaction='edit', formrequest=True)
    def put(self, thisid):
        # allow multirow editing, i.e., to send emails for multiple selected positions
        theseids = thisid.split(',')
        meeting_id = request.args['meeting_id']
        meeting = Meeting.query.filter_by(id=meeting_id).one()
        positions = []
        self._responsedata = []
        users = set()
        for id in theseids:
            # try to coerce to int, but ok if not
            try:
                id = int(id)
            except ValueError:
                pass

            # collect users which hold this position, and positions which have been selected
            position = Position.query.filter_by(id=id).one()
            users |= set(members_active(position, meeting.date))
            positions.append(position)

        # send reminder email to each user
        self.responsekeys = {'reminded': [], 'newinvites': []}
        for user in users:
            reminder = generatereminder(meeting_id, user, positions)
            if reminder:
                self.responsekeys['reminded'].append('{}'.format(user.name))
            else:
                self.responsekeys['newinvites'].append('{}'.format(user.name))

        # do this at the end to pick up invite.lastreminded (updated in generatereminder())
        # note need to flush to pick up any new invites
        db.session.flush()
        for id in theseids:
            thisdata = self._data[id]
            thisrow = self.updaterow(id, thisdata)
            self._responsedata += [thisrow]


def meetingstatus_getstatus(row):
    meeting_id = request.args['meeting_id']
    statusreport = StatusReport.query.filter_by(meeting_id=meeting_id, position=row).one_or_none()
    if not statusreport or not statusreport.statusreport:
        return 'missing'
    else:
        return 'entered'

def meetingstatus_getusers(position):
    meeting_id = request.args['meeting_id']
    meeting = Meeting.query.filter_by(id=meeting_id).one()
    members = []
    for member in members_active(position, meeting.date):
        invite = Invite.query.filter_by(meeting_id=meeting_id, user=member).one_or_none()
        # lastreminder should always be present, but maybe not for testing
        if invite and invite.lastreminder:
            members.append('{} ({})'.format(member.name, isodate.dt2asc(invite.lastreminder)))
        else:
            members.append(member.name)
    return ', '.join(members)

def meetingstatus_pretablehtml():
    meetingid = request.args['meeting_id']
    meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()
    pretablehtml = div()
    with pretablehtml:
        # meeting header
        h1('{} - {}'.format(meeting.date, meeting.purpose), _class='TextCenter')

        meetingstatus_filters = filtercontainerdiv()
        with meetingstatus_filters:
            filterdiv('meetingstatus-external-filter-status', 'Status')

        # make dom repository for Editor send reminders standalone form
        with div(style='display: none;'):
            dd(**{'data-editor-field': 'invitestates'})
            dd(**{'data-editor-field': 'from_email'})
            dd(**{'data-editor-field': 'subject'})
            dd(**{'data-editor-field': 'message'})
            dd(**{'data-editor-field': 'options'})

    return pretablehtml.render()

meetingstatus_dbattrs = 'id,interest_id,position,users,status'.split(',')
meetingstatus_formfields = 'rowid,interest_id,position,users,status'.split(',')
meetingstatus_dbmapping = dict(zip(meetingstatus_dbattrs, meetingstatus_formfields))
meetingstatus_formmapping = dict(zip(meetingstatus_formfields, meetingstatus_dbattrs))
meetingstatus_formmapping['status'] = meetingstatus_getstatus
meetingstatus_formmapping['users'] = meetingstatus_getusers

meetingstatus_yadcf_options = [
    yadcfoption('status:name', 'meetingstatus-external-filter-status', 'select', placeholder='Select', width='130px'),
]

meetingstatus_view = MeetingStatusView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Position,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    pretablehtml=meetingstatus_pretablehtml,
    templateargs={'adminguide': adminguide},
    yadcfoptions=meetingstatus_yadcf_options,
    pagename='Meeting Status',
    endpoint='admin.meetingstatus',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/meetingstatus',
    dbmapping=meetingstatus_dbmapping,
    formmapping=meetingstatus_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'position', 'name': 'position', 'label': 'Position',
         'type': 'readonly',
         },
        {'data': 'users', 'name': 'users', 'label': 'Members (last request)',
         'type': 'readonly',
         },
        {'data': 'status', 'name': 'status', 'label': 'Status Report',
         'type': 'readonly',
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=lambda: [
        # 'editor' gets eval'd to editor instance
        {'text': 'Send Reminders',
         'name': 'send-reminders',
         'editor': {'eval': 'meeting_invites_editor'},
         'url': url_for('admin._meetingstatusreminder', interest=g.interest),
         'action': {
             'eval': 'meeting_sendreminders("{}")'.format(rest_url_for('admin._meetingstatusreminder',
                                                                       interest=g.interest))}
         },
        'csv'
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'select': 'os',
    },
)
meetingstatus_view.register()


#########################################################################################
# meetingstatusreminder api endpoint
#########################################################################################

class MeetingStatusReminderApi(MeetingApiBase):

    def permission(self):
        '''
        determine if current user is permitted to use the view
        '''
        allowed = super().permission()

        # must have ids query arg, overrides super().permission() check
        if not request.args.get('ids', False):
            allowed = False

        return allowed

    def get_reminders(self, meeting_id, theseposids):
        '''
        get members who need to be reminded, and their positions

        :param meeting_id: id of meeting to check for invites
        :param theseposids: position ids to check
        :return: {member:invitestate, member:invitestate, ...}, [position, position, ...]
        '''
        meeting = Meeting.query.filter_by(id=meeting_id).one()
        positions = []
        members = set()
        for id in theseposids:
            # try to coerce to int, but ok if not
            try:
                id = int(id)
            except ValueError:
                pass

            # collect members which hold this position, and positions which have been selected
            position = Position.query.filter_by(id=id).one()
            members |= set(members_active(position, meeting.date))
            positions.append(position)

        memberinvitestates = {}
        for member in members:
            invite = Invite.query.filter_by(meeting_id=meeting_id, user=member).one_or_none()
            if invite:
                memberinvitestates[member] = True
            else:
                memberinvitestates[member] = False

        return memberinvitestates, positions

    def get(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            # this returns reminder form options, similar to MeetingInviteAPI
            meeting_id = request.args['meeting_id']
            # set defaults from meeting first, then from invite email if it exists (it should)
            meeting = Meeting.query.filter_by(id=meeting_id).one()
            from_email = meeting.organizer.email
            subject = '[{} {}] Reminder -- RSVP and Status Report Request'.format(meeting.purpose, meeting.date)
            message = ''

            # if mail has been sent as invite, pick up values used prior
            email = Email.query.filter_by(meeting_id=meeting.id, type=MEETING_INVITE_EMAIL).one_or_none()
            if email:
                from_email = email.from_email
                # override default subject
                subject = '[{} {}] Reminder -- RSVP and Status Report Request'.format(meeting.purpose, meeting.date)
                message = email.message

            # if mail has been sent as reminder, pick up values used prior
            email = Email.query.filter_by(meeting_id=meeting.id, type=MEETING_REMINDER_EMAIL).one_or_none()
            if email:
                from_email = email.from_email
                subject = email.subject
                message = email.message

            theseposids = request.args['ids'].split(',')
            userstates, positions = self.get_reminders(meeting_id, theseposids)

            invitestates = {'reminders': [], 'invites': []}
            for user in userstates:
                # if already invited, send reminder
                if userstates[user]:
                    invitestates['reminders'].append({'name': user.name, 'email': user.email})
                # otherwise send invite
                else:
                    invitestates['invites'].append({'name': user.name, 'email': user.email})

            return jsonify(from_email=from_email, subject=subject, message=message,
                           invitestates=invitestates)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status': 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

    def post(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            meeting_id = request.args['meeting_id']
            theseposids = request.args['ids'].split(',')
            userstates, positions = self.get_reminders(meeting_id, theseposids)

            # there should be one 'id' in this form data, 'keyless'
            requestdata = get_request_data(request.form)
            meeting_id = request.args['meeting_id']
            from_email = requestdata['keyless']['from_email']
            subject = requestdata['keyless']['subject']
            message = requestdata['keyless']['message']

            # if mail has been sent as reminder, save in previous record, else create record then save
            email = Email.query.filter_by(interest=localinterest(), meeting_id=meeting_id, type=MEETING_REMINDER_EMAIL).one_or_none()
            if not email:
                email = Email(interest=localinterest(), meeting_id=meeting_id, type=MEETING_REMINDER_EMAIL)
                db.session.add(email)
            email.from_email = from_email
            email.subject = subject
            email.message = message
            # flush so generatereminder() can pick up latest email record
            db.session.flush()

            # send reminder email to each user
            for user in userstates:
                reminder = generatereminder(request.args['meeting_id'], user, positions)
            # note need to flush to pick up any new invites
            db.session.flush()

            # do this at the end to pick up invite.lastreminded (updated in generatereminder())
            self._responsedata = []
            meeting = Meeting.query.filter_by(id=meeting_id).one()
            srpositions = get_tags_positions(meeting.statusreporttags)
            for user in userstates:
                for position in positions_active(user, meeting.date):
                    if position in srpositions:
                        thisrow = meetingstatus_view.dte.get_response_data(position)
                        self._responsedata += [thisrow]

            db.session.commit()
            return jsonify(self._responsedata)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_meetingstatusreminder/rest', view_func=MeetingStatusReminderApi.as_view('_meetingstatusreminder'),
                methods=['GET', 'POST'])


##########################################################################################
# agendaheadings endpoint
###########################################################################################

agendaheadings_dbattrs = 'id,interest_id,heading,positions'.split(',')
agendaheadings_formfields = 'rowid,interest_id,heading,positions'.split(',')
agendaheadings_dbmapping = dict(zip(agendaheadings_dbattrs, agendaheadings_formfields))
agendaheadings_formmapping = dict(zip(agendaheadings_formfields, agendaheadings_dbattrs))

agendaheadings_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=AgendaHeading,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Agenda Headings',
    endpoint='admin.agendaheadings',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/agendaheadings',
    dbmapping=agendaheadings_dbmapping,
    formmapping=agendaheadings_formmapping,
    checkrequired=True,
    tableidtemplate ='agendaheadings-{{ meeting_id }}-{{ motion_id }}',
    clientcolumns=[
        {'data': 'heading', 'name': 'heading', 'label': 'Agenda Heading',
         '_unique': True,
         },
        {'data': 'positions', 'name': 'positions', 'label': 'Positions',
         '_treatment': {
             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'positions',
                              'dbfield': 'positions', 'uselist': True,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         }
    ],
    idSrc='rowid',
    buttons=[
        'create',
        'editRefresh',
        'remove',
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
agendaheadings_view.register()

##########################################################################################
# meetingtypes endpoint
###########################################################################################

class MeetingTypesView(DbCrudApiInterestsRolePermissions):
    def createrow(self, formdata):
        '''
        provide default for order field when row is created
        :param formdata: data from form
        :return: see super().createrow()
        '''
        max = db.session.query(func.max(MeetingType.order)).filter_by(**self.queryparams).filter(*self.queryfilters).one()
        if max[0]:
            formdata['order'] = max[0] + 1
        else:
            formdata['order'] = 1
        output = super().createrow(formdata)
        return output

meetingtypes_dbattrs = 'id,interest_id,order,meetingtype,options,buttonoptions,meetingwording,statusreportwording,invitewording,autoagendatitle'.split(',')
meetingtypes_formfields = 'rowid,interest_id,order,meetingtype,options,buttonoptions,meetingwording,statusreportwording,invitewording,autoagendatitle'.split(',')
meetingtypes_dbmapping = dict(zip(meetingtypes_dbattrs, meetingtypes_formfields))
meetingtypes_formmapping = dict(zip(meetingtypes_formfields, meetingtypes_dbattrs))

meetingtypes_view = MeetingTypesView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=MeetingType,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Meeting Types',
    endpoint='admin.meetingtypes',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/meetingtypes',
    dbmapping=meetingtypes_dbmapping,
    formmapping=meetingtypes_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'order', 'name': 'order', 'label': 'Reorder',
         'type': 'hidden',
         'className': 'reorder shrink-to-fit',
         'render': {'eval': 'render_grip'},
         },
        {'data': 'meetingtype', 'name': 'meetingtype', 'label': 'Meeting Type',
         '_unique': True,
         },
        {'data': 'autoagendatitle', 'name': 'autoagendatitle', 'label': 'Automatic Agenda Item Title',
         'fieldInfo': 'When a meeting is created, if this is specified, it will cause an agenda item to be created '
                      'in the meeting with this title. Note this can include text of the form {{ purpose }} or '
                      '{{ meetingtype.statusreportwording }} which is templated against the meeting record. '
                      'See the administrator for acceptable template variables.',
        },
        {'data': 'meetingwording', 'name': 'meetingwording', 'label': '"meeting"',
         'fieldInfo': 'If you don\'t want the text on the page and emails to say "meeting" you can customize '
                      'that here. Use lowercase letters.',
         'ed': {'label': 'Custom Wording for "meeting"', 'def': 'meeting'},
        },
        {'data': 'statusreportwording', 'name': 'statusreportwording', 'label': '"status report"',
         'fieldInfo': 'If you don\'t want the text on the page and emails to say "status report" you can customize '
                      'that here. Use lowercase letters.',
         'ed': {'label': 'Custom Wording for "status report"', 'def': 'status report'},
         },
        {'data': 'invitewording', 'name': 'invitewording', 'label': '"invitation"',
         'fieldInfo': 'If you don\'t want the text on the page and emails to say "invitation" you can customize '
                      'that here. Use lowercase letters.',
         'ed': {'label': 'Custom Wording for "invitation"', 'def': 'invitation'},
         },
        {'data': 'options', 'name': 'options', 'label': 'Meeting Options',
         'type': 'checkbox',
         'ed': {
             'options': [{'value': o, 'label': MEETING_OPTIONS[o]} for o in MEETING_OPTIONS],
             'separator': MEETING_OPTION_SEPARATOR,
         }
         },
        {'data': 'buttonoptions', 'name': 'buttonoptions', 'label': 'Meeting Button Options',
         'type': 'checkbox',
         'ed': {
             'options': [o['option'] for o in MEETING_BUTTON_OPTIONS],
             'separator': MEETING_OPTION_SEPARATOR,
         }
         },
    ],
    idSrc='rowid',
    buttons=[
        'create',
        'editRefresh',
        'remove',
        'csv'
    ],
    dtoptions={
        'order': [['order:name', 'asc']],
        'rowReorder': {
            'dataSrc': 'order',
            'selector': 'td.reorder',
            'snapX': True,
        },
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
meetingtypes_view.register()
