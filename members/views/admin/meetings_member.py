'''
meetings_member - handling for meetings member
====================================================================================
'''

# standard
from datetime import date, datetime
from traceback import format_exc, format_exception_only

# pypi
from flask import request, flash, g, jsonify, current_app
from flask_security import current_user, logout_user, login_user
from flask.views import MethodView
from sqlalchemy import func
from dominate.tags import div, h1

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Position, Invite, Meeting, AgendaItem, ActionItem
from ...model import DiscussionItem
from ...model import invite_response_all, INVITE_RESPONSE_ATTENDING, INVITE_RESPONSE_NO_RESPONSE, action_all
from .meetings_common import MemberStatusReportBase
from .viewhelpers import localuser2user, user2localuser, localinterest
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.timeu import asctime
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption

isodate = asctime('%Y-%m-%d')
displaytime = asctime('%Y-%m-%d %H:%M')

class ParameterError(Exception): pass



##########################################################################################
# memberstatusreport endpoint
##########################################################################################

def get_invite_response(dbrow):
    invite = dbrow.invite
    return invite.response

class MemberStatusReportView(MemberStatusReportBase):
    # remove auth_required() decorator
    decorators = []

    def permission(self):
        invitekey = request.args.get('invitekey', None)
        if invitekey:
            permitted = True
            invite = Invite.query.filter_by(invitekey=invitekey).one()
            user = localuser2user(invite.user)
            self.meeting = invite.meeting
            self.interest = self.meeting.interest

            if current_user != user:
                # log out and in automatically
                # see https://flask-security-too.readthedocs.io/en/stable/api.html#flask_security.login_user
                logout_user()
                login_user(user)
                db.session.commit()
                flash('you have been automatically logged in as {}'.format(current_user.name))

            # at this point, if current_user has the target user (may have been changed by invitekey)
            # check role permissions, permitted = True (from above) unless determined otherwise
            roles_accepted = [ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER]
            allowed = False
            for role in roles_accepted:
                if current_user.has_role(role):
                    allowed = True
                    break
            if not allowed:
                permitted = False

        # no invitekey, not permitted
        else:
            permitted = False

        return permitted

    def beforequery(self):
        # set user based on invite key
        invite = self.get_invite()
        self.theuser = localuser2user(invite.user)
        super().beforequery()
        self.queryparams['meeting_id'] = self.meeting.id
        self.queryparams['invite_id'] = invite.id

    def get_invite(self):
        meeting = self.get_meeting()
        invite = Invite.query.filter_by(meeting_id=meeting.id, user_id=user2localuser(current_user).id).one_or_none()
        if not invite:
            raise ParameterError('no invitation found for this meeting/user combination')
        return invite

    def format_pretablehtml(self):
        meeting = self.get_meeting()

        html = div()
        with html:
            self.instructions()
            h1('{} - {} - {}'.format(meeting.date, meeting.purpose, current_user.name), _class='TextCenter')

        return html.render()


memberstatusreport = MemberStatusReportView(
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-member-guide.html'},
    pagename='My Status Report',
    endpoint='admin.memberstatusreport',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/memberstatusreport',
)
memberstatusreport.register()

##########################################################################################
# mymeetings endpoint
##########################################################################################

class MyMeetingsView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        self.queryparams['user'] = user2localuser(current_user)

def mymeetings_attended(row):
    today = date.today()
    if row.meeting.date >= today:
        return ''
    else:
        return 'yes' if row.attended else 'no'

mymeetings_dbattrs = 'id,interest_id,meeting.purpose,meeting.date,response,attended,invitekey,meeting.gs_agenda,meeting.gs_status,meeting.gs_minutes'.split(',')
mymeetings_formfields = 'rowid,interest_id,purpose,date,response,attended,invitekey,gs_agenda,gs_status,gs_minutes'.split(',')
mymeetings_dbmapping = dict(zip(mymeetings_dbattrs, mymeetings_formfields))
mymeetings_formmapping = dict(zip(mymeetings_formfields, mymeetings_dbattrs))
mymeetings_formmapping['date'] = lambda row: isodate.dt2asc(row.meeting.date)
mymeetings_formmapping['attended'] = mymeetings_attended
mymeetings_formmapping['gs_agenda'] = lambda row: row.meeting.gs_agenda if row.meeting.gs_agenda else ''
mymeetings_formmapping['gs_status'] = lambda row: row.meeting.gs_status if row.meeting.gs_status else ''
mymeetings_formmapping['gs_minutes'] = lambda row: row.meeting.gs_minutes if row.meeting.gs_minutes else ''

mymeetings = MyMeetingsView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Invite,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-member-guide.html'},
    pagename='My Meetings',
    endpoint='admin.mymeetings',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/mymeetings',
    dbmapping=mymeetings_dbmapping,
    formmapping=mymeetings_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': '',  # needs to be '' else get exception converting options from meetings render_template
         # TypeError: '<' not supported between instances of 'str' and 'NoneType'
         'name': 'view-control',
         'className': 'view-control shrink-to-fit',
         'orderable': False,
         'defaultContent': '',
         'label': '',
         'type': 'hidden',  # only affects editor modal
         'title': 'View',
         'render': {'eval': 'render_icon("fas fa-eye")'},
         },
        {'data': 'date', 'name': 'date', 'label': 'Meeting Date',
         'type': 'readonly'
         },
        {'data': 'purpose', 'name': 'purpose', 'label': 'Meeting Purpose',
         'type': 'readonly'
         },
        {'data': 'response', 'name': 'response', 'label': 'RSVP',
         'type': 'readonly'
         },
        {'data': 'attended', 'name': 'attended', 'label': 'Attended',
         'className': 'TextCenter',
         'type': 'readonly',
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
        {'data': 'invitekey', 'name': 'invitekey', 'label': 'My Status Report',
         'type': 'hidden',
         'dt': {'visible': False},
         },
    ],
    idSrc='rowid',
    buttons=[
        {
            'extend': 'edit',
            'name': 'view-status',
            'text': 'My Status Report',
            'action': {'eval': 'mystatus_statusreport'},
            'className': 'Hidden',
        },
        'csv',
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [['date:name', 'desc']],
    },
)
mymeetings.register()

##########################################################################################
# myactionitems endpoint
##########################################################################################

class MyActionItemsView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        self.queryparams['assignee'] = user2localuser(current_user)

myactionitems_dbattrs = 'id,interest_id,action,status,comments,meeting.date,agendaitem.title,agendaitem.agendaitem,update_time,updated_by'.split(',')
myactionitems_formfields = 'rowid,interest_id,action,status,comments,date,agendatitle,agendatext,update_time,updated_by'.split(',')
myactionitems_dbmapping = dict(zip(myactionitems_dbattrs, myactionitems_formfields))
myactionitems_formmapping = dict(zip(myactionitems_formfields, myactionitems_dbattrs))
myactionitems_formmapping['date'] = lambda row: isodate.dt2asc(row.meeting.date) if row.meeting else ''
# todo: should this be in tables.py? but see https://github.com/louking/loutilities/issues/25
myactionitems_dbmapping['meeting.date'] = '__readonly__'
myactionitems_dbmapping['agendaitem.title'] = '__readonly__'
myactionitems_dbmapping['agendaitem.agendaitem'] = '__readonly__'
myactionitems_formmapping['update_time'] = lambda row: displaytime.dt2asc(row.update_time)
myactionitems_dbmapping['update_time'] = lambda form: datetime.now()
myactionitems_formmapping['updated_by'] = lambda row: LocalUser.query.filter_by(id=row.updated_by).one().name
myactionitems_dbmapping['updated_by'] = lambda form: user2localuser(current_user).id

agendaitems_filters = filtercontainerdiv()
agendaitems_filters += filterdiv('agendaitems-external-filter-status', 'Status')

agendaitems_yadcf_options = [
    yadcfoption('status:name', 'agendaitems-external-filter-status', 'multi_select', placeholder='Select statuses', width='200px'),
]

myactionitems = MyActionItemsView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=ActionItem,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-member-guide.html'},
    pretablehtml=agendaitems_filters.render(),
    yadcfoptions=agendaitems_yadcf_options,
    pagename='My Action Items',
    endpoint='admin.myactionitems',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/myactionitems',
    dbmapping=myactionitems_dbmapping,
    formmapping=myactionitems_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'date', 'name': 'date', 'label': 'Meeting Date',
         'type': 'readonly'
         },
        {'data': 'action', 'name': 'action', 'label': 'Action',
         'type': 'readonly'
         },
        {'data': 'agendatitle', 'name': 'agendatitle', 'label': 'Agenda Item',
         'type': 'readonly',
         'dt': {'visible': False},
         },
        {'data': 'agendatext', 'name': 'agendatext', 'label': '',
         'type': 'display',
         'dt': {'visible': False},
         },
        {'data': 'status', 'name': 'status', 'label': 'Status',
         'type': 'select2',
         'options': action_all,
         },
        {'data': 'comments', 'name': 'comments', 'label': 'Progress / Resolution',
         'type': 'ckeditorClassic',
         'fieldInfo': 'record your progress or how this was resolved',
         'dt': {'visible': False},
         },
        {'data': 'update_time', 'name': 'update_time', 'label': 'Last Update',
         'type': 'hidden',
         },
        {'data': 'updated_by', 'name': 'updated_by', 'label': 'Updated By',
         'type': 'hidden',
         },
    ],
    idSrc='rowid',
    buttons=[
        'editRefresh',
        'csv',
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [['date:name', 'desc']],
    },
)
myactionitems.register()

##########################################################################################
# mymeetingrsvp api endpoint
##########################################################################################

class MyMeetingRsvpApi(MethodView):

    def __init__(self):
        self.roles_accepted = [ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER]

    def permission(self):
        '''
        determine if current user is permitted to use the view
        '''
        # adapted from loutilities.tables.DbCrudApiRolePermissions
        allowed = False

        # must have invitekey query arg
        if request.args.get('invitekey', False):
            for role in self.roles_accepted:
                if current_user.has_role(role):
                    allowed = True
                    break

        return allowed

    def get(self):
        try:
            invitekey = request.args['invitekey']
            invite = Invite.query.filter_by(invitekey=invitekey).one()
            options = [r for r in invite_response_all
                       # copy if no response yet, or (if a response) anything but no response
                       if invite.response == INVITE_RESPONSE_NO_RESPONSE or r != INVITE_RESPONSE_NO_RESPONSE]
            return jsonify(status='success', response=invite.response, options=options)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:\n{}'.format(exc)}
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

            invitekey = request.args['invitekey']
            response = request.form['response']

            invite = Invite.query.filter_by(invitekey=invitekey).one()
            invite.response = response
            invite.attended = response == INVITE_RESPONSE_ATTENDING
            db.session.commit()

            output_result = {'status' : 'success'}
            return jsonify(output_result)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:\n{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_mymeetingrsvp/rest', view_func=MyMeetingRsvpApi.as_view('_mymeetingrsvp'),
                methods=['GET', 'POST'])


