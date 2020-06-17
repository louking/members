'''
meetings_admin - administrative task handling for meetings admin
====================================================================================
'''
# standard

# pypi
from flask import request
from dominate.tags import p, div, table, tr, td, h1, h2

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Tag, Position
from ...model import Meeting, Invite, AgendaItem, Motion, MotionVote
from ...model import localinterest_query_params, localinterest_viafilter
from .viewhelpers import dtrender, localinterest

from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.user.model import User

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

    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()
        self.queryparams['meeting_id'] = request.args['meetingid']

    def format_pretablehtml(self):
        meetingid = request.args['meetingid']
        meeting = Meeting.query.filter_by(id=meetingid, interest_id=localinterest().id).one_or_none()
        html = h1('{} - {}'.format(meeting.date, meeting.purpose), _class='TextCenter')
        return html.render()

    def createrow(self, formdata):
        formdata['meeting_id'] = request.args['meetingid']
        output = super().createrow(formdata)
        return output

meeting_dbattrs = 'id,interest_id,meeting_id,order,title,agendaitem'.split(',')
meeting_formfields = 'rowid,interest_id,meeting_id,order,title,agendaitem'.split(',')
meeting_dbmapping = dict(zip(meeting_dbattrs, meeting_formfields))
meeting_formmapping = dict(zip(meeting_formfields, meeting_dbattrs))

# see https://datatables.net/blog/2019-01-11#DataTables-Javascript for parent/child editing
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
         'name':None,
         'className': 'details-control',
         'orderable': False,
         'defaultContent': '',
         'width': '15px',
         'label': '',
         'render': {'eval':'render_plus'},
         },
        {'data': 'order', 'name': 'order', 'label': 'Order',
         'className': 'field_req',
         'display': False,
         },
        {'data': 'title', 'name': 'title', 'label': 'Title',
         'className': 'field_req',
         },
    ],
    serverside=True,
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'remove', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [2,'asc'],
    },
)
meeting.register()

