'''
tasks - administrative task handling
===========================================
'''
# standard
from datetime import timedelta

# pypi

# homegrown
from . import bp
from ... import app
from ...model import db, LocalInterest, TaskType, Task, TaskField, InputType, TaskGroup, UserTaskCompletion
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER
from loutilities.tables import DbCrudApiRolePermissions # only for InputType
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

debug = False

##########################################################################################
# tasktypes endpoint
###########################################################################################

tasktype_dbattrs = 'id,interest_id,tasktype,description'.split(',')
tasktype_formfields = 'rowid,interest_id,tasktype,description'.split(',')
tasktype_dbmapping = dict(zip(tasktype_dbattrs, tasktype_formfields))
tasktype_formmapping = dict(zip(tasktype_formfields, tasktype_dbattrs))

tasktype = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = TaskType,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    pagename = 'Task Types',
                    endpoint = 'admin.tasktypes',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/tasktypes',
                    dbmapping = tasktype_dbmapping, 
                    formmapping = tasktype_formmapping, 
                    clientcolumns = [
                        {'data': 'tasktype', 'name': 'tasktype', 'label': 'Task Type',
                         'className': 'field_req',
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Description'},
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
tasktype.register()

##########################################################################################
# tasks endpoint
###########################################################################################

task_dbattrs = 'id,interest_id,task,description,priority,period,tasktype'.split(',')
task_formfields = 'rowid,interest_id,task,description,priority,period,tasktype'.split(',')
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
                        {'data': 'tasktype', 'name': 'tasktype', 'label': 'Task Type',
                         '_treatment': {'relationship': {'fieldmodel': TaskType, 'labelfield': 'tasktype', 'formfield': 'tasktype',
                                                        'dbfield': 'tasktype', 'uselist': False}}
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Description', 'type': 'textarea'},
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
# inputtypes endpoint
###########################################################################################

inputtype_dbattrs = 'id,inputtype'.split(',')
inputtype_formfields = 'rowid,inputtype'.split(',')
inputtype_dbmapping = dict(zip(inputtype_dbattrs, inputtype_formfields))
inputtype_formmapping = dict(zip(inputtype_formfields, inputtype_dbattrs))

#??  need to use DbCrudApiInterestsRolePermissions even if this table doesn't use local interest
inputtype = DbCrudApiRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = InputType,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    pagename = 'Input Types',
                    endpoint = 'admin.inputtypes',
                    rule = '/inputtypes',
                    dbmapping = inputtype_dbmapping,
                    formmapping = inputtype_formmapping,
                    clientcolumns = [
                        {'data': 'inputtype', 'name': 'inputtype', 'label': 'inputtype',
                         'className': 'field_req',
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid',
                    buttons = ['create', 'editRefresh', 'remove'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
inputtype.register()

