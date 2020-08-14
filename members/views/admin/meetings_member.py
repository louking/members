'''
meetings_member - handling for meetings member
====================================================================================
'''

# standard

# pypi
from flask import request, flash
from flask_security import current_user, logout_user, login_user
from sqlalchemy import func
from dominate.tags import div, h1, h2, p

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Position, Invite, Meeting
from ...model import MemberStatusReport, StatusReport, DiscussionItem
from ...model import invite_response_all
from .viewhelpers import localuser2user, user2localuser, localinterest
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

class ParameterError(Exception): pass


##########################################################################################
# memberstatusreport endpoint
###########################################################################################

class MemberStatusreportView(DbCrudApiInterestsRolePermissions):
    def __init__(self, **kwargs):
        args = dict(
            pretablehtml = self.format_pretablehtml
        )
        args.update(kwargs)

        # initialize inherited class, and a couple of attributes
        super().__init__(**args)

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
        instructhtml += h2('Instructions')
        instructhtml += p('RSVP to the meeting in the first row')
        instructhtml += p('To edit your status, click on a row and then click Edit. Don\'t forget to click Save')
        html += instructhtml

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
        # self.queryfilters = [Invite.user_id == user2localuser(current_user).id]


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
                        title=position.position,
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

def get_invite_response(dbrow):
    invite = dbrow.invite
    return invite.response

memberstatusreport_dbattrs = 'id,interest_id,order,content.title,is_rsvp,invite_id,invite.response,content.id,content.statusreport'.split(',')
memberstatusreport_formfields = 'rowid,interest_id,order,title,is_rsvp,invite_id,rsvp_response,statusreport_id,statusreport'.split(',')
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
         'type': 'readonly',
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
        ],
    },
    idSrc='rowid',
    buttons=[
        'create',
        'editChildRowRefresh',
        'csv'
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
memberstatusreport.register()

