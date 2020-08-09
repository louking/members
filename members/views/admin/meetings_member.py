'''
meetings_member - handling for meetings member
====================================================================================
'''

# standard

# pypi
from . import bp
from ...model import db
from ...model import LocalInterest, Position
from flask import request

# homegrown
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

##########################################################################################
# meetingstatus endpoint
###########################################################################################

meetingstatus_dbattrs = 'id,interest_id,position'.split(',')
meetingstatus_formfields = 'rowid,interest_id,position'.split(',')
meetingstatus_dbmapping = dict(zip(meetingstatus_dbattrs, meetingstatus_formfields))
meetingstatus_formmapping = dict(zip(meetingstatus_formfields, meetingstatus_dbattrs))

class MeetingStatusView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        '''
        add meeting_id to query parameters
        '''
        super().beforequery()

        # add filters if requested
        self.queryparams['meeting_id'] = request.args.get('meeting_id', None)
        self.queryparams['invitekey'] = request.args.get('invitekey', None)

        # todo: this shouldn't be in queryparams
        self.queryparams['user_id'] = request.args.get('user_id', None)

        # remove empty parameters from query filters
        delfields = []
        for field in self.queryparams:
            if self.queryparams[field] == None:
                delfields.append(field)
        for field in delfields:
            del self.queryparams[field]

    def permission(self):
        prelim = super().permission()
        return prelim

    def updatetables(self, rows):
        pass

    def editor_method_postcommit(self, form):
        # this is here in case invites changed during edit action
        self.updatetables(self._responsedata)

    def open(self):
        super().open()
        self.updatetables(self.output_result['data'])


meetingstatus = MeetingStatusView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Position,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/meetings-members-guide.html'},
    pagename='My Status Reports',
    endpoint='admin.meetingstatus',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/meetingstatus',
    dbmapping=meetingstatus_dbmapping,
    formmapping=meetingstatus_formmapping,
    checkrequired=True,
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
        {'data': 'position', 'name': 'position', 'label': 'Report Title',
         'type': 'readonly',
         },
    ],
    childrowoptions= {
        'template': 'meetingstatus-child-row.njk',
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
meetingstatus.register()

