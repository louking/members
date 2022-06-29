'''
leadership_tasks_admin - leadership task administrative handling
===========================================
'''
# standard
from datetime import date
from re import match

# pypi
from flask import g, url_for, request
from flask_security import current_user
from slugify import slugify
from dominate.tags import input, button

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Task, TaskField, TaskGroup, TaskTaskField, TaskCompletion
from ...model import Position
from ...model import input_type_all, localinterest_query_params, localinterest_viafilter, gen_fieldname
from ...model import FIELDNAME_ARG, INPUT_TYPE_UPLOAD, INPUT_TYPE_DISPLAY
from ...model import date_unit_all, DATE_UNIT_WEEKS, DATE_UNIT_MONTHS, DATE_UNIT_YEARS
from ...version import __docversion__
from ...helpers import positions_active
from .viewhelpers import lastcompleted, get_status, get_order, get_expires, localinterest
from .viewhelpers import get_position_taskgroups, get_taskgroup_taskgroups
from .viewhelpers import create_taskcompletion, get_task_completion, user2localuser, localuser2user
from .viewhelpers import get_fieldoptions, get_taskfields
from .viewhelpers import get_member_tasks
from .viewhelpers import dtrender, dttimerender
from .viewhelpers import EXPIRES_SOON, PERIOD_WINDOW_DISPLAY, STATUS_DISPLAYORDER

# this is just to pick up list() function
from .leadership_tasks_member import fieldupload

from loutilities.user.model import User
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions, AssociationSelect, AssociationCrudApi
from loutilities.tables import DteDbRelationship, get_request_action, get_request_data
from loutilities.tables import SEPARATOR, REGEX_ISODATE
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption

class ParameterError(Exception): pass

debug = False

adminguide = 'https://members.readthedocs.io/en/{docversion}/leadership-task-admin-guide.html'.format(docversion=__docversion__)

##########################################################################################
# tasks endpoint
###########################################################################################

class TaskView(AssociationCrudApi):

    def editor_method_posthook(self, form):
        '''
        do validation after editor method because we want all processing to have taken place before
        we try to read thistask.fields
        '''
        action = get_request_action(form)

        # we only have to worry about create and edit functions
        if action == 'create':
            thisid = self.created_id
        elif action in ['edit', 'editRefresh']:
            # kludge to get task.id
            # NOTE: this is only called from 'edit' / put function, and there will be only one id
            thisid = list(get_request_data(form).keys())[0]
        else:
            return

        thistask = Task.query.filter_by(id=thisid).one()

        # build sets of duplicated fields
        duplicated = set()
        found = set()

        for tasktaskfield in thistask.fields:
            taskfield = tasktaskfield.taskfield
            if taskfield.fieldname in found:
                duplicated.add(taskfield.fieldname)
            found.add(taskfield.fieldname)

        # indicate error for any fields which were duplicated
        if duplicated:
            dupnames = [TaskField.query.filter_by(fieldname=fn).one().taskfield for fn in list(duplicated)]
            self._fielderrors = [{'name': 'fields.id', 'get_status': '{} fields were found in more than one category'.format(dupnames)}]
            raise ParameterError

        # disable position if not isbyposition
        if not thistask.isbyposition:
            thistask.position = None
            self._responsedata[0]['position']['id'] = None
            self._responsedata[0]['position']['position'] = None
        
        # update any affected taskcompletions
        # this allows the isbyposition or position to change with the completed tasks updated accordingly
        taskcompletions = TaskCompletion.query.filter_by(task=thistask).filter(TaskCompletion.position != thistask.position).all()
        for taskcompletion in taskcompletions:
            taskcompletion.position = thistask.position
        
def task_validate(action, formdata):
    results = []

    # TODO: remove this when #51 fixed
    from re import compile
    # datepattern = compile('^(19|20)\d\d[-](0[1-9]|1[012])[-](0[1-9]|[12][0-9]|3[01])$')
    datepattern = compile('^(0[1-9]|1[012])[-](0[1-9]|[12][0-9]|3[01])$')
    if formdata['dateofyear'] and not datepattern.match(formdata['dateofyear']):
        results.append({'name': 'dateofyear', 'status': 'must be formatted as MM-DD'})

    # if both of these are set, they will conflict with each other
    if formdata['period'] and formdata['dateofyear']:
        results.append({'name': 'period', 'status': 'only one of these should be supplied'})
        results.append({'name': 'dateofyear', 'status': 'only one of these should be supplied'})

    # expirysoon is needed for nonoptional tasks which have a period or dateofyear
    if formdata['isoptional'] != 'yes' and (formdata['period'] or formdata['dateofyear']):
        if not formdata['expirysoon']:
            results.append({'name': 'expirysoon', 'status': 'please supply'})

    # for task completion by position, a position needs to be supplied
    if formdata['isbyposition'] == 'yes' and not formdata['position']['id']:
        results.append({'name': 'position.id', 'status': 'please supply'})
        
    return results

task_dbattrs = 'id,interest_id,task,description,isbyposition,position,priority,expirysoon,expirysoon_units,period,period_units,dateofyear,expirystarts,expirystarts_units,isoptional,taskgroups,fields'.split(',')
task_formfields = 'rowid,interest_id,task,description,isbyposition,position,priority,expirysoon,expirysoon_units,period,period_units,dateofyear,expirystarts,expirystarts_units,isoptional,taskgroups,fields'.split(',')
task_dbmapping = dict(zip(task_dbattrs, task_formfields))
task_formmapping = dict(zip(task_formfields, task_dbattrs))
# only take mm-dd portion of date into database
# TODO: uncomment these when #51 fixed
# task_dbmapping['dateofyear'] = lambda formrow: formrow['dateofyear'][-5:] if formrow['dateofyear'] else None
# task_formmapping['dateofyear'] = lambda dbrow: '{}-{}'.format(date.today().year, dbrow.dateofyear) if dbrow.dateofyear else None

task_view = TaskView(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Task,
                    assnmodelfield='task',
                    assnlistfield='fields',
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'tasks.view.jinja2',
                    templateargs={'adminguide': adminguide},
                    pagename = 'Tasks',
                    endpoint = 'admin.tasks',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/tasks',
                    dbmapping = task_dbmapping, 
                    formmapping = task_formmapping, 
                    checkrequired = True,
                    validate = task_validate,
                    clientcolumns = [
                        {'data': 'task', 'name': 'task', 'label': 'Task',
                         'className': 'field_req',
                         },
                        {'data': 'priority', 'name': 'priority', 'label': 'Priority',
                         'className': 'field_req',
                         'class': 'TextCenter',
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Display', 'type': 'textarea',
                         'className': 'field_req',
                         'render': {'eval': '$.fn.dataTable.render.ellipsis( 80 )'},
                         'fieldInfo': '<a href=https://daringfireball.net/projects/markdown/syntax target=_blank>Markdown</a>' +
                                      ' can be used. Click link for syntax'
                         },
                        {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
                         'fieldInfo': 'task groups this task should be associated with',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup',
                                              'formfield': 'taskgroups',
                                              'dbfield': 'taskgroups', 'uselist': True,
                                              'searchbox': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'isbyposition', 'name': 'isbyposition', 'label': 'Position Based',
                         'class': 'TextCenter',
                         '_treatment': {'boolean': {'formfield': 'isbyposition', 'dbfield': 'isbyposition'}},
                         'ed': {'def': 'no'},
                         'fieldInfo': 'if yes, task completion occurs when anyone in the indicated Position completes; if no, all individuals assigned must complete',
                         },
                        {'data': 'position', 'name': 'position', 'label': 'Position',
                         '_treatment': {
                             'relationship': 
                                {
                                    'fieldmodel': Position, 
                                    'labelfield': 'position', 
                                    'formfield': 'position',
                                    'dbfield': 'position', 
                                    'uselist': False,
                                    'searchbox': True,
                                    'queryparams': localinterest_query_params,
                                }},
                         'fieldInfo': 'required if Position Based = yes, otherwise ignored',
                         },
                        {'data': 'expirysoon', 'name': 'expirysoon', 'label': 'Expires Soon',
                         'class': 'TextCenter',
                         'fieldInfo': 'time before task expires to start indicating "expires soon"',
                         'ed': {'def': EXPIRES_SOON / PERIOD_WINDOW_DISPLAY}
                         },
                        {'data': 'expirysoon_units', 'name': 'expirysoon_units', 'label': '',
                         'type': 'select2',
                         'className': 'inhibitlabel',
                         'options': date_unit_all,
                         'ed' :{
                             'def': DATE_UNIT_WEEKS
                         },
                         },
                        {'data': 'fields', 'name': 'fields', 'label': 'Fields',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker':
                                     AssociationSelect(
                                         tablemodel=Task,
                                         associationtablemodelfield='task',
                                         associationmodel=TaskTaskField,
                                         associationfields=['need', 'taskfield'],
                                         selectattrs=[TaskTaskField.need, TaskField.taskfield],
                                         labelfield='fields',
                                         formfield='fields',
                                         dbfield='fields', uselist=True,
                                         queryparams=localinterest_query_params,
                                     )
                             }}
                         },
                        {'data': 'period', 'name': 'period', 'label': 'Period',
                         'fieldInfo': 'Period or Date of Year may be specified. Leave blank if this task doesn\'t need to be done periodically',
                         'class': 'TextCenter',
                         },
                        {'data': 'period_units', 'name': 'period_units', 'label': '',
                         'type': 'select2',
                         'className': 'inhibitlabel',
                         'options': date_unit_all,
                         'ed' :{
                             'def': DATE_UNIT_YEARS
                         },
                         },
                        {'data': 'dateofyear', 'name': 'dateofyear', 'label': 'Date of Year',
                         # TODO: uncomment these when #51 fixed
                         # 'type': 'datetime',
                         # 'render': {'eval': 'render_month_date'},
                         # 'ed': {'displayFormat': 'MM-DD', 'wireFormat':'YYYY-MM-DD', 'def': None},
                         'fieldInfo': 'Period or Date of Year may be specified. Leave blank if this task doesn\'t need to be done by a particular date',
                         # TODO: remove this when #51 fixed
                         'ed': {'label': 'Date of Year (mm-dd)'},
                         },
                        {'data': 'expirystarts', 'name': 'expirystarts', 'label': 'Overdue Starts',
                         'fieldInfo': 'only used if Date of Year specified. time after task expires to start indicating "overdue"',
                         'class': 'TextCenter',
                         },
                        {'data': 'expirystarts_units', 'name': 'expirystarts_units', 'label': '',
                         'type': 'select2',
                         'className': 'inhibitlabel',
                         'options': date_unit_all,
                         'ed' :{
                             'def': DATE_UNIT_MONTHS
                         },
                         },
                        {'data': 'isoptional', 'name': 'isoptional', 'label': 'Optional Task',
                         'class': 'TextCenter',
                         '_treatment': {'boolean': {'formfield': 'isoptional', 'dbfield': 'isoptional'}},
                         'ed': {'def': 'no'},
                         'fieldInfo': 'indicates if task completion is optional',
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
                    edoptions = {
                        'template': '#customForm',
                    }
                    )
task_view.register()

##########################################################################################
# taskfields endpoint
###########################################################################################

taskfield_dbattrs = 'id,interest_id,taskfield,fieldname,displaylabel,displayvalue,fieldinfo,fieldoptions,inputtype,priority,uploadurl,override_completion'.split(',')
taskfield_formfields = 'rowid,interest_id,taskfield,fieldname,displaylabel,displayvalue,fieldinfo,fieldoptions,inputtype,priority,uploadurl,override_completion'.split(',')
taskfield_dbmapping = dict(zip(taskfield_dbattrs, taskfield_formfields))
taskfield_formmapping = dict(zip(taskfield_formfields, taskfield_dbattrs))

from ...model import INPUT_TYPE_CHECKBOX, INPUT_TYPE_RADIO, INPUT_TYPE_SELECT2
INPUT_TYPE_HASOPTIONS = [INPUT_TYPE_CHECKBOX, INPUT_TYPE_RADIO, INPUT_TYPE_SELECT2]

taskfield_formmapping['fieldoptions'] = get_fieldoptions

class TaskFieldCrud(DbCrudApiInterestsRolePermissions):
    def createrow(self, formdata):
        taskfieldrow = super().createrow(formdata)
        taskfield = TaskField.query.filter_by(id=self.created_id).one()
        taskfield.fieldname = gen_fieldname()
        if taskfield.inputtype == INPUT_TYPE_UPLOAD:
            taskfield.uploadurl = (url_for('admin.fieldupload', interest=g.interest)
                                          + '?{}={}'.format(FIELDNAME_ARG, taskfield.fieldname))
        return self.dte.get_response_data(taskfield)

taskfield_view = TaskFieldCrud(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = TaskField,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
                    pagename = 'Task Fields',
                    endpoint = 'admin.taskfields',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskfields',
                    dbmapping = taskfield_dbmapping, 
                    formmapping = taskfield_formmapping, 
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'taskfield', 'name': 'taskfield', 'label': 'Field',
                         'className': 'field_req',
                         '_unique': True,
                         },
                        {'data': 'priority', 'name': 'priority', 'label': 'Priority',
                         'className': 'field_req',
                         },
                        {'data': 'displaylabel', 'name': 'displaylabel', 'label': 'Field Label',
                         'className': 'field_req',
                         },
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
                        # see taskfield_formmapping and afterdatatables.js editor.on('initEdit', ...
                        {'data': 'fieldoptions', 'name': 'fieldoptions', 'label': 'Options',
                         'type': 'select2', 'separator':SEPARATOR,
                         'options': [],
                         'opts': {
                             'multiple': 'multiple',
                             'tags': True
                         }
                         },
                        {'data': 'fieldinfo', 'name': 'fieldinfo', 'label': 'Field Hint',
                         'fieldInfo': 'this gets displayed under the field to help the user fill in the form'
                         },
                        {'data': 'displayvalue', 'name': 'displayvalue', 'label': 'Field Value', 'type': 'textarea',
                         'render': {'eval': '$.fn.dataTable.render.ellipsis( 80 )'},
                         'fieldInfo': 'text to display for {} Input Type (display-only)'.format(INPUT_TYPE_DISPLAY)},
                        {'data': 'fieldname', 'name': 'fieldname', 'label': 'Field Name', 'type': 'readonly'
                         },
                        {'data': 'uploadurl', 'name': 'uploadurl', 'label': 'Upload URL', 'type': 'readonly'
                         },
                        {'data': 'override_completion', 'name': 'override_completion', 'label': 'Override Completion',
                         '_treatment': {'boolean': {'formfield': 'override_completion', 'dbfield': 'override_completion'}},
                         'fieldInfo': 'if \'yes\' this field overrides date when member marks task completed',
                         'ed': {'def': 'no'},
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
taskfield_view.register()

##########################################################################################
# taskgroups endpoint
###########################################################################################

def _validate_branch(taskgroup, branchlist):
    '''
    recursively check if this taskgroup in branchlist -- if it is, there's an error

    :param taskgroup: task group to check
    :param branchlist: list of task groups so far in this branch
    :return: results error list
    '''
    results = []
    if taskgroup.id in branchlist:
        branchnames = ', '.join(["'{}'".format(TaskGroup.query.filter_by(id=id).one().taskgroup) for id in branchlist])
        results = [{'name': 'tgtaskgroups.id', 'status': 'task group loop found: \'{}\' repeated following {}'.format(taskgroup.taskgroup, branchnames)}]

    else:
        thisbranch = branchlist + [taskgroup.id]
        for tg in taskgroup.taskgroups:
            results = _validate_branch(tg, thisbranch)
            if results: break

    return results

def _validate_taskgroup(action, formdata):
    results = []

    # NOTE: only using from 'create', 'edit' functions, so assuming there will be only one id
    if action == 'create':
        initialbranch = []
    elif action == 'edit':
        # kludge to get referenced taskgroup.id
        thisid = int(list(get_request_data(request.form).keys())[0])
        initialbranch = [thisid]
    else:
        return results

    # recursively look through all task groups this task group refers to
    # if the any task group is referenced more than once on a branch then we have a loop
    # stop at first problem
    for tgid in formdata['tgtaskgroups']['id'].split(SEPARATOR):
        # if empty string, no ids were supplied
        if tgid == '': break
        taskgroup = TaskGroup.query.filter_by(id=tgid).one()
        results = _validate_branch(taskgroup, initialbranch)
        if results: break

    return results

taskgroup_dbattrs = 'id,interest_id,taskgroup,description,tasks,positions,users,taskgroups'.split(',')
taskgroup_formfields = 'rowid,interest_id,taskgroup,description,tasks,positions,users,tgtaskgroups'.split(',')
taskgroup_dbmapping = dict(zip(taskgroup_dbattrs, taskgroup_formfields))
taskgroup_formmapping = dict(zip(taskgroup_formfields, taskgroup_dbattrs))

taskgroup_view = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = TaskGroup,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
                    pagename = 'Task Groups',
                    endpoint = 'admin.taskgroups',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskgroups',
                    dbmapping = taskgroup_dbmapping, 
                    formmapping = taskgroup_formmapping,
                    checkrequired = True,
                    validate = _validate_taskgroup,
                    clientcolumns = [
                        {'data': 'taskgroup', 'name': 'taskgroup', 'label': 'Task Group',
                         'className': 'field_req',
                         # TODO: is this unique in the table or within an interest? Needs to be within an interest
                         '_unique': True,
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Description',
                         'className': 'field_req',
                         },
                        # note name tgtaskgroups rather than taskgroups to avoid conflict with name in tasks subform
                        # see also #55
                        {'data': 'tgtaskgroups', 'name': 'tgtaskgroups', 'label': 'Task Groups',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup', 'formfield': 'tgtaskgroups',
                                              'dbfield': 'taskgroups', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'tasks', 'name': 'tasks', 'label': 'Tasks',
                         '_treatment': {
                             'relationship': {'fieldmodel': Task, 'labelfield': 'task', 'formfield': 'tasks',
                                              'dbfield': 'tasks', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              'editable' : { 'api' : task_view },
                                              }}
                         },
                        {'data': 'positions', 'name': 'positions', 'label': 'Positions',
                         '_treatment': {
                             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'positions',
                                              'dbfield': 'positions', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'users', 'name': 'users', 'label': 'Members',
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
taskgroup_view.register()

##########################################################################################
# taskdetails endpoint
###########################################################################################

def taskdetails_addlfields(task, member):
    tc = get_task_completion(task, member)
    return get_taskfields(tc, task)

# map id to rowid, retrieve all other required fields
# no dbmapping because this table is read-only
taskdetails_dbattrs = 'id,member,task,lastcompleted,status,order,expires,fields,task_taskgroups,member_taskgroups,member_positions'.split(',')
taskdetails_formfields = 'rowid,member,task,lastcompleted,status,order,expires,fields,task_taskgroups,member_taskgroups,member_positions'.split(',')
taskdetails_dbmapping = dict(zip(taskdetails_dbattrs, taskdetails_formfields))

taskdetails_formmapping = {}
taskdetails_formmapping['rowid'] = 'id'
taskdetails_formmapping['task_taskgroups'] = 'task_taskgroups'
taskdetails_formmapping['member_taskgroups'] = 'member_taskgroups'
taskdetails_formmapping['member_positions'] = 'member_positions'
taskdetails_formmapping['member'] = lambda tu: tu.member.name
taskdetails_formmapping['task'] = lambda tu: tu.task.task
taskdetails_formmapping['lastcompleted'] = lambda tu: lastcompleted(tu.task, tu.member)
taskdetails_formmapping['status'] = lambda tu: get_status(tu.task, tu.member)
taskdetails_formmapping['order'] = lambda tu: get_order(tu.task, tu.member)
taskdetails_formmapping['expires'] = lambda tu: get_expires(tu.task, tu.member)
taskdetails_formmapping['fields'] = lambda tu: 'yes' if tu.task.fields else ''
taskdetails_formmapping['addlfields'] = lambda tu: taskdetails_addlfields(tu.task, tu.member)

class TaskMember():
    '''
    allows creation of "taskuser" object to simulate database behavior
    '''
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

class TaskDetails(DbCrudApiInterestsRolePermissions):

    def getids(self, id):
        '''
        return split of id into local user id, task id
        :param id: id for each TaskMember entry
        :return: (localuserid, taskid)
        '''
        return tuple([int(usertask) for usertask in id.split(';')])

    def setid(self, userid, taskid):
        '''
        return combined userid, taskid
        :param userid: id for each LocalUser entry
        :param taskid: id for each Task entry
        :return: id
        '''
        return ';'.join([str(userid), str(taskid)])

    def open(self):
        locinterest = localinterest()
        localusersdb = LocalUser.query.filter_by(interest=locinterest).all()

        # collect all the members
        localusers = set()
        for localuser in localusersdb:
            localusers |= {localuser}

        # retrieve member data from localusers
        members = []
        for localuser in iter(localusers):
            # None can be returned, but it seems like this should happen only if the User table was manipulated
            # manually without adjusting the LocalUser table accordingly.
            # This should only happen in development testing of member management
            user = User.query.filter_by(id=localuser.user_id).one_or_none()
            if user:
                members.append({'localuser':localuser, 'member': user})

        tasksmembers = []
        for member in members:
            # collect all the tasks which are referenced by positions and taskgroups for this member
            ondate = request.args.get('ondate', date.today())
            tasks = get_member_tasks(member['localuser'], ondate)

            # create/add taskmember to list for all tasks
            active_positions = positions_active(member['localuser'], ondate)
            for task in iter(tasks):
                membertaskid = self.setid(member['localuser'].id, task.id)
                taskmember = TaskMember(
                    id=membertaskid,
                    task=task, task_taskgroups=task.taskgroups,
                    member=member['member'],
                    member_positions=active_positions,
                )

                # drill down to get all the taskgroups
                member_taskgroups = set()
                for position in active_positions:
                    get_position_taskgroups(position, member_taskgroups)
                for taskgroup in member['localuser'].taskgroups:
                    get_taskgroup_taskgroups(taskgroup, member_taskgroups)
                taskmember.member_taskgroups = member_taskgroups

                tasksmembers.append(taskmember)

        self.rows = iter(tasksmembers)

    def updaterow(self, thisid, formdata):
        '''
        just update TaskCompletion.completion

        :param thisid:
        :param formdata:
        :return:
        '''
        memberid, taskid = self.getids(thisid)
        luser = LocalUser.query.filter_by(id=memberid).one()
        task = Task.query.filter_by(id=taskid).one()

        # create new TaskCompletion record, update the task completion time and user who made the update
        tc = create_taskcompletion(task, luser, self.localinterest, formdata)
        tc.completion = dtrender.asc2dt(formdata['lastcompleted'])
        tc.updated_by = user2localuser(current_user).id

        member = {'localuser': luser, 'member': User.query.filter_by(id=luser.user_id).one()}

        ondate = request.args.get('ondate', date.today())
        taskmember = TaskMember(
            id=thisid,
            task=task, task_taskgroups=task.taskgroups,
            member=member['member'],
            member_positions=positions_active(member['localuser'], ondate),
        )

        # drill down to get all the taskgroups
        member_taskgroups = set()
        for position in positions_active(member['localuser'], ondate):
            get_position_taskgroups(position, member_taskgroups)
        for taskgroup in member['localuser'].taskgroups:
            get_taskgroup_taskgroups(taskgroup, member_taskgroups)
        taskmember.member_taskgroups = member_taskgroups

        return self.dte.get_response_data(taskmember)

    def refreshrows(self, ids):
        '''
        refresh row(s) from database

        :param ids: comma separated ids of row to be refreshed
        :rtype: list of returned rows for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        theseids = ids.split(',')
        responsedata = []
        ondate = request.args.get('ondate', date.today())
        for thisid in theseids:
            # id is made up of localuser.id, task.id
            localuserid, taskid = self.getids(thisid)
            localuser = LocalUser.query.filter_by(id=localuserid).one()
            task = Task.query.filter_by(id=taskid).one()

            member = {'localuser': localuser, 'member': User.query.filter_by(id=localuser.user_id).one()}

            taskuser = TaskMember(
                id=thisid,
                task=task, task_taskgroups=task.taskgroups,
                member=member['member'],
                member_positions=positions_active(member['localuser'], ondate),
                member_taskgroups=member['localuser'].taskgroups,
            )

            responsedata.append(self.dte.get_response_data(taskuser))

        return responsedata

class ReadOnlySelect2(DteDbRelationship):
    def col_options(self):
        col = super().col_options()
        # readonly select2
        col['opts']['disabled'] = True
        return col

def taskdetails_validate(action, formdata):
    results = []

    # kludge to get task.id
    # NOTE: this is only called from 'edit' / put function, and there will be only one id
    thisid = list(get_request_data(request.form).keys())[0]

    # id is made up of localuser.id, task.id
    localuserid, taskid = taskdetails_view.getids(thisid)
    task = Task.query.filter_by(id=taskid).one()

    # build list of fields which could override completion date (should only be one)
    override_completion = []
    for tasktaskfield in task.fields:
        taskfield = tasktaskfield.taskfield
        if taskfield.override_completion:
            override_completion.append(taskfield.fieldname)

    for field in override_completion:
        if not match(REGEX_ISODATE, formdata[field]):
            results.append({'name': field, 'status': 'please specify date in yyyy-mm-dd format'})
        elif formdata[field] > date.today().isoformat():
            results.append({'name':field, 'status': 'cannot specify date later than today'})

    if not match(REGEX_ISODATE, formdata['lastcompleted']):
        results.append({'name':'lastcompleted', 'status': 'please specify date in yyyy-mm-dd format'})

    elif formdata['lastcompleted'] > date.today().isoformat():
        results.append({'name':'lastcompleted', 'status': 'cannot specify date later than today'})

    return results

taskdetails_filters = filtercontainerdiv()
with taskdetails_filters:
    filterdiv('members-external-filter-members', 'Member')
    filterdiv('members-external-filter-positions-by-member', 'Members in Positions')
    filterdiv('members-external-filter-taskgroups-by-member', 'Members in Task Groups')
    filterdiv('members-external-filter-tasks', 'Task')
    filterdiv('members-external-filter-taskgroups-by-task', 'Tasks in Task Groups')
    filterdiv('members-external-filter-statuses', 'Status')
    filterdiv('members-external-filter-completed', 'Last Completed')
    filterdiv('members-external-filter-expires', 'Expiration Date')
    datefilter = filterdiv('positiondate-external-filter-startdate', 'In Position On')
    with datefilter:
        input(type='text', id='effective-date', name='effective-date', _class='like-select2-sizing')
        button('Today', id='todays-date-button')

taskdetails_yadcf_options = [
    yadcfoption('member:name', 'members-external-filter-members', 'multi_select', placeholder='Select members', width='200px'),
    yadcfoption('task:name', 'members-external-filter-tasks', 'multi_select', placeholder='Select tasks', width='200px'),
    yadcfoption('task_taskgroups.taskgroup:name', 'members-external-filter-taskgroups-by-task', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('member_positions.position:name', 'members-external-filter-positions-by-member', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('member_taskgroups.taskgroup:name', 'members-external-filter-taskgroups-by-member', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('status:name', 'members-external-filter-statuses', 'multi_select', placeholder='Select statuses', width='200px'),
    yadcfoption('lastcompleted:name', 'members-external-filter-completed', 'range_date'),
    yadcfoption('expires:name', 'members-external-filter-expires', 'range_date'),
]

taskdetails_view = TaskDetails(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Task,
                    template = 'datatables.jinja2',
                    templateargs = {
                        'tablefiles': lambda: fieldupload.list(),
                        'adminguide': adminguide,
                    },
                    pretablehtml = taskdetails_filters.render(),
                    yadcfoptions = taskdetails_yadcf_options,
                    pagename = 'Task Details',
                    endpoint = 'admin.taskdetails',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskdetails',
                    dbmapping = taskdetails_dbmapping,
                    formmapping = taskdetails_formmapping,
                    checkrequired = True,
                    validate = taskdetails_validate,
                    clientcolumns = [
                        {'data': 'member', 'name': 'member', 'label': 'Member',
                         'type': 'readonly',
                         },
                        {'data': 'order', 'name': 'order', 'label': 'Display Order',
                         'type': 'hidden',
                         'className': 'Hidden',
                         },
                        {'data': 'status', 'name': 'status', 'label': 'Status',
                         'type': 'readonly',
                         'className': 'status-field',
                         },
                        {'data': 'task', 'name': 'task', 'label': 'Task',
                         'type': 'readonly',
                         },
                        {'data': 'lastcompleted', 'name': 'lastcompleted', 'label': 'Last Completed',
                         'type': 'datetime',
                         # 'ed': {'opts':{'maxDate':date.today().isoformat()}}
                         },
                        {'data': 'expires', 'name': 'expires', 'label': 'Expiration Date',
                         'type': 'readonly',
                         'className': 'status-field',
                         },
                        {'data': 'member_positions', 'name': 'member_positions', 'label': 'Member Positions',
                         # 'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                    fieldmodel = Position, labelfield = 'position',
                                    formfield = 'member_positions',
                                    dbfield = 'member_positions', uselist = True,
                                    queryparams = localinterest_query_params,
                                 )
                             }}
                         },
                        {'data': 'member_taskgroups', 'name': 'member_taskgroups', 'label': 'Member Task Groups',
                         # 'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                    fieldmodel = TaskGroup, labelfield = 'taskgroup',
                                    formfield = 'member_taskgroups',
                                    dbfield = 'member_taskgroups', uselist = True,
                                    queryparams = localinterest_query_params,
                                 )
                             }}
                         },
                        {'data': 'task_taskgroups', 'name': 'task_taskgroups', 'label': 'Task Task Groups',
                         'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                        fieldmodel = TaskGroup, labelfield = 'taskgroup', formfield = 'task_taskgroups',
                                        dbfield = 'task_taskgroups', uselist = True,
                                        queryparams = localinterest_query_params,
                                 )

                            }}
                         },
                        {'data': 'fields', 'name': 'fields', 'label': 'Add\'l Fields',
                         'type': 'readonly',
                         'dtonly': True,
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = [
                        {
                            'extend':'editRefresh',
                            'text':'View',
                            'editor': {'eval':'editor'},
                            'formButtons': [
                                {'text': 'Update', 'action': {'eval': 'submit_button'}},
                                {'text': 'Dismiss', 'action': {'eval':'dismiss_button'}}
                            ]
                        },
                        'csv'
                    ],
                    dtoptions = {
                        'scrollCollapse': True,
                        'scrollX': True,
                        'scrollXInner': "100%",
                        'scrollY': True,
                        'rowCallback': {'eval': 'set_cell_status_class'},
                        # note id is column 0 to datatables, col 2 (display order) hidden
                        'order': [['member:name', 'asc'], ['order:name', 'asc'], ['expires:name', 'asc']],
                    },
                    edoptions={
                        'i18n':
                            # "edit" window shows "Task" in title
                            {'edit':
                                {
                                    'title': 'Task',
                                }
                            }
                    },
                )
taskdetails_view.register()

##########################################################################################
# membersummary endpoint
###########################################################################################

status_slugs = [slugify(s) for s in STATUS_DISPLAYORDER]
slug2status = dict(zip(status_slugs, STATUS_DISPLAYORDER))
status2slug = dict(zip(STATUS_DISPLAYORDER, status_slugs))
membersummary_dbattrs = 'id,interest_id,member,member_positions,member_taskgroups'.split(',') + status_slugs
membersummary_formfields = 'rowid,interest_id,member,member_positions,member_taskgroups'.split(',') + status_slugs
membersummary_dbmapping = dict(zip(membersummary_dbattrs, membersummary_formfields))
membersummary_formmapping = dict(zip(membersummary_formfields, membersummary_dbattrs))

class MemberMember():
    '''
    allows creation of "membermember" object to simulate database behavior
    '''
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

class MemberSummary(DbCrudApiInterestsRolePermissions):
    def open(self):
        # create another instance of TaskDetails
        taskdetails = TaskDetails(
            app=bp,  # use blueprint instead of app
            db=db,
            model=Task,
            local_interest_model=LocalInterest,
            dbmapping=taskdetails_dbmapping,
            formmapping=taskdetails_formmapping,
            rule='unused',
            clientcolumns=[
                {'data': 'member', 'name': 'member', 'label': 'Member',
                 'type': 'readonly',
                 },
                {'data': 'status', 'name': 'status', 'label': 'Status',
                 'type': 'readonly',
                 'className': 'status-field',
                 },
            ],
        )

        members = {}
        taskdetails.open()
        linterest = localinterest()
        for row in taskdetails.rows:
            thistask = taskdetails.dte.get_response_data(row)
            # add user record
            localuserid, taskid = taskdetails.getids(row.id)
            thistask['User'] = localuser2user(localuserid)
            name = thistask['User'].name

            # add member name to members if not already there
            if name not in members:
                # note taskgroups should be the same for all task records, so ok to set with first for this member
                members[name] = MemberMember(
                    id = localuserid,
                    member = name,
                    member_positions = thistask['member_positions'],
                    member_taskgroups = thistask['member_taskgroups'],
                    interest_id = linterest.id,
                )
                for slug in status_slugs:
                    setattr(members[name], slug, 0)

            # update status for this record
            thisslug = status2slug[thistask['status']]
            count = getattr(members[name], thisslug)
            setattr(members[name], thisslug, count+1)

        # set rows for response
        therows = []
        for name in members:
            for slug in status_slugs:
                if (getattr(members[name],slug) == 0):
                    setattr(members[name],slug,None)
            therows.append(members[name])
        self.rows = iter(therows)

membersummary_filters = filtercontainerdiv()
membersummary_filters += filterdiv('members-external-filter-members', 'Member')
membersummary_filters += filterdiv('members-external-filter-positions-by-member', 'Members in Positions')
membersummary_filters += filterdiv('members-external-filter-taskgroups-by-member', 'Members in Task Groups')

membersummary_yadcf_options = [
    yadcfoption('member:name', 'members-external-filter-members', 'multi_select', placeholder='Select members', width='200px'),
    yadcfoption('member_positions.position:name', 'members-external-filter-positions-by-member', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('member_taskgroups.taskgroup:name', 'members-external-filter-taskgroups-by-member', 'multi_select', placeholder='Select task groups', width='200px'),
]

membersummary = MemberSummary(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = LocalUser,
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
                    pretablehtml = membersummary_filters.render(),
                    yadcfoptions = membersummary_yadcf_options,
                    pagename = 'Member Summary',
                    endpoint = 'admin.membersummary',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/membersummary',
                    dbmapping = membersummary_dbmapping,
                    formmapping = membersummary_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'member', 'name': 'member', 'label': 'Member',
                         'type':'readonly',
                         },
                    ] + [
                        {'data':slug, 'name':slug,
                         'type':'readonly',
                         'class': 'TextCenter',
                         'label':slug2status[slug]
                         } for slug in status_slugs
                    ] + [
                        {'data': 'member_positions', 'name': 'member_positions', 'label': 'Member Positions',
                         'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                    fieldmodel = Position, labelfield = 'position',
                                    formfield = 'member_positions',
                                    dbfield = 'member_positions', uselist = True,
                                    queryparams = localinterest_query_params,
                                 )
                             }}
                         },
                        {'data': 'member_taskgroups', 'name': 'member_taskgroups', 'label': 'Member Task Groups',
                         'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                    fieldmodel = TaskGroup, labelfield = 'taskgroup',
                                    formfield = 'member_taskgroups',
                                    dbfield = 'member_taskgroups', uselist = True,
                                    queryparams = localinterest_query_params,
                                 )
                             }}
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons=[
                        {
                            'extend': 'edit',
                            'text': 'View Member',
                            'action': {'eval': 'member_details'}
                        },
                        'csv'
                    ],

                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
membersummary.register()

##########################################################################################
# history endpoint
###########################################################################################

def history_addlfields(tc, task):
    return get_taskfields(tc, task)

history_dbattrs = 'id,interest_id,member,position,task,completion,update_time,updated_by'.split(',')
history_formfields = 'rowid,interest_id,member,position,task,completion,update_time,updated_by'.split(',')
history_dbmapping = dict(zip(history_dbattrs, history_formfields))
history_formmapping = dict(zip(history_formfields, history_dbattrs))

history_formmapping['member'] = lambda tc: localuser2user(tc.user_id).name
history_formmapping['position'] = lambda tc: tc.position.position if tc.position else ""
history_formmapping['task'] = lambda tc: tc.task.task
history_formmapping['completion'] = lambda tc: dtrender.dt2asc(tc.completion)
history_formmapping['update_time'] = lambda tc: dttimerender.dt2asc(tc.update_time)
history_formmapping['updated_by'] = lambda tc: localuser2user(tc.updated_by).name
history_formmapping['addlfields'] = lambda tc: history_addlfields(tc, tc.task)

history_filters = filtercontainerdiv()
history_filters += filterdiv('members-external-filter-update-time', 'Update Time')
history_filters += filterdiv('members-external-filter-updated-by', 'Updated By')
history_filters += filterdiv('members-external-filter-members', 'Member')
history_filters += filterdiv('members-external-filter-tasks', 'Task')
history_filters += filterdiv('members-external-filter-completed', 'Completed')

history_yadcf_options = [
    yadcfoption('update_time:name', 'members-external-filter-update-time', 'range_date'),
    yadcfoption('updated_by:name', 'members-external-filter-updated-by', 'multi_select', placeholder='Select who updated', width='200px'),
    yadcfoption('member:name', 'members-external-filter-members', 'multi_select', placeholder='Select members', width='200px'),
    yadcfoption('task:name', 'members-external-filter-tasks', 'multi_select', placeholder='Select tasks', width='200px'),
    yadcfoption('completion:name', 'members-external-filter-completed', 'range_date'),
]

history = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = TaskCompletion,
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
                    pretablehtml = history_filters.render(),
                    yadcfoptions=history_yadcf_options,
                    pagename = 'History',
                    endpoint = 'admin.history',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/history',
                    dbmapping = history_dbmapping, 
                    formmapping = history_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'update_time', 'name': 'update_time', 'label': 'Update Time',
                         'type': 'readonly',
                         },
                        {'data': 'updated_by', 'name': 'updated_by', 'label': 'Updated By',
                         'type': 'readonly',
                         },
                        {'data': 'member', 'name': 'member', 'label': 'Member',
                         'type': 'readonly',
                         },
                        {'data': 'position', 'name': 'position', 'label': 'Position',
                         'type': 'readonly',
                         },
                        {'data': 'task', 'name': 'task', 'label': 'Task',
                         'type': 'readonly',
                         },
                        {'data': 'completion', 'name': 'completion', 'label': 'Date Completed',
                         'type': 'readonly',
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = [
                        {
                            'extend':'editRefresh',
                            'text':'View',
                            'editor': {'eval':'editor'},
                            'formButtons': [
                                {'text': 'Dismiss', 'action': {'eval':'dismiss_button'}}
                            ]
                        },
                        'csv'
                    ],
                    dtoptions = {
                        'scrollCollapse': True,
                        'scrollX': True,
                        'scrollXInner': "100%",
                        'scrollY': True,
                        'order': [['update_time:name', 'desc']],
                    },
                    edoptions={
                        'i18n':
                            # "edit" window shows "Task" in title
                            {'edit':
                                {
                                    'title': 'Task Completion',
                                }
                            }
                    },
                    )
history.register()


