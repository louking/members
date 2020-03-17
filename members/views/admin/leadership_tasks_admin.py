'''
tasks - administrative task handling
===========================================
'''
# standard
from copy import deepcopy

# pypi

# homegrown
from . import bp
from ... import app
from ...model import db, LocalInterest, TaskType, Task, TaskField, InputType, TaskGroup, UserTaskCompletion
from loutilities.user.model import Role, Interest
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER
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
                        { 'data': 'tasktype', 'name': 'tasktype', 'label': 'Task Type',
                          'className': 'field_req',
                          },
                        { 'data': 'description', 'name': 'description', 'label': 'Description' },
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
tasktype.register()

