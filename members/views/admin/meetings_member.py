'''
meetings_member - handling for meetings member
====================================================================================
'''

# standard
from datetime import date

# pypi
from flask import request, flash, g
from flask_security import current_user, logout_user, login_user
from sqlalchemy import func
from dominate.tags import div, h1, h2, ul, li, p, b
from dominate.util import text

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Position, Invite, Meeting, AgendaItem
from ...model import MemberStatusReport, StatusReport, DiscussionItem
from ...model import invite_response_all
from .viewhelpers import localuser2user, user2localuser, localinterest
from loutilities.tables import rest_url_for, CHILDROW_TYPE_TABLE
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

class ParameterError(Exception): pass


##########################################################################################
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
        else:
            agendatitle += ' [{}]'.format(current_user.name)

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
        permitted = super().permission()

        if permitted:
            invitekey = request.args.get('invitekey', None)
            if invitekey:
                invite = Invite.query.filter_by(invitekey=invitekey).one()
                user = localuser2user(invite.user)
                self.meeting = invite.meeting
                if current_user != user:
                    # log out and in automatically
                    # see https://flask-security-too.readthedocs.io/en/stable/api.html#flask_security.login_user
                    old_user = current_user.name
                    logout_user()
                    login_user(user)
                    db.session.commit()
                    flash('you have been automatically logged in as {}'.format(current_user.name))

            # no invitekey, so meeting_id must be specified, use the current_user
            else:
                meeting_id = request.args.get('meeting_id', None)
                if not meeting_id:
                    raise ParameterError('meeting_id needs to be specified in URL')

                self.meeting = Meeting.query.filter_by(id=meeting_id).one()

            # at this point, current_user has the target user (may have been changed by invitekey)

            # check role permissions, permitted = True (from above) unless determined otherwise
            roles_accepted = [ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER]
            allowed = False
            for role in roles_accepted:
                if current_user.has_role(role):
                    allowed = True
                    break
            if not allowed:
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
        html += h1('{} - {} - {}'.format(meeting.date, meeting.purpose, current_user.name), _class='TextCenter')

        instructhtml = div()
        html += instructhtml
        instructhtml += h2('Instructions')
        listhtml = ul()
        instructhtml += listhtml

        listhtml += li('RSVP to the meeting by clicking/editing the first row')
        listhtml += li('Provide Status Reports for each of your positions by clicking/editing subsequent rows')
        listhtml += li('Optionally add a Status Report for something outside your assigned position by clicking New')
        discussionhtml = li()
        with discussionhtml:
            text('If you would like to highlight a topic for discussion in the board meeting, add a discussion item from ')
            text('within the relevant status report by clicking on "New" in the Discussion Item section of the status report. ')
            with ul():
                li('Status report has to be in Edit mode to add discussion items')
                li('NOTE: Without a discussion item identified, the topic will not be added to the meeting agenda')
        listhtml += discussionhtml

        instructhtml += p('In all cases, don\'t forget to Save each item as you work through your report')

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

memberstatusreport_dbattrs = 'id,interest_id,order,content.title,is_rsvp,invite_id,invite.response,content.id,content.statusreport,content.position_id'.split(',')
memberstatusreport_formfields = 'rowid,interest_id,order,title,is_rsvp,invite_id,rsvp_response,statusreport_id,statusreport,position_id'.split(',')
memberstatusreport_dbmapping = dict(zip(memberstatusreport_dbattrs, memberstatusreport_formfields))
memberstatusreport_formmapping = dict(zip(memberstatusreport_formfields, memberstatusreport_dbattrs))

memberstatusreport = MemberStatusreportView(
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=MemberStatusReport,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-members-guide.html'},
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
         },
        {'data': 'rsvp_response', 'name': 'rsvp_response', 'label': 'Attending',
         'type': 'select2', 'options': invite_response_all,
         'visible': False,
         },
        {'data': 'statusreport', 'name': 'statusreport', 'label': 'Status Report',
         'visible': False,
         'type': 'ckeditorInline',
         # 'type': 'ckeditorExt',
         'opts': {
             'toolbar': ["heading", "|", "bold", "italic", "link", "bulletedList", "numberedList",
                         "|", "indent", "outdent", "|", "blockQuote", "insertTable", "undo", "redo"]
         }
         },
    ],
    childrowoptions= {
        'template': 'memberstatusreport-child-row.njk',
        'showeditor': True,
        'group': 'interest',
        'groupselector': '#metanav-select-interest',
        'childelementargs': [
            {'name': 'discussionitems', 'type': CHILDROW_TYPE_TABLE, 'table': memberdiscussions,
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
    buttons=[
        'create',
        'editChildRowRefresh',
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
memberstatusreport.register()

