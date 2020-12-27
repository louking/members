'''
organization_admin - organization administrative handling
===========================================
'''
# standard
from datetime import date

# pypi
from dominate.tags import div, label, input, a, span

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, TaskGroup, Tag, AgendaHeading, UserPosition
from ...model import Position
from ...model import localinterest_query_params
from .viewhelpers import dtrender

from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption
from loutilities.tables import get_request_action
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_ORGANIZATION_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

class ParameterError(Exception): pass

debug = False

##########################################################################################
# positions endpoint
###########################################################################################

position_dbattrs = 'id,interest_id,position,description,taskgroups,emailgroups,has_status_report,agendaheading'.split(',')
position_formfields = 'rowid,interest_id,position,description,taskgroups,emailgroups,has_status_report,agendaheading'.split(',')
position_dbmapping = dict(zip(position_dbattrs, position_formfields))
position_formmapping = dict(zip(position_formfields, position_dbattrs))

position = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_ORGANIZATION_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Position,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/organization-admin-guide.html'},
                    pagename = 'Positions',
                    endpoint = 'admin.positions',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/positions',
                    dbmapping = position_dbmapping,
                    formmapping = position_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'position', 'name': 'position', 'label': 'Position',
                         'className': 'field_req',
                         '_unique': True,
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Description',
                         'type': 'textarea',
                         },
                        # {'data': 'users', 'name': 'users', 'label': 'Members',
                        #  'fieldInfo': 'members who hold this position',
                        #  '_treatment': {
                        #      # viadbattr stores the LocalUser id which has user_id=user.id for each of these
                        #      # and pulls the correct users out of User based on LocalUser table
                        #      'relationship': {'fieldmodel': User, 'labelfield': 'name',
                        #                       'formfield': 'users', 'dbfield': 'users',
                        #                       'viadbattr': LocalUser.user_id,
                        #                       'viafilter': localinterest_viafilter,
                        #                       'queryparams': {'active': True},
                        #                       'uselist': True}}
                        #  },
                        {'data': 'has_status_report', 'name': 'has_status_report', 'label': 'Has Status Report',
                         'className': 'TextCenter',
                         '_treatment': {'boolean': {'formfield': 'has_status_report', 'dbfield': 'has_status_report'}},
                         'ed': {'def': 'yes'},
                         },
                        {'data': 'agendaheading', 'name': 'agendaheading', 'label': 'Agenda Heading',
                         'fieldInfo': 'heading under which this position is shown in agenda',
                         '_treatment': {
                             'relationship': {'fieldmodel': AgendaHeading, 'labelfield': 'heading', 'formfield': 'agendaheading',
                                              'dbfield': 'agendaheading', 'uselist': False,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
                         'fieldInfo': 'members who hold this position must do tasks within these groups',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup', 'formfield': 'taskgroups',
                                              'dbfield': 'taskgroups', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'emailgroups', 'name': 'emailgroups', 'label': 'Email Groups',
                         'fieldInfo': 'members holding this position receive summary emails about other members configured with these groups',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup',
                                              'formfield': 'emailgroups',
                                              'dbfield': 'emailgroups', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid',
                    buttons = ['create', 'editRefresh', 'remove', 'csv'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
position.register()


##########################################################################################
# assignpositions endpoint
###########################################################################################

assignposition_dbattrs = 'id,user,position,user.taskgroups,user.tags,startdate,finishdate'.split(',')
assignposition_formfields = 'rowid,user,position,taskgroups,tags,startdate,finishdate'.split(',')
assignposition_dbmapping = dict(zip(assignposition_dbattrs, assignposition_formfields))
assignposition_formmapping = dict(zip(assignposition_formfields, assignposition_dbattrs))
# see https://github.com/DataTables/Plugins/commit/eb06604fdc9d5
# see https://datatables.net/forums/discussion/25433
assignposition_dbmapping['startdate'] = lambda formrow: dtrender.asc2dt(formrow['startdate'])
assignposition_formmapping['startdate'] = lambda dbrow: dtrender.dt2asc(dbrow.startdate)
assignposition_dbmapping['finishdate'] = lambda formrow: dtrender.asc2dt(formrow['finishdate']) if formrow['finishdate'] else None
# assignposition_formmapping['finishdate'] = lambda dbrow: dtrender.dt2asc(dbrow.finishdate) if dbrow.finishdate else None
assignposition_formmapping['finishdate'] = lambda dbrow: dtrender.dt2asc(dbrow.finishdate) if dbrow.finishdate else ''

class AssignPositionView(DbCrudApiInterestsRolePermissions):
    def editor_method_postcommit(self, formdata):
        '''
        updates to taskgroups and tags affect multiple rows related to the user(s) impacted, so need to update
        self._responsedata to show changes to those rows

        :param formdata: form data
        '''
        super().editor_method_postcommit(formdata)
        action = get_request_action(formdata)
        if action == 'edit':
            userids = set()
            upids = set()
            for row in self._responsedata:
                userids.add(row['user']['id'])
                upids.add(row['rowid'])
            otherrows = []
            for userid in userids:
                ups = UserPosition.query.filter_by(user_id=userid).all()
                otherrows += [self.dte.get_response_data(up) for up in ups if up.id not in upids]
            self._responsedata += otherrows

def assignposition_pretablehtml():
    pretablehtml = div()
    with pretablehtml:
        # hide / show hidden rows
        with filtercontainerdiv(style='margin-bottom: 4px;'):
            filterdiv('assignposition-external-filter-startdate', 'In Position On')

        # with datefilter:
        #     label('In Position On', _for='effective-date')
        #     input(type='text', id='effective-date', name='effective-date', value=dtrender.dt2asc(date.today()))
        #     a('Clear Date', id='clear-date', href='#')
        # filters = div(style='display: none;')
    return pretablehtml.render()

assignposition_yadcf_options = {
    # 'general': {'cumulative_filtering': True},
    'columns': [
        yadcfoption('startdate:name', 'assignposition-external-filter-startdate', 'date_custom_func',
                    custom_func={'eval': 'yadcf_between_dates("startdate", "finishdate")'},
                    filter_reset_button_text='Clear Date',
                    ),
        # yadcfoption('finishdate:name', 'assignposition-external-filter-finishdate', 'range_date'),
    ]
}

assignposition = AssignPositionView(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_ORGANIZATION_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=UserPosition,
    version_id_col='version_id',  # optimistic concurrency control
    # queryparams={'active': True},
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/organization-admin-guide.html'},
    pagename='Assign Positions',
    endpoint='admin.assignpositions',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/assignpositions',
    dbmapping=assignposition_dbmapping,
    formmapping=assignposition_formmapping,
    checkrequired=True,
    pretablehtml=assignposition_pretablehtml,
    yadcfoptions=assignposition_yadcf_options,
    clientcolumns=[
        {'data': 'user', 'name': 'user', 'label': 'Member',
         'className': 'field_req',
         '_treatment': {
             'relationship': {'fieldmodel': LocalUser, 'labelfield': 'name', 'formfield': 'user',
                              'dbfield': 'user', 'uselist': False,
                              'searchbox': True,
                              'queryparams': {'active': True},
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'position', 'name': 'position', 'label': 'Position',
         'className': 'field_req',
         'fieldInfo': 'tasks are assigned via position, task groups, or both',
         '_treatment': {
             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'position',
                              'dbfield': 'position', 'uselist': False,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'startdate', 'name': 'startdate', 'label': 'Start Date',
         'type': 'datetime',
         'className': 'field_req',
         # 'render': {'eval': 'render_date()'},
         },
        {'data': 'finishdate', 'name': 'finishdate', 'label': 'Finish Date',
         'type': 'datetime',
         # 'render': {'eval': 'render_date()'},
         },
        # {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
        #  'fieldInfo': 'tasks are generally assigned via position',
        #  '_treatment': {
        #      'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup',
        #                       'viasubrecord': 'user',
        #                       'formfield': 'taskgroups',
        #                       'dbfield': 'taskgroups', 'uselist': True,
        #                       'queryparams': localinterest_query_params,
        #                       }}
        #  },
        # {'data': 'tags', 'name': 'tags', 'label': 'Tags',
        #  'fieldInfo': 'tasks are generally assigned via position',
        #  '_treatment': {
        #      'relationship': {'fieldmodel': Tag, 'labelfield': 'tag',
        #                       'viasubrecord': 'user',
        #                       'formfield': 'tags',
        #                       'dbfield': 'tags', 'uselist': True,
        #                       'queryparams': localinterest_query_params,
        #                       }}
        #  },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
assignposition.register()

