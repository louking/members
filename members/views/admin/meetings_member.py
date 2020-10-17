'''
meetings_member - handling for meetings member
====================================================================================
'''

# standard
from datetime import date, datetime

# pypi
from flask import request, flash, g
from flask_security import current_user, logout_user, login_user
from sqlalchemy import func
from dominate.tags import div, h1, ol, li, p, em, strong, a
from dominate.util import text
from slugify import slugify

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Position, Invite, Meeting, AgendaItem, ActionItem
from ...model import MemberStatusReport, StatusReport, DiscussionItem
from ...model import invite_response_all, action_all
from .viewhelpers import localuser2user, user2localuser, localinterest
from loutilities.tables import rest_url_for, CHILDROW_TYPE_TABLE
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.timeu import asctime
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption

isodate = asctime('%Y-%m-%d')
displaytime = asctime('%Y-%m-%d %H:%M')

class ParameterError(Exception): pass


###########################################################################################
# memberdiscussions endpoint
###########################################################################################

memberdiscussions_dbattrs = 'id,interest_id,meeting.purpose,meeting.date,discussiontitle,agendaitem.agendaitem,'\
                            'agendaitem.is_hidden,agendaitem.hidden_reason,position_id,meeting_id,statusreport_id,agendaitem_id'.split(',')
memberdiscussions_formfields = 'rowid,interest_id,purpose,date,discussiontitle,agendaitem,'\
                               'is_hidden,hidden_reason,position_id,meeting_id,statusreport_id,agendaitem_id'.split(',')
memberdiscussions_dbmapping = dict(zip(memberdiscussions_dbattrs, memberdiscussions_formfields))
memberdiscussions_formmapping = dict(zip(memberdiscussions_formfields, memberdiscussions_dbattrs))

class MemberDiscussionsView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()

        # add meeting_id to filters if requested
        self.queryparams['meeting_id'] = request.args.get('meeting_id', None)
        self.queryfilters = [DiscussionItem.agendaitem_id == AgendaItem.id]

        statusreport_id = request.args.get('statusreport_id', None)
        if statusreport_id:
            self.queryparams['statusreport_id'] = statusreport_id
            self.queryfilters += [AgendaItem.statusreport_id == statusreport_id]

            # remove empty parameters from query filters
        delfields = []
        for field in self.queryparams:
            if self.queryparams[field] == None:
                delfields.append(field)
        for field in delfields:
            del self.queryparams[field]

    def createrow(self, formdata):
        meeting_id = formdata['meeting_id']

        agendatitle = formdata['discussiontitle']
        if 'position_id' in formdata and formdata['position_id']:
            position = Position.query.filter_by(id=formdata['position_id']).one()
            agendatitle += ' [{} / {}]'.format(current_user.name, position.position)
            agendaheading = position.agendaheading
        else:
            agendatitle += ' [{}]'.format(current_user.name)
            agendaheading = None

        # todo: should this be a critical region because of order? possibly that doesn't matter
        # determine current order number, in case we need to add records
        max = db.session.query(func.max(AgendaItem.order)).filter_by(meeting_id=meeting_id).one()
        # if AgendaItem records configured, use current max + 1
        order = max[0] + 1
        agendaitem = AgendaItem(
            interest=localinterest(),
            meeting_id=formdata['meeting_id'],
            statusreport_id=formdata['statusreport_id'],
            title=agendatitle,
            agendaheading=agendaheading,
            order=order,
        )
        db.session.add(agendaitem)

        # force agendaitem to be the one just created
        # need to do this instead of calling super.createrow() because of chicken/egg problem for access
        # of agendaitem during set_dbrow()
        dbrow = DiscussionItem(interest=localinterest(), agendaitem=agendaitem)
        self.dte.set_dbrow(formdata, dbrow)
        self.db.session.add(dbrow)
        self.db.session.flush()
        self.created_id = dbrow.id

        # prepare response
        thisrow = self.dte.get_response_data(dbrow)
        return thisrow

    def deleterow(self, thisid):
        """
        check if date for meeting has passed before allowing discussion deletion

        :param thisid: id for row
        :return: empty list
        """
        discussionitem = DiscussionItem.query.filter_by(id=thisid).one()
        today = date.today()
        if discussionitem.meeting.date < today:
            self._error = 'Cannot delete discussion item after meeting is over'
            raise ParameterError(self._error)

        # delete agenda item if it exists (it should but safe to check)
        if discussionitem.agendaitem:
            db.session.delete(discussionitem.agendaitem)

        return super().deleterow(thisid)

    def postprocessrows(self, rows):
        for row in rows:
            agendaitem = AgendaItem.query.filter_by(id=row['agendaitem_id']).one()
            if agendaitem.is_hidden:
                row['DT_RowClass'] = 'hidden-row'
            else:
                row['hidden_reason'] = ''

    def editor_method_postcommit(self, form):
        self.postprocessrows(self._responsedata)

    def open(self):
        super().open()
        self.postprocessrows(self.output_result['data'])


memberdiscussions = MemberDiscussionsView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=DiscussionItem,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    pagename='Discussion Items',
    endpoint='admin.memberdiscussions',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/memberdiscussions',
    dbmapping=memberdiscussions_dbmapping,
    formmapping=memberdiscussions_formmapping,
    checkrequired=True,
    tableidtemplate ='memberdiscussions-{{ meeting_id }}-{{ statusreport_id }}',
    clientcolumns=[
        {'data': 'purpose', 'name': 'purpose', 'label': 'Meeting',
         'type': 'readonly',
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'readonly',
         '_ColumnDT_args' :
             {'sqla_expr': func.date_format(Meeting.date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'}
         },
        {'data': 'discussiontitle', 'name': 'discussiontitle', 'label': 'Discussion Title',
         },
        {'data': 'agendaitem', 'name': 'agendaitem', 'label': 'Discussion Details',
         'type':'ckeditorInline',
         },
        {'data': 'hidden_reason', 'name': 'hidden_reason', 'label': 'Reason for Hiding',
         'type':'readonly',
         },
        # meeting_id and statusreport_id are required for tying to meeting view row
        # put these last so as not to confuse indexing between datatables (python vs javascript)
        {'data': 'meeting_id', 'name': 'meeting_id', 'label': 'Meeting ID',
         'type': 'hidden',
         'visible': False,
         },
        {'data': 'statusreport_id', 'name': 'statusreport_id', 'label': 'Status Report ID',
         'type': 'hidden',
         'visible': False,
         },
        {'data': 'position_id', 'name': 'position_id', 'label': 'Position ID',
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
memberdiscussions.register()


##########################################################################################
# memberstatusreport endpoint
##########################################################################################

class MemberStatusreportView(DbCrudApiInterestsRolePermissions):
    # remove auth_required() decorator
    decorators = []

    def __init__(self, **kwargs):
        args = dict(
            pretablehtml = self.format_pretablehtml
        )
        args.update(kwargs)

        # initialize inherited class, and a couple of attributes
        super().__init__(**args)

        # this causes self.dte.get_response_data to execute postprocessrow() to transform returned response
        self.dte.set_response_hook(self.postprocessrow)

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

    def get_meeting(self):
        invitekey = request.args.get('invitekey', None)
        if invitekey:
            invite = Invite.query.filter_by(invitekey=invitekey).one()
            meeting = invite.meeting
        else:
            meeting_id = request.args.get('meeting_id', None)
            if not meeting_id:
                raise ParameterError('meeting_id needs to be specified in URL')

            meeting = Meeting.query.filter_by(id=meeting_id).one()

        return meeting

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
            h1('{} - {} - {}'.format(meeting.date, meeting.purpose, current_user.name), _class='TextCenter')

            # id referenced from beforedatatables.js meeting_send_email()
            with div(id='mystatus-instructions', style='display: none;'):
                p('Please respond as follows:')
                with ol():
                    li('RSVP to the meeting by clicking/editing the first row')
                    li('Provide Status Reports for each of your positions by clicking/editing subsequent rows')
                    with li():
                        em('Optionally')
                        text(' add a Status Report for something outside your assigned position by clicking New')
                with p():
                    text('If you would like to add a discussion item to the meeting agenda, click on "New" in the '
                         'Discussion Item ')
                    strong('while editing')
                    text(' the relevant status report')
                with p():
                    text('For step by step instructions, see the ')
                    a('Member Guide',
                      href='https://members.readthedocs.io/en/latest/meetings-member-guide.html#'
                           + slugify('My Status Report view'),
                      target='_blank')

        return html.render()

    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()

        # self.meeting set up in self.permission()
        self.queryparams['meeting_id'] = self.meeting.id
        invite = self.get_invite()
        self.queryparams['invite_id'] = invite.id

    def open(self):
        # before standard open handling, create records if they don't exist
        # self.queryparams and self.queryfilters have already been set up for this meeting / user

        # make sure there's an invite record, and we'll be using this later
        invite = self.get_invite()

        # determine current order number, in case we need to add records
        max = db.session.query(func.max(MemberStatusReport.order)).filter_by(**self.queryparams).filter(
                *self.queryfilters).one()
        # if MemberStatusReport records configured, use current max + 1
        if max[0]:
            order = max[0] + 1
        # if no MemberStatusReport records configured, start order at 1
        else:
            order = 1

        # add rsvp record if it doesn't exist
        if not MemberStatusReport.query.filter_by(is_rsvp=True, **self.queryparams).filter(*self.queryfilters).one_or_none():
            statusreport = StatusReport(
                title='RSVP',
                interest=localinterest(),
                meeting=self.meeting,
            )
            db.session.add(statusreport)
            rsvprec = MemberStatusReport(
                interest=localinterest(), 
                meeting_id=self.meeting.id, 
                invite=invite,
                content=statusreport,
                is_rsvp=True, 
                order=order
            )
            db.session.add(rsvprec)
            order += 1

        # check member's current positions
        # see https://stackoverflow.com/questions/36916072/flask-sqlalchemy-filter-on-many-to-many-relationship-with-parent-model
        # see https://stackoverflow.com/questions/34804756/sqlalchemy-filter-many-to-one-relationship-where-the-one-object-has-a-list-cont
        positions = Position.query.filter_by(has_status_report=True)\
            .filter(Position.users.any(LocalUser.id == user2localuser(current_user).id)).all()
        for position in positions:
            filters = [StatusReport.position == position] + self.queryfilters
            # has the member status report already been created? if not, create one
            if not MemberStatusReport.query.filter_by(**self.queryparams).join(StatusReport).filter(*filters).one_or_none():
                # statusreport for this position may exist already, done by someone else
                statusquery = {'interest': localinterest(), 'meeting': self.meeting, 'position': position}
                statusreport = StatusReport.query.filter_by(**statusquery).one_or_none()
                if not statusreport:
                    statusreport = StatusReport(
                        title='{} Status Report'.format(position.position),
                        interest=localinterest(),
                        meeting=self.meeting,
                        position=position
                    )
                    db.session.add(statusreport)
                # there's always a new memberstatusreport if it didn't exist before
                memberstatusreport = MemberStatusReport(
                    interest=localinterest(),
                    meeting=self.meeting,
                    invite=invite,
                    content=statusreport,
                    order=order,
                )
                db.session.add(memberstatusreport)
                order += 1

        db.session.flush()
        super().open()

    def createrow(self, formdata):
        """
        create row, need invite id and new StatusReport record

        :param formdata: form from create window
        :return: response data
        """
        # make sure there's an invite record
        invite = self.get_invite()
        formdata['invite_id'] = invite.id
        statusreport = StatusReport(
            title=formdata['title'],
            interest=localinterest(),
            meeting=self.meeting,
        )
        db.session.add(statusreport)
        db.session.flush()

        # need to do this instead of calling super.createrow() because of chicken/egg problem for access
        # of subrecords during set_dbrow()
        # determine current order number, in case we need to add records
        max = db.session.query(func.max(MemberStatusReport.order)).filter_by(**self.queryparams).filter(
                *self.queryfilters).one()
        # if MemberStatusReport records configured, use current max + 1
        order = max[0] + 1
        dbrow = MemberStatusReport(
            interest=localinterest(),
            meeting=self.meeting,
            invite=invite,
            content=statusreport,
            order=order,
        )
        self.dte.set_dbrow(formdata, dbrow)
        self.db.session.add(dbrow)
        self.db.session.flush()
        self.created_id = dbrow.id

        # prepare response
        thisrow = self.dte.get_response_data(dbrow)
        return thisrow

    def postprocessrow(self, row):
        """
        annotate row with table definition(s)

        :param row: row dict about to be returned to client
        :return: updated row dict
        """
        # flag if this row has hidden discussion items
        hiddenagendaitems = AgendaItem.query.filter_by(statusreport_id=row['statusreport_id'], is_hidden=True).all()
        if hiddenagendaitems:
            row['DT_RowClass'] = 'hidden-row'

        # set context for table filtering
        invite = Invite.query.filter_by(id=row['invite_id']).one()
        context = {
            'meeting_id': invite.meeting_id,
            'statusreport_id': row['statusreport_id'],
        }
        if row['position_id']:
            context['position_id'] = row['position_id']

        tablename = 'discussionitems'
        tables = [
            {
                'name': tablename,
                'label': 'Discussion Items',
                'url': rest_url_for('admin.memberdiscussions', interest=g.interest, urlargs=context),
                'createfieldvals': context,
                'tableid': self.childtables[tablename]['table'].tableid(**context)
            }]

        row['tables'] = tables

        tableid = self.tableid(**context)
        if tableid:
            row['tableid'] = tableid

def get_invite_response(dbrow):
    invite = dbrow.invite
    return invite.response

def memberstatusreport_buttons():
    invite = Invite.query.filter_by(invitekey=request.args['invitekey']).one()
    meeting = invite.meeting
    today = date.today()
    if meeting.date >= today:
        buttons = [
            'create',
            'editChildRowRefresh',
            {'text': 'Instructions',
             'action': {'eval': 'mystatus_instructions()'}
             },
        ]
    else:
        buttons = []

    return buttons

memberstatusreport_dbattrs = 'id,interest_id,order,content.title,is_rsvp,invite_id,invite.response,invite.attended,'\
                             'content.id,content.statusreport,content.position_id'.split(',')
memberstatusreport_formfields = 'rowid,interest_id,order,title,is_rsvp,invite_id,rsvp_response,attended,'\
                                'statusreport_id,statusreport,position_id'.split(',')
memberstatusreport_dbmapping = dict(zip(memberstatusreport_dbattrs, memberstatusreport_formfields))
memberstatusreport_formmapping = dict(zip(memberstatusreport_formfields, memberstatusreport_dbattrs))
memberstatusreport_dbmapping['invite.attended'] = lambda form: True if form['attended'] == 'true' else False

memberstatusreport = MemberStatusreportView(
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=MemberStatusReport,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-member-guide.html'},
    pagename='My Status Report',
    endpoint='admin.memberstatusreport',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/memberstatusreport',
    dbmapping=memberstatusreport_dbmapping,
    formmapping=memberstatusreport_formmapping,
    checkrequired=True,
    tableidtemplate ='actionitems-{{ meeting_id }}-{{ comment_id }}',
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
        {'data': 'title', 'name': 'title', 'label': 'Report Title',
         'className': 'field_req',
         },
        {'data': 'rsvp_response', 'name': 'rsvp_response', 'label': 'Attending',
         'type': 'select2', 'options': invite_response_all,
         'visible': False,
         },
        {'data': 'statusreport', 'name': 'statusreport', 'label': 'Status Report',
         'visible': False,
         'type': 'ckeditorInline',
         },
        # this is hidden, updated automatically by member setting response (see afterdatatables.js)
        {'data': 'attended', 'name': 'attended', 'label': 'Attended',
         'visible': False,
         'type': 'hidden',
         },
    ],
    childrowoptions= {
        'template': 'memberstatusreport-child-row.njk',
        'showeditor': True,
        'group': 'interest',
        'groupselector': '#metanav-select-interest',
        'childelementargs': [
            {'name': 'discussionitems', 'type': CHILDROW_TYPE_TABLE, 'table': memberdiscussions,
             'postcreatehook': 'discussionitems_postcreate',
             'args': {
                 'buttons': ['create', 'editRefresh', 'remove'],
                 'columns': {
                     'datatable': {
                         # uses data field as key
                         'purpose': {'visible': False},
                         'date': {'visible': False},
                         'statusreport': {'visible': False},
                     },
                     'editor': {
                         # uses name field as key
                         'purpose': {'type': 'hidden'},
                         'date': {'type': 'hidden'},
                         # 'statusreport': {'type': 'hidden'},
                     },
                 },
                 'updatedtopts': {
                     'dom': 'Brt',
                     'paging': False,
                 },
             }
             },
        ],
    },
    idSrc='rowid',
    buttons=memberstatusreport_buttons,
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'paging': False,
    },
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
            'text': 'My Status Report',
            'action': {'eval': 'mymeeting_statusreport'}
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
         'type': 'ckeditorInline',
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

