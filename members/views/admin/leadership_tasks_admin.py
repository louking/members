'''
tasks - administrative task handling
===========================================
'''
# standard
from datetime import timedelta

# pypi

# homegrown
from . import bp
from ...model import db, LocalInterest, LocalUser, Task, TaskField, TaskGroup, TaskCompletion
from ...model import input_type_all, localinterest_query_params, localinterest_viafilter
from loutilities.user.model import User
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

debug = False

##########################################################################################
# tasks endpoint
###########################################################################################

task_dbattrs = 'id,interest_id,task,description,priority,period,fields'.split(',')
task_formfields = 'rowid,interest_id,task,description,priority,period,fields'.split(',')
task_dbmapping = dict(zip(task_dbattrs, task_formfields))
task_formmapping = dict(zip(task_formfields, task_dbattrs))
DAYS_PER_PERIOD = 7
task_dbmapping['period'] = lambda formrow: timedelta(int(formrow['period'])*DAYS_PER_PERIOD)
task_formmapping['period'] = lambda dbrow: dbrow.period.days // DAYS_PER_PERIOD

task = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Task,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    pagename = 'Tasks',
                    endpoint = 'admin.tasks',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/tasks',
                    dbmapping = task_dbmapping, 
                    formmapping = task_formmapping, 
                    clientcolumns = [
                        {'data': 'task', 'name': 'task', 'label': 'Task',
                         'className': 'field_req',
                         },
                        {'data': 'priority', 'name': 'priority', 'label': 'Priority'},
                        {'data': 'period', 'name': 'period', 'label': 'Period (weeks)'},
                        {'data': 'description', 'name': 'description', 'label': 'Display', 'type': 'textarea',
                         'fieldInfo': '<a href=https://daringfireball.net/projects/markdown/syntax target=_blank>Markdown</a>' +
                                      ' can be used. Click link for syntax'
                         },
                        {'data': 'fields', 'name': 'fields', 'label': 'Fields',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskField, 'labelfield': 'taskfield', 'formfield': 'fields',
                                              'dbfield': 'fields', 'uselist': True,
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
task.register()

##########################################################################################
# taskfields endpoint
###########################################################################################

taskfield_dbattrs = 'id,interest_id,taskfield,displaylabel,displayvalue,fieldinfo,inputtype,priority'.split(',')
taskfield_formfields = 'rowid,interest_id,taskfield,displaylabel,displayvalue,fieldinfo,inputtype,priority'.split(',')
taskfield_dbmapping = dict(zip(taskfield_dbattrs, taskfield_formfields))
taskfield_formmapping = dict(zip(taskfield_formfields, taskfield_dbattrs))

taskfield = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = TaskField,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    pagename = 'Task Fields',
                    endpoint = 'admin.taskfields',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskfields',
                    dbmapping = taskfield_dbmapping, 
                    formmapping = taskfield_formmapping, 
                    clientcolumns = [
                        {'data': 'taskfield', 'name': 'taskfield', 'label': 'Field Name',
                         'className': 'field_req',
                         # TODO: is this unique in the table or within an interest? Needs to be within an interest
                         '_unique': True,
                         },
                        {'data': 'priority', 'name': 'priority', 'label': 'Priority',
                         'className': 'field_req',
                         },
                        {'data': 'displaylabel', 'name': 'displaylabel', 'label': 'Field Label',
                         'className': 'field_req',
                         },
                        {'data': 'displayvalue', 'name': 'displayvalue', 'label': 'Field Value', 'type': 'textarea'},
                        {'data': 'inputtype', 'name': 'inputtype', 'label': 'Input Type',
                         'fieldInfo' : 'if you want the field to collect input, select the input type',
                         'type': 'select2',
                         'options': sorted(input_type_all),
                         'ed' :{
                             'opts' : {
                                 'placeholder' : 'Select input type',
                                 'allowClear' : True
                             }
                         },
                         },
                        {'data': 'fieldinfo', 'name': 'fieldinfo', 'label': 'Field Hint',
                         'fieldInfo': 'this gets displayed under the field to help the user fill in the form'
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
taskfield.register()

##########################################################################################
# taskgroups endpoint
###########################################################################################

taskgroup_dbattrs = 'id,interest_id,taskgroup,description,tasks,users'.split(',')
taskgroup_formfields = 'rowid,interest_id,taskgroup,description,tasks,users'.split(',')
taskgroup_dbmapping = dict(zip(taskgroup_dbattrs, taskgroup_formfields))
taskgroup_formmapping = dict(zip(taskgroup_formfields, taskgroup_dbattrs))

taskgroup = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = TaskGroup,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    pagename = 'Task Groups',
                    endpoint = 'admin.taskgroups',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskgroups',
                    dbmapping = taskgroup_dbmapping, 
                    formmapping = taskgroup_formmapping, 
                    clientcolumns = [
                        {'data': 'taskgroup', 'name': 'taskgroup', 'label': 'Task Group',
                         'className': 'field_req',
                         # TODO: is this unique in the table or within an interest? Needs to be within an interest
                         '_unique': True,
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Description',
                         'className': 'field_req',
                         },
                        {'data': 'tasks', 'name': 'tasks', 'label': 'Tasks',
                         '_treatment': {
                             'relationship': {'fieldmodel': Task, 'labelfield': 'task', 'formfield': 'tasks',
                                              'dbfield': 'tasks', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'users', 'name': 'users', 'label': 'Users',
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
taskgroup.register()

##########################################################################################
# usertaskgroups endpoint
###########################################################################################

def set_bound_user(formrow):
    user = User.query.filter_by(name=formrow['user_id']).one()
    return user.id

def get_bound_user(dbrow):
    user = User.query.filter_by(id=dbrow.user_id).one()
    return user.name
    
assigntaskgroup_dbattrs = 'id,user_id,taskgroups'.split(',')
assigntaskgroup_formfields = 'rowid,user_id,taskgroups'.split(',')
assigntaskgroup_dbmapping = dict(zip(assigntaskgroup_dbattrs, assigntaskgroup_formfields))
assigntaskgroup_formmapping = dict(zip(assigntaskgroup_formfields, assigntaskgroup_dbattrs))
assigntaskgroup_dbmapping['user_id'] = set_bound_user
assigntaskgroup_formmapping['user_id'] = get_bound_user

assigntaskgroup = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = LocalUser,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    queryparams = {'active': True},
                    template = 'datatables.jinja2',
                    pagename = 'Assign Task Groups',
                    endpoint = 'admin.assigntaskgroups',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/assigntaskgroups',
                    dbmapping = assigntaskgroup_dbmapping, 
                    formmapping = assigntaskgroup_formmapping,
                    clientcolumns = [
                        {'data': 'user_id', 'name': 'user_id', 'label': 'User',
                         'className': 'field_req',
                         # TODO: is this unique in the table or within an interest? Needs to be within an interest
                         '_unique': True,
                         },
                        {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup', 'formfield': 'taskgroups',
                                              'dbfield': 'taskgroups', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = ['editRefresh', 'csv'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
assigntaskgroup.register()
