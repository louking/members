"""
meetings_common - common view support for meetings
====================================================================================
"""
# standard
from datetime import date
from copy import deepcopy

# pypi
from flask import request, g
from flask_security import current_user
from sqlalchemy.orm import aliased
from sqlalchemy import func, or_
from dominate.tags import div, ol, li, p, em, strong, a, i
from dominate.util import text
from slugify import slugify

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Position, Invite, Meeting, AgendaItem, ActionItem
from ...model import DiscussionItem
from ...model import action_all, motion_all, motionvote_all
from ...model import MOTION_STATUS_OPEN, MOTIONVOTE_STATUS_APPROVED, MOTIONVOTE_STATUS_NOVOTE
from ...model import ACTION_STATUS_OPEN, ACTION_STATUS_CLOSED
from ...model import localinterest_query_params, localinterest_viafilter
from ...model import MemberStatusReport, StatusReport
from ...model import INVITE_RESPONSE_NO_RESPONSE
from .viewhelpers import dtrender, localinterest, localuser2user, user2localuser
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER
from loutilities.tables import rest_url_for, CHILDROW_TYPE_TABLE
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption

class ParameterError(Exception): pass

class ChildElementArgs():
    '''
    supports configuration for childelementargs for DbCrudApiInterestsRolePermissions instantiation. For
    CHILDROW_TYPE_TABLE elements,

    :param elements: childelementargs configuration without 'table' field
    '''

    def __init__(self, elements):
        self.elements = elements

    def get_childelementargs(self, tables):
        '''
        substitute tables[element['name']] value for 'table' field

        :param tables: {tablename: table, ... }
        :return: childelementargs configuration
        '''
        theseelements = deepcopy(self.elements)
        for element in theseelements:
            if element['type'] == CHILDROW_TYPE_TABLE:
                if element['name'] not in tables:
                    raise ParameterError('{} missing from tables parameter'.format(element['name']))
                element['table'] = tables[element['name']]

        return theseelements

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
    def permission(self):
        '''
        verify current_user has access to this user's discussions.
        as side effect, set self.theuser (User)

        :return: True if permission is to be granted
        '''
        permitted = super().permission()
        if permitted:
            invitekey = request.args.get('invitekey', None)
            localuser_id = Invite.query.filter_by(invitekey=invitekey).one().user.id if invitekey else user2localuser(current_user).id
            localuser = LocalUser.query.filter_by(id=localuser_id).one()
            self.theuser = localuser2user(localuser)
            # ok for current user, otherwise, must have super admin or meetings admin permission,
            # and be allowed current interest
            if not (self.theuser == current_user
                    or
                    # one of current user's roles is super admin or meetings admin
                    (set([r.name for r in current_user.roles]) & set([ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN])
                     and
                     # targeted user is allowed current interest
                     g.interest in [i.interest for i in self.theuser.interests])):
                permitted = False
        return permitted


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
            agendatitle += ' [{} / {}]'.format(self.theuser.name, position.position)
            agendaheading = position.agendaheading
        else:
            agendatitle += ' [{}]'.format(self.theuser.name)
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
    tableidcontext=lambda row: {
        'rowid': row['rowid'],
    },
    tableidtemplate ='discussionitems-{{ rowid }}',
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
         'type':'ckeditorClassic',
         },
        {'data': 'hidden_reason', 'name': 'hidden_reason', 'label': 'Reason for Hiding',
         'type':'readonly',
         },
        # the following fields are required for tying to meeting view row and other housekeeping
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

def memberstatusreport_buttons():
    invitekey = request.args.get('invitekey', None)
    rsvpclass = ''
    if invitekey:
        invite = Invite.query.filter_by(invitekey=request.args['invitekey']).one()
        meeting = invite.meeting
        today = date.today()
        if invite.response == INVITE_RESPONSE_NO_RESPONSE:
            rsvpclass = 'rsvp-noresponse'
    if invitekey and meeting.date >= today:
        buttons = [
            {'text': 'New',
             'action': {'eval': 'mystatus_create'}
             },
            {'extend': 'editChildRowRefresh', 'editor':{'eval': 'editor'}, 'className': 'Hidden'},
            {'text': 'RSVP',
             'className': rsvpclass,
             'action': {
                 'eval': 'mystatus_rsvp("{}?invitekey={}")'.format(rest_url_for('admin._mymeetingrsvp',
                                                                                interest=g.interest),
                                                                   invite.invitekey)}
             },
            {'text': 'Instructions',
             'action': {'eval': 'mystatus_instructions()'}
             },
        ]
    else:
        buttons = []

    return buttons

memberstatusreport_dbattrs = 'id,interest_id,order,content.title,is_rsvp,invite_id,'\
                             'content.id,content.statusreport,content.position_id'.split(',')
memberstatusreport_formfields = 'rowid,interest_id,order,title,is_rsvp,invite_id,'\
                                'statusreport_id,statusreport,position_id'.split(',')
memberstatusreport_dbmapping = dict(zip(memberstatusreport_dbattrs, memberstatusreport_formfields))
memberstatusreport_formmapping = dict(zip(memberstatusreport_formfields, memberstatusreport_dbattrs))
memberstatusreport_dbmapping['invite.attended'] = lambda form: True if form['attended'] == 'true' else False

# used by meetings_member.MemberStatusReportView and meetings_admin.TheirStatusReportView
class MemberStatusReportBase(DbCrudApiInterestsRolePermissions):
    def __init__(self, **kwargs):
        args = dict(
            local_interest_model=LocalInterest,
            app=bp,  # use blueprint instead of app
            db=db,
            model=MemberStatusReport,
            version_id_col='version_id',  # optimistic concurrency control
            template='datatables.jinja2',
            pretablehtml=self.format_pretablehtml,
            dbmapping=memberstatusreport_dbmapping,
            formmapping=memberstatusreport_formmapping,
            checkrequired=True,
            tableidcontext=lambda row: {
                'comment_id': row['comment_id'],
            },
            tableidtemplate='memberstatusreport-{{ comment_id }}',
            clientcolumns=[
                {'data': '',  # needs to be '' else get exception converting options from meetings render_template
                 # TypeError: '<' not supported between instances of 'str' and 'NoneType'
                 'name': 'details-control',
                 'className': 'details-control shrink-to-fit',
                 'orderable': False,
                 'defaultContent': '',
                 'label': '',
                 'type': 'hidden',  # only affects editor modal
                 'title': '<i class="fa fa-plus-square" aria-hidden="true"></i>',
                 'render': {'eval': 'render_plus'},
                 },
                {'data': '',  # needs to be '' else get exception converting options from meetings render_template
                 # TypeError: '<' not supported between instances of 'str' and 'NoneType'
                 'name': 'edit-control',
                 'className': 'edit-control shrink-to-fit',
                 'orderable': False,
                 'defaultContent': '',
                 'label': '',
                 'type': 'hidden',  # only affects editor modal
                 'title': 'Edit',
                 'render': {'eval': 'render_edit'},
                 },
                {'data': 'title', 'name': 'title', 'label': 'Status Report Title',
                 'className': 'field_req',
                 },
                {'data': 'statusreport', 'name': 'statusreport', 'label': 'Status Report',
                 'visible': False,
                 'type': 'ckeditorClassic',
                 },
            ],
            childrowoptions={
                'template': 'memberstatusreport-child-row.njk',
                'showeditor': True,
                'group': 'interest',
                'groupselector': '#metanav-select-interest',
                'childelementargs': [
                    {'name': 'discussionitems', 'type': CHILDROW_TYPE_TABLE, 'table': memberdiscussions,
                     'tableidtemplate': 'discussionitems-{{ parentid }}',
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
        args.update(kwargs)

        # initialize inherited class, and a couple of attributes
        super().__init__(**args)

        # this causes self.dte.get_response_data to execute postprocessrow() to transform returned response
        self.dte.set_response_hook(self.postprocessrow)

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

        # check member's current positions
        # see https://stackoverflow.com/questions/36916072/flask-sqlalchemy-filter-on-many-to-many-relationship-with-parent-model
        # see https://stackoverflow.com/questions/34804756/sqlalchemy-filter-many-to-one-relationship-where-the-one-object-has-a-list-cont
        positions = Position.query.filter_by(has_status_report=True)\
            .filter(Position.users.any(LocalUser.id == user2localuser(self.theuser).id)).all()
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
        rowclasses = []

        # flag if this row has hidden discussion items
        hiddenagendaitems = AgendaItem.query.filter_by(statusreport_id=row['statusreport_id'], is_hidden=True).all()
        if hiddenagendaitems:
            rowclasses.append('hidden-row')

        # set class needsedit depending on whether statusreport is present
        if not row['statusreport']:
            rowclasses.append('needsedit')

        # set context for table filtering
        invite = Invite.query.filter_by(id=row['invite_id']).one()
        context = {
            'meeting_id': invite.meeting_id,
            'statusreport_id': row['statusreport_id'],
        }
        templatecontext = {
            'rowid': row['rowid']
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
                'tableid': self.childtables[tablename]['table'].tableid(**templatecontext)
            }]

        row['tables'] = tables

        # set DT_RowClass based on accumulated classes
        row['DT_RowClass'] = ' '.join(rowclasses)

    def instructions(self):
        theinstructions = div()

        with theinstructions:

            # id referenced from beforedatatables.js meeting_send_email()
            with div(id='mystatus-instructions', style='display: none;'):
                p('Please respond as follows:')
                with ol():
                    with li():
                        text('RSVP to the meeting by clicking ')
                        strong('RSVP')
                        text(' button')
                    li('Provide Status Reports for each of your positions by editing subsequent rows (see Note)')
                    with li():
                        em('Optionally')
                        text(' add a Status Report for something outside your assigned position by clicking the ')
                        strong('New')
                        text(' button')
                with p():
                    text('If you would like to add a discussion item to the meeting agenda, click ')
                    strong('New')
                    text(' in the Discussion Item ')
                    strong('while editing')
                    text(' the relevant status report')
                with p():
                    text('For step by step instructions, see the ')
                    a('Help for My Status Report',
                      href='https://members.readthedocs.io/en/latest/meetings-member-guide.html#'
                           + slugify('My Status Report view'),
                      target='_blank')
                p(strong('NOTES:'))
                with ol():
                    with li():
                        text('to ')
                        i('view')
                        text(' a status report, click on ')
                        i(_class='fa fa-plus', style='background-color: forestgreen; color: white; padding: 2px; '
                                                     'font-size: 60%;')
                        text(' to expand, ')
                        i(_class='fa fa-minus', style='background-color: deepskyblue; color: white; padding: 2px; '
                                                      'font-size: 60%;')
                        text(' to collapse')
                    with li():
                        text('to ')
                        i('edit')
                        text(' a status report, click on ')
                        i(_class='fas fa-edit', style='color: orangered;')
                    with li():
                        text('if the edit button is displayed as ')
                        i(_class='fas fa-edit', style='color: forestgreen;')
                        text(' this means the status report has been entered -- it can still be edited, though')

            div(id='mystatus_button_error', style='display: none;')

        return theinstructions

##########################################################################################
# actionitems endpoint
###########################################################################################

actionitems_dbattrs = 'id,interest_id,meeting_id,agendaitem_id,meeting.purpose,meeting.date,action,comments,status,assignee,update_time,updated_by'.split(',')
actionitems_formfields = 'rowid,interest_id,meeting_id,agendaitem_id,purpose,date,action,comments,status,assignee,update_time,updated_by'.split(',')
actionitems_dbmapping = dict(zip(actionitems_dbattrs, actionitems_formfields))
actionitems_formmapping = dict(zip(actionitems_formfields, actionitems_dbattrs))

# need aliased because LocalUser referenced twice within motions
# https://stackoverflow.com/questions/46800183/using-sqlalchemy-datatables-with-multiple-relationships-between-the-same-tables
# need to use single variable with onclause so duplicate join checking in tables.DbCrudApi.__init__() doesn't duplicate join
localuser_actionitems_alias = aliased(LocalUser)
localuser_actionitems_onclause = localuser_actionitems_alias.id == ActionItem.assignee_id

actionitems_filters = filtercontainerdiv()
actionitems_filters += filterdiv('actionitems-external-filter-date', 'Date')
actionitems_filters += filterdiv('actionitems-external-filter-assignee', 'Assignee')
actionitems_filters += filterdiv('actionitems-external-filter-status', 'Status')

actionitems_yadcf_options = [
    yadcfoption('date:name', 'actionitems-external-filter-date', 'range_date'),
    yadcfoption('assignee.name:name', 'actionitems-external-filter-assignee', 'multi_select', placeholder='Select names', width='200px'),
    yadcfoption('status:name', 'actionitems-external-filter-status', 'select', placeholder='Select', width='100px'),
]

# used by meetings_member.MemberActionItemsView and meetings_admin.ActionItemsView
class ActionItemsBase(DbCrudApiInterestsRolePermissions):
    def __init__(self, **kwargs):
        args = dict(
            local_interest_model=LocalInterest,
            app=bp,  # use blueprint instead of app
            db=db,
            model=ActionItem,
            version_id_col='version_id',  # optimistic concurrency control
            template='datatables.jinja2',
            pretablehtml=actionitems_filters.render(),
            yadcfoptions=actionitems_yadcf_options,
            endpointvalues={'interest': '<interest>'},
            dbmapping=actionitems_dbmapping,
            formmapping=actionitems_formmapping,
            checkrequired=True,
            tableidcontext=lambda row: {
                'agendaitem_id': row['agendaitem_id'],
            },
            tableidtemplate='actionitems-{{ agendaitem_id }}',
            clientcolumns=[
                {'data': '',  # needs to be '' else get exception converting options from meetings render_template
                 # TypeError: '<' not supported between instances of 'str' and 'NoneType'
                 'name': 'details-control',
                 'className': 'details-control shrink-to-fit',
                 'orderable': False,
                 'defaultContent': '',
                 'label': '',
                 'type': 'hidden',  # only affects editor modal
                 'title': '<i class="fa fa-plus-square" aria-hidden="true"></i>',
                 'render': {'eval': 'render_plus'},
                 },
                {'data': 'purpose', 'name': 'purpose', 'label': 'Meeting',
                 'type': 'readonly',
                 },
                {'data': 'date', 'name': 'date', 'label': 'Date',
                 'type': 'readonly',
                 '_ColumnDT_args':
                     {'sqla_expr': func.date_format(Meeting.date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'}
                 },
                {'data': 'action', 'name': 'action', 'label': 'Action',
                 'className': 'field_req',
                 'type': 'textarea',
                 'fieldInfo': 'description of action item',
                 },
                {'data': 'comments', 'name': 'comments', 'label': 'Comments',
                 'type': 'ckeditorClassic',
                 'fieldInfo': 'details of action item (if needed), notes about progress, and resolution - note won\'t be printed in agenda',
                 'visible': False,
                 },
                {'data': 'assignee', 'name': 'assignee', 'label': 'Assignee',
                 'className': 'field_req',
                 '_treatment': {
                     'relationship': {'fieldmodel': localuser_actionitems_alias, 'labelfield': 'name',
                                      'onclause': localuser_actionitems_onclause,
                                      'formfield': 'assignee', 'dbfield': 'assignee',
                                      'queryparams': lambda: {'active': True,
                                                              'interest': localinterest_query_params()['interest']},
                                      'searchbox': True,
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
            childrowoptions={
                'template': 'actionitem-child-row.njk',
                'showeditor': True,
                'group': 'interest',
                'groupselector': '#metanav-select-interest',
                'childelementargs': [],
            },
            serverside=True,
            idSrc='rowid',
            dtoptions={
                'scrollCollapse': True,
                'scrollX': True,
                'scrollXInner': "100%",
                'scrollY': True,
            },
        )
        args.update(kwargs)

        # initialize inherited class, and a couple of attributes
        super().__init__(**args)

    def beforequery(self):
        '''
        add filters to query parameters
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
        # NOTE: show_actions_since is only used from Meetings view, and we also need to show any action items
        # which haven't been closed, regardless of when they were last updated.
        show_actions_since = request.args.get('show_actions_since', None)
        if show_actions_since:
            show_actions_since = dtrender.asc2dt(show_actions_since)
            self.queryfilters = [or_(ActionItem.update_time >= show_actions_since,
                                     ActionItem.status != ACTION_STATUS_CLOSED)]



