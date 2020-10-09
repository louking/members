'''
organization_admin - organization administrative handling
===========================================
'''
# standard

# pypi

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, TaskGroup, Tag, AgendaHeading
from ...model import Position
from ...model import localinterest_query_params, localinterest_viafilter

from loutilities.user.model import User
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_ORGANIZATION_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

class ParameterError(Exception): pass

debug = False

##########################################################################################
# positions endpoint
###########################################################################################

position_dbattrs = 'id,interest_id,position,description,taskgroups,users,emailgroups,has_status_report,agendaheading'.split(',')
position_formfields = 'rowid,interest_id,position,description,taskgroups,users,emailgroups,has_status_report,agendaheading'.split(',')
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
                        {'data': 'users', 'name': 'users', 'label': 'Members',
                         'fieldInfo': 'members who hold this position',
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

def set_bound_user(formrow):
    user = User.query.filter_by(name=formrow['user_id']).one()
    return user.id


def get_bound_user(dbrow):
    user = User.query.filter_by(id=dbrow.user_id).one()
    return user.name


assignposition_dbattrs = 'id,user_id,positions,taskgroups,tags'.split(',')
assignposition_formfields = 'rowid,user_id,positions,taskgroups,tags'.split(',')
assignposition_dbmapping = dict(zip(assignposition_dbattrs, assignposition_formfields))
assignposition_formmapping = dict(zip(assignposition_formfields, assignposition_dbattrs))
assignposition_dbmapping['user_id'] = set_bound_user
assignposition_formmapping['user_id'] = get_bound_user

assignposition = DbCrudApiInterestsRolePermissions(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_ORGANIZATION_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=LocalUser,
    version_id_col='version_id',  # optimistic concurrency control
    queryparams={'active': True},
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/organization-admin-guide.html'},
    pagename='Assign Positions',
    endpoint='admin.assignpositions',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/assignpositions',
    dbmapping=assignposition_dbmapping,
    formmapping=assignposition_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'user_id', 'name': 'user_id', 'label': 'Member',
         'className': 'field_req',
         '_unique': True,
         },
        {'data': 'positions', 'name': 'positions', 'label': 'Positions',
         'fieldInfo': 'tasks are assigned via position, task groups, or both',
         '_treatment': {
             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'positions',
                              'dbfield': 'positions', 'uselist': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
         'fieldInfo': 'tasks are assigned via position, task groups, or both',
         '_treatment': {
             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup',
                              'formfield': 'taskgroups',
                              'dbfield': 'taskgroups', 'uselist': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'tags', 'name': 'tags', 'label': 'Tags',
         'fieldInfo': 'tags are assigned via position, user, or both',
         '_treatment': {
             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag',
                              'formfield': 'tags',
                              'dbfield': 'tags', 'uselist': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['editRefresh', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
assignposition.register()

