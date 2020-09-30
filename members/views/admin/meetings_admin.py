"""
meetings_admin - administrative task handling for meetings admin
====================================================================================
"""
# standard
from datetime import datetime, date
from traceback import format_exception_only, format_exc

# pypi
from flask import g, request, jsonify, current_app
from flask.views import MethodView
from flask_security import current_user
from dominate.tags import h1, div, label, input
from sqlalchemy import func
from sqlalchemy.orm import aliased

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Tag
from ...model import Meeting, Invite, AgendaItem, ActionItem, Motion, MotionVote, AgendaHeading, Position, StatusReport
from ...model import localinterest_query_params, localinterest_viafilter
from ...model import invite_response_all
from ...model import action_all, motion_all, motionvote_all
from ...model import MOTION_STATUS_OPEN, MOTIONVOTE_STATUS_APPROVED, MOTIONVOTE_STATUS_NOVOTE
from ...model import ACTION_STATUS_OPEN
from ...meeting_invites import generateinvites, get_invites, generatereminder
from .viewhelpers import dtrender, localinterest, localuser2user, get_tags_users
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption
from members.reports import meeting_gen_reports, meeting_reports

from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.user.model import User
from loutilities.tables import _editormethod, get_request_action, rest_url_for, CHILDROW_TYPE_TABLE

from loutilities.timeu import asctime
isodate = asctime('%Y-%m-%d')

class ParameterError(Exception): pass

debug = False

##########################################################################################
# tags endpoint
###########################################################################################

tag_dbattrs = 'id,interest_id,tag,description,positions,users'.split(',')
tag_formfields = 'rowid,interest_id,tag,description,positions,users'.split(',')
tag_dbmapping = dict(zip(tag_dbattrs, tag_formfields))
tag_formmapping = dict(zip(tag_formfields, tag_dbattrs))

tag = DbCrudApiInterestsRolePermissions(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Tag,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    pagename='Tags',
    endpoint='admin.tags',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/tags',
    dbmapping=tag_dbmapping,
    formmapping=tag_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'tag', 'name': 'tag', 'label': 'Tag',
         'className': 'field_req',
         '_unique': True,
         },
        {'data': 'description', 'name': 'description', 'label': 'Description',
         'className': 'field_req',
         'type': 'textarea',
         },
        {'data': 'positions', 'name': 'positions', 'label': 'Positions',
         'fieldInfo': 'tags are assigned to positions, members, or both',
         '_treatment': {
             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'positions',
                              'dbfield': 'positions', 'uselist': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'users', 'name': 'users', 'label': 'Members',
         'fieldInfo': 'tags are assigned to positions, members, or both',
         '_treatment': {
             # viadbattr stores the LocalUser id which has user_id=user.id for each of these
             # and pulls the correct users out of User based on LocalUser table
             'relationship': {'fieldmodel': User, 'labelfield': 'name',
                              'formfield': 'users', 'dbfield': 'users',
                              'viadbattr': LocalUser.user_id,
                              'viafilter': localinterest_viafilter,
                              'queryparams': {'active': True},
                              'uselist': True}}
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'remove', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
tag.register()

##########################################################################################
# meetings endpoint
###########################################################################################

meetings_dbattrs = 'id,interest_id,date,purpose,show_actions_since,tags,votetags,time,location,'\
                   'gs_agenda,gs_status,gs_minutes'.split(',')
meetings_formfields = 'rowid,interest_id,date,purpose,show_actions_since,tags,votetags,time,location,' \
                      'gs_agenda,gs_status,gs_minutes'.split(',')
meetings_dbmapping = dict(zip(meetings_dbattrs, meetings_formfields))
meetings_formmapping = dict(zip(meetings_formfields, meetings_dbattrs))
meetings_dbmapping['date'] = lambda formrow: dtrender.asc2dt(formrow['date'])
meetings_formmapping['date'] = lambda dbrow: dtrender.dt2asc(dbrow.date)
meetings_dbmapping['show_actions_since'] = lambda formrow: dtrender.asc2dt(formrow['show_actions_since'])
meetings_formmapping['show_actions_since'] = lambda dbrow: dtrender.dt2asc(dbrow.show_actions_since)

def meetingcreatefieldvals():
    interest = localinterest()
    return {
        'tags.id': [t.id for t in interest.interestmeetingtags],
        'votetags.id': [t.id for t in interest.interestmeetingvotetags],
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
        agendaitem = AgendaItem(interest=localinterest(), meeting=themeeting, order=2, title='Action Items', agendaitem='',
                                is_action_only=True)
        db.session.add(agendaitem)
        return output

meetings = MeetingsView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Meeting,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    pagename='Meetings',
    endpoint='admin.meetings',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/meetings',
    dbmapping=meetings_dbmapping,
    formmapping=meetings_formmapping,
    checkrequired=True,
    createfieldvals=meetingcreatefieldvals,
    clientcolumns=[
        {'data': 'purpose', 'name': 'purpose', 'label': 'Purpose',
         'className': 'field_req',
         'type': 'textarea',
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'datetime',
         'className': 'field_req',
         },
        {'data': 'time', 'name': 'time', 'label': 'Time',
         'className': 'field_req',
         },
        {'data': 'location', 'name': 'location', 'label': 'Location',
         'type': 'textarea',
         'className': 'field_req',
         },
        {'data': 'show_actions_since', 'name': 'show_actions_since', 'label': 'Show Actions Since',
         'type': 'datetime',
         'className': 'field_req',
         },
        {'data': 'gs_agenda', 'name': 'gs_agenda', 'label': 'Agenda',
         'type': 'googledoc', 'opts': {'text': 'Agenda'},
         'render': {'eval': '$.fn.dataTable.render.googledoc( "Agenda" )'},
         },
        {'data': 'gs_status', 'name': 'gs_status', 'label': 'Status Report',
         'type': 'googledoc', 'opts': {'text': 'Status Report'},
         'render': {'eval': '$.fn.dataTable.render.googledoc( "Status Report" )'},
         },
        {'data': 'gs_minutes', 'name': 'gs_minutes_fdr', 'label': 'Minutes',
         'type': 'googledoc', 'opts': {'text': 'Minutes'},
         'render': {'eval': '$.fn.dataTable.render.googledoc( "Minutes" )'},
         },
        {'data': 'tags', 'name': 'tags', 'label': 'Invite Tags',
         'fieldInfo': 'members who have these tags, either directly or via position, will be invited to the meeting',
         '_treatment': {
             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag', 'formfield': 'tags',
                              'dbfield': 'tags', 'uselist': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'votetags', 'name': 'votetags', 'label': 'Vote Tags',
         'fieldInfo': 'members who have these tags, either directly or via position, can vote on motions',
         '_treatment': {
             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag', 'formfield': 'votetags',
                              'dbfield': 'votetags', 'uselist': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=[
        {
            'extend': 'edit',
            'text': 'View Meeting',
            'action': {'eval': 'meeting_details'}
        },
        {
            'extend': 'edit',
            'text': 'Meeting Status',
            'action': {'eval': 'meeting_status'}
        },
        'create',
        'editRefresh',
        'remove',
        'csv'
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [['date:name','desc']],
    },
)
meetings.register()

##########################################################################################
# invites endpoint
###########################################################################################

invites_dbattrs = 'id,interest_id,meeting.purpose,meeting.date,user.name,user.email,agendaitem.agendaitem,invitekey,response,attended,activeinvite'.split(',')
invites_formfields = 'rowid,interest_id,purpose,date,name,email,agendaitem,invitekey,response,attended,activeinvite'.split(',')
invites_dbmapping = dict(zip(invites_dbattrs, invites_formfields))
invites_formmapping = dict(zip(invites_formfields, invites_dbattrs))
# invites_formmapping['date'] = lambda dbrow: isodate.dt2asc(dbrow.meeting.date)

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

invites = InvitesView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Invite,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    pretablehtml=invites_filters.render(),
    yadcfoptions=invites_yadcf_options,
    pagename='Invites',
    endpoint='admin.invites',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/invites',
    dbmapping=invites_dbmapping,
    formmapping=invites_formmapping,
    checkrequired=True,
    tableidtemplate ='invites-{{ meeting_id }}-{{ agendaitem_id }}',
    clientcolumns=[
        {'data': 'purpose', 'name': 'purpose', 'label': 'Meeting',
         'type': 'readonly',
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'readonly',
         '_ColumnDT_args' :
             {'sqla_expr': func.date_format(Meeting.date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'}
         },
        {'data': 'name', 'name': 'name', 'label': 'Name',
         'type': 'readonly',
         },
        {'data': 'email', 'name': 'email', 'label': 'Email',
         'type': 'readonly',
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
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
invites.register()

##########################################################################################
# actionitems endpoint
###########################################################################################

actionitems_dbattrs = 'id,interest_id,meeting_id,agendaitem_id,meeting.purpose,meeting.date,action,comments,status,assignee,update_time,updated_by'.split(',')
actionitems_formfields = 'rowid,interest_id,meeting_id,agendaitem_id,purpose,date,action,comments,status,assignee,update_time,updated_by'.split(',')
actionitems_dbmapping = dict(zip(actionitems_dbattrs, actionitems_formfields))
actionitems_formmapping = dict(zip(actionitems_formfields, actionitems_dbattrs))
# actionitems_formmapping['date'] = lambda dbrow: isodate.dt2asc(dbrow.meeting.date)

class ActionItemsView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()

        # add filters if requested
        self.queryparams['meeting_id'] = request.args.get('meeting_id', None)
        self.queryparams['agendaitem_id'] = request.args.get('agendaitem_id', None)

        # remove empty parameters from query filters
        delfields = []
        for field in self.queryparams:
            if self.queryparams[field] == None:
                delfields.append(field)
        for field in delfields:
            del self.queryparams[field]

        # optionally determine filter for show actions since
        show_actions_since = request.args.get('show_actions_since', None)
        if show_actions_since:
            show_actions_since = dtrender.asc2dt(show_actions_since)
            self.queryfilters = [ActionItem.update_time >= show_actions_since]

    def _get_localuser(self):
        # TODO: process request.args to see if different user is needed
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

actionitems_filters = filtercontainerdiv()
actionitems_filters += filterdiv('actionitems-external-filter-date', 'Date')
actionitems_filters += filterdiv('actionitems-external-filter-assignee', 'Assignee')
actionitems_filters += filterdiv('actionitems-external-filter-status', 'Status')

actionitems_yadcf_options = [
    yadcfoption('date:name', 'actionitems-external-filter-date', 'range_date'),
    yadcfoption('assignee.name:name', 'actionitems-external-filter-assignee', 'multi_select', placeholder='Select names', width='200px'),
    yadcfoption('status:name', 'actionitems-external-filter-status', 'select', placeholder='Select', width='100px'),
]

actionitems = ActionItemsView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=ActionItem,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    pretablehtml=actionitems_filters.render(),
    yadcfoptions=actionitems_yadcf_options,
    pagename='Action Items',
    endpoint='admin.actionitems',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/actionitems',
    dbmapping=actionitems_dbmapping,
    formmapping=actionitems_formmapping,
    checkrequired=True,
    tableidtemplate ='actionitems-{{ meeting_id }}-{{ agendaitem_id }}',
    clientcolumns=[
        {'data': 'purpose', 'name': 'purpose', 'label': 'Meeting',
         'type': 'readonly',
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'readonly',
         '_ColumnDT_args' :
             {'sqla_expr': func.date_format(Meeting.date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'}
         },
        {'data': 'action', 'name': 'action', 'label': 'Action',
         'className': 'field_req',
         'type': 'textarea',
         'fieldInfo': 'description of action item',
         },
        {'data': 'comments', 'name': 'comments', 'label': 'Comments',
         'type': 'ckeditorInline',
         'fieldInfo': 'details of action item (if needed), notes about progress, and resolution - note won\'t be printed in agenda',
         'visible': False,
         },
        {'data': 'assignee', 'name': 'assignee', 'label': 'Assignee',
         'className': 'field_req',
         '_treatment': {
             'relationship': {'fieldmodel': LocalUser, 'labelfield': 'name',
                              'formfield': 'assignee', 'dbfield': 'assignee',
                              'queryparams': lambda: {'active':True, 'interest':localinterest_query_params()['interest']},
                              'uselist': False}}
         },
        {'data': 'status', 'name': 'status', 'label': 'Status',
         'type': 'select2',
         'options': action_all,
         'ed': {'def': ACTION_STATUS_OPEN}
         },
        # meeting_id and agendaitem_id are required for tying to meeting view row
        # put these last so as not to confuse indexing between datatables (python vs javascript)
        {'data': 'meeting_id', 'name': 'meeting_id', 'label': 'Meeting ID',
         'type': 'hidden',
         'visible': False,
         },
        {'data': 'agendaitem_id', 'name': 'agendaitem_id', 'label': 'Agenda Item ID',
         'type': 'hidden',
         'visible': False,
         },
    ],
    serverside=True,
    idSrc='rowid',
    buttons=[
        'create',
        'editRefresh',
        'csv'
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
actionitems.register()

##########################################################################################
# motionsvote endpoint
###########################################################################################

motionvotes_dbattrs = 'id,interest_id,meeting.date,motion.motion,user.name,vote,meeting_id,motion_id'.split(',')
motionvotes_formfields = 'rowid,interest_id,date,motion,user,vote,meeting_id,motion_id'.split(',')
motionvotes_dbmapping = dict(zip(motionvotes_dbattrs, motionvotes_formfields))
motionvotes_formmapping = dict(zip(motionvotes_formfields, motionvotes_dbattrs))
# motionsvote_formmapping['date'] = lambda dbrow: isodate.dt2asc(dbrow.meeting.date)

class MotionVotesView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()

        # add filters if requested
        self.queryparams['meeting_id'] = request.args.get('meeting_id', None)
        self.queryparams['motion_id'] = request.args.get('motion_id', None)

        # remove empty parameters from query filters
        delfields = []
        for field in self.queryparams:
            if self.queryparams[field] == None:
                delfields.append(field)
        for field in delfields:
            del self.queryparams[field]

motionvotes_filters = filtercontainerdiv()
motionvotes_filters += filterdiv('motionvotes-external-filter-date', 'Date')

motionvotes_yadcf_options = [
    yadcfoption('date:name', 'motionvotes-external-filter-date', 'range_date'),
]

motionvotes = MotionVotesView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=MotionVote,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    pretablehtml=motionvotes_filters.render(),
    yadcfoptions=motionvotes_yadcf_options,
    pagename='Motion Votes',
    endpoint='admin.motionvotes',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/motionvotes',
    dbmapping=motionvotes_dbmapping,
    formmapping=motionvotes_formmapping,
    checkrequired=True,
    tableidtemplate ='motionvotes-{{ meeting_id }}-{{ motion_id }}',
    clientcolumns=[
        {'data': 'motion', 'name': 'motion', 'label': 'Motion',
         'type': 'readonly',
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'readonly',
         '_ColumnDT_args' :
             {'sqla_expr': func.date_format(Meeting.date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'}
         },
        {'data': 'user', 'name': 'user', 'label': 'Member',
         'type':'readonly',
         # onclause required when ambiguous foreign keys in a subsequent join
         'onclause': MotionVote.user_id == LocalUser.id,
         },
        {'data': 'vote', 'name': 'vote', 'label': 'Vote',
         'type': 'select2',
         'options': motionvote_all,
         },
        # meeting_id and motion_id are required for tying to motion view row
        # put these last so as not to confuse indexing between datatables (python vs javascript)
        {'data': 'meeting_id', 'name': 'meeting_id', 'label': 'Meeting ID',
         'type': 'hidden',
         'visible': False,
         },
        {'data': 'motion_id', 'name': 'motion_id', 'label': 'Motion ID',
         'type': 'hidden',
         'visible': False,
         },
    ],
    serverside=True,
    idSrc='rowid',
    buttons=[
        'create',
        'editRefresh',
        'csv'
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
motionvotes.register()

##########################################################################################
# motions endpoint
###########################################################################################

motions_dbattrs = 'id,interest_id,meeting.purpose,meeting.date,motion,comments,status,meeting_id,agendaitem_id,mover,seconder'.split(',')
motions_formfields = 'rowid,interest_id,purpose,date,motion,comments,status,meeting_id,agendaitem_id,mover,seconder'.split(',')
motions_dbmapping = dict(zip(motions_dbattrs, motions_formfields))
motions_formmapping = dict(zip(motions_formfields, motions_dbattrs))
# motions_formmapping['date'] = lambda dbrow: isodate.dt2asc(dbrow.meeting.date)

class MotionsView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()

        # add filters if requested
        self.queryparams['meeting_id'] = request.args.get('meeting_id', None)
        self.queryparams['agendaitem_id'] = request.args.get('agendaitem_id', None)

        # remove empty parameters from query filters
        delfields = []
        for field in self.queryparams:
            if self.queryparams[field] == None:
                delfields.append(field)
        for field in delfields:
            del self.queryparams[field]

    def updatetables(self, rows):
        for row in rows:
            context = {
                'meeting_id': row['meeting_id'],
                'agendaitem_id': row['agendaitem_id'],
                'motion_id': row['rowid'],
            }

            tablename = 'motionvotes'
            tables = [
                {
                    'name': tablename,
                    'label': 'Votes',
                    'url': rest_url_for('admin.motionvotes', interest=g.interest, urlargs=context),
                    'tableid': self.childtables[tablename]['table'].tableid(**context)
                }]

            row['tables'] = tables

            tableid = self.tableid(**context)
            if tableid:
                row['tableid'] = tableid

    def editor_method_postcommit(self, form):
        # this is here in case invites changed during edit action
        # self.updateinvites()
        self.updatetables(self._responsedata)

    def open(self):
        super().open()
        self.updatetables(self.output_result['data'])

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
        get_tags_users(meeting.votetags, users)

        ## retrieve the motion we've just created
        motion = Motion.query.filter_by(id=self.created_id).one()

        ## for each user, create a voting record
        for user in users:
            invite = Invite.query.filter_by(meeting=meeting, user=user).one_or_none()

            # this user wasn't invited to the meeting
            if not invite: continue

            vote = MotionVote(interest=localinterest(), meeting=meeting, motion=motion, user=user)
            # if user is attending the meeting, assume they approve, otherwise no vote
            if invite.attended:
                vote.vote = MOTIONVOTE_STATUS_APPROVED
            else:
                vote.vote = MOTIONVOTE_STATUS_NOVOTE
            db.session.add(vote)
        # db.session.commit()

        return output

motions_filters = filtercontainerdiv()
motions_filters += filterdiv('motions-external-filter-date', 'Date')

motions_yadcf_options = [
    yadcfoption('date:name', 'motions-external-filter-date', 'range_date'),
]

def voting_members():
    """
    return list containing sql expression which finds voting members for this meeting

    :return: LocalUsers sql expression
    """
    meeting_id = request.args.get('meeting_id', None)

    # if we're outside of meeting, not allowed to edit or create anyway, so this should be ok
    if not meeting_id:
        return []

    meeting = Meeting.query.filter_by(id=meeting_id).one()
    votetags = meeting.votetags
    localusers = set()
    get_tags_users(votetags, localusers)
    return [LocalUser.id.in_([lu.id for lu in localusers])]

# need aliased because LocalUser referenced twice within motions
localuser_alias = aliased(LocalUser)

motions = MotionsView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Motion,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    pretablehtml=motions_filters.render(),
    yadcfoptions=motions_yadcf_options,
    pagename='Motions',
    endpoint='admin.motions',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/motions',
    dbmapping=motions_dbmapping,
    formmapping=motions_formmapping,
    checkrequired=True,
    tableidtemplate ='motions-{{ meeting_id }}-{{ agendaitem_id }}',
    clientcolumns=[
        {'data':'', # needs to be '' else get exception converting options from meetings render_template
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
        {'data': 'purpose', 'name': 'purpose', 'label': 'Meeting',
         'type': 'readonly',
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'readonly',
         '_ColumnDT_args' :
             {'sqla_expr': func.date_format(Meeting.date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'}
         },
        {'data': 'motion', 'name': 'motion', 'label': 'Motion',
         'type': 'ckeditorInline',
         },
        {'data': 'comments', 'name': 'comments', 'label': 'Comments',
         'type': 'ckeditorInline',
         },
        {'data': 'status', 'name': 'status', 'label': 'Status',
         'type': 'select2',
         'options': motion_all,
         'ed': {'def': MOTION_STATUS_OPEN}
         },
        {'data': 'mover', 'name': 'mover', 'label': 'Mover',
         'className': 'field_req',
         'visible': False,
         '_treatment': {
             'relationship': {'fieldmodel': LocalUser, 'labelfield': 'name',
                              'formfield': 'mover', 'dbfield': 'mover',
                              'queryparams': lambda: {'active':True, 'interest':localinterest_query_params()['interest']},
                              'queryfilters': voting_members,
                              # onclause is required for serverside=True tables with ambiguous foreign keys
                              'onclause': Motion.mover_id == LocalUser.id,
                              'uselist': False}}
         },
        {'data': 'seconder', 'name': 'seconder', 'label': 'Seconder',
         'className': 'field_req',
         'visible': False,
         '_treatment': {
             'relationship': {'fieldmodel': localuser_alias, 'labelfield': 'name',
                              'formfield': 'seconder', 'dbfield': 'seconder',
                              'queryparams': lambda: {'active':True, 'interest':localinterest_query_params()['interest']},
                              'queryfilters': voting_members,
                              'onclause': Motion.seconder_id == localuser_alias.id,
                              'uselist': False}}
         },
        # meeting_id and agendaitem_id are required for tying to meeting view row
        # put these last so as not to confuse indexing between datatables (python vs javascript)
        {'data': 'meeting_id', 'name': 'meeting_id', 'label': 'Meeting ID',
         'type': 'hidden',
         'visible': False,
         },
        {'data': 'agendaitem_id', 'name': 'agendaitem_id', 'label': 'Agenda Item ID',
         'type': 'hidden',
         'visible': False,
         },
    ],
    childrowoptions= {
        'template': 'motion-child-row.njk',
        'showeditor': True,
        'group': 'interest',
        'groupselector': '#metanav-select-interest',
        'childelementargs': [
            {'name':'motionvotes', 'type':CHILDROW_TYPE_TABLE, 'table':motionvotes,
                 'args':{
                     'buttons': ['create', 'editRefresh', 'remove'],
                     'columns': {
                         'datatable': {
                             # uses data field as key
                             'date': {'visible': False}, 'motion': {'visible': False},
                         },
                         'editor': {
                             # uses name field as key
                             'date': {'type': 'hidden'}, 'motion': {'type': 'hidden'},
                         },
                     },
                     'inline' : {
                         # uses name field as key; value is used for editor.inline() options
                         'vote': {'submitOnBlur': True}
                     },
                     'updatedtopts': {
                         'dom': 'frt',
                         'paging': False,
                     },
                 }
             },
        ],
    },
    serverside=True,
    idSrc='rowid',
    buttons=[
        # 'create',
        # 'editChildRowRefresh',
        'csv'
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
motions.register()

##########################################################################################
# meeting endpoint
###########################################################################################

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

            tableid = self.tableid(**context)
            if tableid:
                row['tableid'] = tableid

    def editor_method_postcommit(self, form):
        # # this is here in case invites changed during edit action
        # self.updateinvites()
        self.postprocessrows(self._responsedata)

    def open(self):
        super().open()
        self.postprocessrows(self.output_result['data'])

    @_editormethod(checkaction='create,checkinvites,sendinvites,refresh', formrequest=True)
    def post(self):
        action = get_request_action(request.form)
        if action == 'checkinvites':
            invitestates, invites = get_invites(request.args['meeting_id'])
            self._responsedata = []
            self.responsekeys['checkinvites'] = invitestates
        elif action == 'sendinvites':
            agendaitem = generateinvites(request.args['meeting_id'])
            thisrow = self.dte.get_response_data(agendaitem)
            self._responsedata = [thisrow]
        else:
            # note we're already wrapped with _editormethod, don't wrap again
            super().do_post()

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

    return pretablehtml.render()


# for parent / child editing see
#   https://datatables.net/blog/2019-01-11#DataTables-Javascript
#   http://live.datatables.net/bihawepu/1/edit
meeting = MeetingView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=AgendaItem,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    pagename='Meeting',
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
        {'data':None,
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
         'type': 'ckeditorInline',
         'visible': False,
         'opts': {
             'toolbar': ["heading", "|", "bold", "italic", "link", "bulletedList", "numberedList",
                         "|", "indent", "outdent", "|", "blockQuote", "insertTable", "undo", "redo"]
         }
         },
        {'data': 'agendaheading', 'name': 'agendaheading', 'label': 'Agenda Heading',
         'fieldInfo': 'heading under which this position is shown in agenda',
         '_treatment': {
             'relationship': {'fieldmodel': AgendaHeading, 'labelfield': 'heading', 'formfield': 'agendaheading',
                              'dbfield': 'agendaheading', 'uselist': False,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'discussion', 'name': 'discussion', 'label': 'Discussion',
         'type': 'ckeditorInline',
         'visible': False,
         'opts': {
             'toolbar': ["heading", "|", "bold", "italic", "link", "bulletedList", "numberedList",
                         "|", "indent", "outdent", "|", "blockQuote", "insertTable", "undo", "redo"]
         }
         },
        {'data': 'is_hidden', 'name': 'is_hidden', 'label': 'Hide',
         '_treatment': {'boolean': {'formfield': 'is_hidden', 'dbfield': 'is_hidden'}},
         'visible': False,
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
            {'name':'invites', 'type':CHILDROW_TYPE_TABLE, 'table':invites,
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
            {'name': 'actionitems', 'type': CHILDROW_TYPE_TABLE, 'table': actionitems,
             'args': {
                 'buttons': ['create', 'editRefresh', 'remove'],
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
            {'name': 'motions', 'type': CHILDROW_TYPE_TABLE, 'table': motions,
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
        ],
    },
    serverside=True,
    idSrc='rowid',
    # need function here else rest_url_for gives RuntimeError (no app context)
    buttons=lambda: [
        # 'editor' gets eval'd to editor instance
        {'extend':'newInvites', 'editor': {'eval': 'editor'}},
        {'text':'Generate Docs',
         'action': {'eval': 'meeting_generate_docs("{}")'.format(rest_url_for('admin.meetinggendocs', interest=g.interest))}},
        'create',
        'editChildRowRefresh',
        'remove',
        'csv'
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [['order:name','asc']],
        'rowReorder': {
            'dataSrc': 'order',
            'selector': 'td.reorder',
            'snapX': True,
        },

},
)
meeting.register()

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
            output_result = {'status' : 'fail', 'error': 'exception occurred:\n{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_meetinggendocs/rest', view_func=MeetingGenDocsApi.as_view('meetinggendocs'), methods=['POST'])


##########################################################################################
# meetingstatus endpoint
###########################################################################################

class MeetingStatusView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        self.queryparams['has_status_report'] = True

    @_editormethod(checkaction='edit', formrequest=True)
    def put(self, thisid):
        # allow multirow editing, i.e., to send emails for multiple selected positions
        theseids = thisid.split(',')
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
            users |= set(position.users)
            positions.append(position)

        # send reminder email to each user
        self.responsekeys = {'reminded': [], 'newinvites': []}
        for user in users:
            reminder = generatereminder(request.args['meeting_id'], user, positions)
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

def meetingstatus_getusers(row):
    meeting_id = request.args['meeting_id']
    users = []
    for user in row.users:
        invite = Invite.query.filter_by(meeting_id=meeting_id, user=user).one_or_none()
        # lastreminder should always be present, but maybe not for testing
        if invite and invite.lastreminder:
            users.append('{} ({})'.format(user.name, isodate.dt2asc(invite.lastreminder)))
        else:
            users.append(user.name)
    return ', '.join(users)

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

meetingstatus = MeetingStatusView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Position,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    pretablehtml=meetingstatus_pretablehtml,
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    yadcfoptions=meetingstatus_yadcf_options,
    pagename='Meeting Status',
    endpoint='admin.meetingstatus',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/meetingstatus',
    dbmapping=meetingstatus_dbmapping,
    formmapping=meetingstatus_formmapping,
    checkrequired=True,
    createfieldvals=meetingcreatefieldvals,
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
    buttons=[
        {
            'extend':'edit',
            'editor': {'eval':'editor'},
            'text': 'Send Reminders',
            'action': {'eval':'meeting_sendreminders(editor)'}
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
meetingstatus.register()

##########################################################################################
# agendaheadings endpoint
###########################################################################################

agendaheadings_dbattrs = 'id,interest_id,heading,positions'.split(',')
agendaheadings_formfields = 'rowid,interest_id,heading,positions'.split(',')
agendaheadings_dbmapping = dict(zip(agendaheadings_dbattrs, agendaheadings_formfields))
agendaheadings_formmapping = dict(zip(agendaheadings_formfields, agendaheadings_dbattrs))

agendaheadings = DbCrudApiInterestsRolePermissions(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=AgendaHeading,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
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
agendaheadings.register()

