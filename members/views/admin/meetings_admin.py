'''
meetings_admin - administrative task handling for meetings admin
====================================================================================
'''
# standard
from uuid import uuid4

# pypi
from flask import request
from dominate.tags import p, div, table, tr, td, h1, h2
from sqlalchemy import func

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Tag, Position, Invite
from ...model import Meeting, Invite, AgendaItem, Motion, MotionVote
from ...model import localinterest_query_params, localinterest_viafilter
from ...model import invite_response_all, INVITE_RESPONSE_ATTENDING
from .viewhelpers import dtrender, localinterest, localuser2user

from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.user.model import User
from loutilities.tables import _editormethod, get_request_action, CHILDROW_TYPE_TABLE
from loutilities.timeu import asctime
isotime = asctime('%Y-%m-%d')

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

meetings_dbattrs = 'id,interest_id,date,purpose,tags'.split(',')
meetings_formfields = 'rowid,interest_id,date,purpose,tags'.split(',')
meetings_dbmapping = dict(zip(meetings_dbattrs, meetings_formfields))
meetings_formmapping = dict(zip(meetings_formfields, meetings_dbattrs))
meetings_dbmapping['date'] = lambda formrow: dtrender.asc2dt(formrow['date'])
meetings_formmapping['date'] = lambda dbrow: dtrender.dt2asc(dbrow.date)

meetings = DbCrudApiInterestsRolePermissions(
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
    clientcolumns=[
        {'data': 'purpose', 'name': 'purpose', 'label': 'Purpose',
         'className': 'field_req',
         'type': 'textarea',
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'datetime',
         'className': 'field_req',
         },
        {'data': 'tags', 'name': 'tags', 'label': 'Tags',
         'fieldInfo': 'members who have these tags, either directly or via position, will be invited',
         '_treatment': {
             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag', 'formfield': 'tags',
                              'dbfield': 'tags', 'uselist': True,
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
        'order': [2,'desc'],
    },
)
meetings.register()

##########################################################################################
# invites endpoint
###########################################################################################

# class InvitesView(DbCrudApiInterestsRolePermissions):
#     '''
#     special processing for nested server attributes
#     '''


invites_dbattrs = 'id,interest_id,meeting.purpose,meeting.date,user.name,user.email,agendaitem.agendaitem,invitekey,response,attended,activeinvite'.split(',')
invites_formfields = 'rowid,interest_id,purpose,date,name,email,agendaitem,invitekey,response,attended,activeinvite'.split(',')
invites_dbmapping = dict(zip(invites_dbattrs, invites_formfields))
invites_formmapping = dict(zip(invites_formfields, invites_dbattrs))
# invites_formmapping['date'] = lambda dbrow: isotime.dt2asc(dbrow.meeting.date)

invites = DbCrudApiInterestsRolePermissions(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Invite,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-admin-guide.html'},
    pagename='Invites',
    endpoint='admin.invites',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/invites',
    dbmapping=invites_dbmapping,
    formmapping=invites_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'purpose', 'name': 'purpose', 'label': 'Meeting',
         'type': 'readonly',
         },
        {'data': 'date', 'name': 'date', 'label': 'Date',
         'type': 'readonly',
         '_ColumnDT_args' : {'sqla_expr': func.date_format(Meeting.date, '%Y-%m-%d')}
         },
        {'data': 'name', 'name': 'name', 'label': 'Name',
         'type': 'readonly',
         },
        {'data': 'email', 'name': 'email', 'label': 'Email',
         'type': 'readonly',
         },
        {'data': 'response', 'name': 'response', 'label': 'Response',
         'type': 'select2',
         'options': invite_response_all,
         },
        {'data': 'attended', 'name': 'attended', 'label': 'Attended',
         'class': 'TextCenter',
         '_treatment': {'boolean': {'formfield': 'attended', 'dbfield': 'attended'}},
         'ed': {'def': 'no'},
         },
        {'data': 'activeinvite', 'name': 'activeinvite', 'label': 'Invited',
         'class': 'TextCenter',
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
# meeting endpoint
###########################################################################################

class MeetingView(DbCrudApiInterestsRolePermissions):
    def __init__(self, **kwargs):
        args = dict(
            pretablehtml = self.format_pretablehtml
        )
        args.update(kwargs)

        # initialize inherited class, and a couple of attributes
        super().__init__(**args)

    def permission(self):
        '''
        verify meetingid arg

        :return: boolean
        '''
        if 'meetingid' not in request.args:
            return False
        meetingid = request.args['meetingid']
        meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()
        if not meeting:
            return False
        return super().permission()

    def format_pretablehtml(self):
        meetingid = request.args['meetingid']
        meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()
        html = h1('{} - {}'.format(meeting.date, meeting.purpose), _class='TextCenter')
        return html.render()

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

    def get_invites(self):
        meetingid = request.args['meetingid']
        meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()

        if not meeting:
            raise ParameterError('meeting with id "{}" not found'.format(meetingid))

        def get_invite(meeting, localuser):
            user = localuser2user(localuser)
            email = user.email
            invitestate = {'name': user.name, 'email':email}
            invite = Invite.query.filter_by(interest=localinterest(), meeting=meeting, user=localuser).one_or_none()
            if invite:
                invitestate['state'] = 'attending' if invite.response == INVITE_RESPONSE_ATTENDING else 'invited'
            else:
                invitestate['state'] = 'send invitation'
            return email, invitestate, invite

        # send invitations to all those who are tagged like the meeting
        invitestates = {}
        invites = {}
        for tag in meeting.tags:
            for user in tag.users:
                email, invitestate, invite = get_invite(meeting, user)
                invitestates[email] = invitestate
                invites[email] = invite
            for position in tag.positions:
                for user in position.users:
                    email, invitestate, invite = get_invite(meeting, user)
                    # may be overwriting but that's ok
                    invitestates[email] = invitestate
                    invites[email] = invite

        # return the state values to simplify client work, also return the database records
        return list(invitestates.values()), list(invites.values())

    def generateinvites(self):
        meetingid = request.args['meetingid']
        meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()

        if not meeting:
            raise ParameterError('meeting with id "{}" not found'.format(meetingid))

        # check if agendaitem already exists. If any invites to the meeting there should already be the agenda item
        # also use this later to deactivate any invites which are not still needed
        previnvites = Invite.query.filter_by(interest=localinterest(), meeting=meeting).all()
        if not previnvites:
            agendaitem = AgendaItem(interest=localinterest(), meeting=meeting, order=1, title='Attendees', agendaitem='')
            db.session.add(agendaitem)
        # all of the invites should have the same agendaitem, so just use the first
        else:
            agendaitem = previnvites[0].agendaitem

        def check_add_invite(meeting, localuser, agendaitem):
            invite = Invite.query.filter_by(interest=localinterest(), meeting=meeting, user=localuser).one_or_none()
            if not invite:
                # create unique key for invite - uuid4 gives unique key
                invitekey = uuid4().hex
                invite = Invite(
                    interest=localinterest(),
                    meeting=meeting,
                    user=localuser,
                    agendaitem=agendaitem,
                    invitekey = invitekey,
                )
                db.session.add(invite)
                # todo: send email

        # send invitations to all those who are tagged like the meeting
        for tag in meeting.tags:
            for user in tag.users:
                check_add_invite(meeting, user, agendaitem)
            for position in tag.positions:
                for user in position.users:
                    check_add_invite(meeting, user, agendaitem)

        # todo: make invites for anyone who has been removed from the list 'inactive'

        # this agendaitem will be added to the displayed table
        db.session.flush()
        return agendaitem

    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()
        self.queryparams['meeting_id'] = request.args['meetingid']
        # this is here to set invites for initial page load
        self.updateinvites()

    def editor_method_postcommit(self, form):
        # this is here in case invites changed during edit action
        self.updateinvites()

    @_editormethod(checkaction='create,checkinvites,sendinvites,refresh', formrequest=True)
    def post(self):
        action = get_request_action(request.form)
        if action == 'checkinvites':
            invitestates, invites = self.get_invites()
            self._responsedata = []
            self.responsekeys['checkinvites'] = invitestates
        elif action == 'sendinvites':
            agendaitem = self.generateinvites()
            thisrow = self.dte.get_response_data(agendaitem)
            self._responsedata = [thisrow]
        else:
            # note we're already wrapped with _editormethod, don't wrap again
            super().do_post()

    def createrow(self, formdata):
        formdata['meeting_id'] = request.args['meetingid']
        output = super().createrow(formdata)
        return output

meeting_dbattrs = 'id,interest_id,meeting_id,order,title,agendaitem,discussion'.split(',')
meeting_formfields = 'rowid,interest_id,meeting_id,order,title,agendaitem,discussion'.split(',')
meeting_dbmapping = dict(zip(meeting_dbattrs, meeting_formfields))
meeting_formmapping = dict(zip(meeting_formfields, meeting_dbattrs))

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
    clientcolumns=[
        {'data':None,
         'name':'details-control',
         'className': 'details-control',
         'orderable': False,
         'defaultContent': '',
         'width': '15px',
         'label': '',
         'type': 'hidden',  # only affects editor modal
         'render': {'eval':'render_plus'},
         },
        {'data': 'order', 'name': 'order', 'label': 'Order',
         'className': 'field_req',
         },
        {'data': 'title', 'name': 'title', 'label': 'Title',
         'className': 'field_req',
         },
        {'data': 'agendaitem', 'name': 'agendaitem', 'label': 'Summary',
         'type': 'ckeditorInline',
         'visible': False,
         'opts': {
             'toolbar': ["heading", "|", "bold", "italic", "link", "bulletedList", "numberedList",
                         "|", "indent", "outdent", "|", "blockQuote", "insertTable", "undo", "redo"]
         }
         },
        {'data': 'discussion', 'name': 'discussion', 'label': 'Discussion',
         'type': 'ckeditorInline',
         'visible': False,
         'opts': {
             'toolbar': ["heading", "|", "bold", "italic", "link", "bulletedList", "numberedList",
                         "|", "indent", "outdent", "|", "blockQuote", "insertTable", "undo", "redo"]
         }
         },
    ],
    childrowoptions= {
        'template': 'meeting-child-row.njk',
        'showeditor': True,
        'childelementargs': [
            dict(name='invites', type=CHILDROW_TYPE_TABLE, table=invites, args=dict()),
        ],
    },
    serverside=True,
    idSrc='rowid',
    buttons=[
        # 'editor' gets eval'd to editor instance
        {'extend':'newInvites', 'editor': {'eval':'editor'}},
        'create',
        'remove',
        'csv'
    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [[1,'asc']],
    },
)
meeting.register()

