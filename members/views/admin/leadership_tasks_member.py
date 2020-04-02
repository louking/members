'''
leadership_tasks_member - member task handling
===========================================
'''

# standard
from datetime import datetime

# pypi
from flask import request, current_app, request
from flask_security import current_user
from markdown import markdown

# homegrown
from . import bp
from ...model import db, LocalInterest, LocalUser, Task, TaskCompletion, InputFieldData, Files
from ...model import FIELDNAME_ARG, INPUT_TYPE_UPLOAD, NEED_ONE_OF, NEED_REQUIRED
from loutilities.tables import SEPARATOR, get_request_data
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.user.tablefiles import FieldUpload

debug = False

# field upload endpoint
fieldupload = FieldUpload(
                app=bp,  # use blueprint instead of app
                db=db,
                local_interest_model=LocalInterest,
                roles_accepted=[ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER],
                uploadendpoint='admin.fieldupload',
                endpointvalues={'interest': '<interest>'},
                uploadrule='/<interest>/fieldupload',
                fieldname = lambda: request.args.get(FIELDNAME_ARG),
                filesdirectory=lambda: current_app.config['APP_FILE_FOLDER'],
                localinterestmodel=LocalInterest,
                filesmodel=Files
            )
fieldupload.register()

# task checklist endpoint
def mdrow(dbrow):
    if dbrow.description:
        return markdown(dbrow.description, extensions=['md_in_html', 'attr_list'])
    else:
        return ''

def get_options(f):
    if not f.fieldoptions:
        return []
    else:
        return f.fieldoptions.split(SEPARATOR)

def addlfields(task):
    taskfields = []
    for ttf in task.fields:
        f = ttf.taskfield
        thistaskfield = {}
        for key in 'taskfield,fieldname,displaylabel,displayvalue,inputtype,fieldinfo,priority,uploadurl'.split(','):
            thistaskfield[key] = getattr(f, key)
        thistaskfield['fieldoptions'] = get_options(f)
        taskfields.append(thistaskfield)
    return taskfields

taskchecklist_dbattrs = 'id,task,description,priority,__readonly__'.split(',')
taskchecklist_formfields = 'rowid,task,description,priority,addlfields'.split(',')
taskchecklist_dbmapping = dict(zip(taskchecklist_dbattrs, taskchecklist_formfields))
taskchecklist_formmapping = dict(zip(taskchecklist_formfields, taskchecklist_dbattrs))

taskchecklist_formmapping['description'] = mdrow
taskchecklist_formmapping['addlfields'] = addlfields

class TaskChecklist(DbCrudApiInterestsRolePermissions):
    def __init__(self, **kwargs):
        
        self.kwargs = kwargs
        args = dict(
            app=bp,  # use blueprint instead of app
            db=db,
            model=Task,
            local_interest_model=LocalInterest,
            roles_accepted=[ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER],
            template='datatables.jinja2',
            pagename='Task Checklist',
            endpoint='admin.taskchecklist',
            endpointvalues={'interest': '<interest>'},
            rule='/<interest>/taskchecklist',
            dbmapping=taskchecklist_dbmapping,
            formmapping=taskchecklist_formmapping,
            validate = self._validate,
            clientcolumns=[
                {'data': 'priority', 'name': 'priority', 'label': 'Priority',
                 'type':'hidden',
                 'className': 'Hidden',
                 },
                {'data': 'task', 'name': 'task', 'label': 'Task',
                 'type': 'display',
                 'className': 'editorFullWidthField task_bold',
                 },
                {'data': 'description', 'name': 'description', 'label': '',
                 'type': 'display',
                 'className': 'editorFullWidthField',
                 'edonly': True,
                 },
            ],
            servercolumns=None,  # not server side
            idSrc='rowid',
            buttons=[
                {
                    'extend':'edit',
                    'text':'View Task',
                    'editor': {'eval':'editor'}
                }
            ],
            dtoptions={
                'scrollCollapse': True,
                'scrollX': True,
                'scrollXInner': "100%",
                'scrollY': True,
            },
            edoptions={
                'i18n':
                    {'edit' :
                         {
                             'title'  : 'Task',
                             'submit' : 'Mark Complete'
                         }
                    }
            }
        )
        args.update(kwargs)
        super().__init__(**args)

    def open(self):
        theserows = []

        # collect all the tasks to send to client
        tasks = set()
        theuser = self._get_localuser()

        # first collect all the tasks which apply to this user
        for taskgroup in theuser.taskgroups:
            for task in taskgroup.tasks:
                tasks |= set([task])

        # TODO: need to add completion date, or status, or display class to the tasks returned
        tasks = sorted(list(tasks), key=lambda t: t.priority)
        for task in iter(tasks):
            theserows.append(task)

        self.rows = iter(theserows)

    def updaterow(self, thisid, formdata):
        # find the task and local user
        thistask = Task.query.filter_by(id=thisid).one()
        localuser = self._get_localuser()

        # create the completion record
        taskcompletion = TaskCompletion(
            user = localuser, 
            interest = self.localinterest,
            completion = datetime.now(), 
            task = thistask,
        )
        db.session.add(taskcompletion)
        db.session.flush()

        # save the additional fields
        for ttf in thistask.fields:
            f = ttf.taskfield
            inputfielddata = InputFieldData(
                field = f,
                taskcompletion = taskcompletion,
                value = formdata[f.fieldname]
            )
            db.session.add(inputfielddata)

            if f.inputtype == INPUT_TYPE_UPLOAD:
                file = Files.query.filter_by(fileid=formdata[f.fieldname]).one()
                file.taskcompletion = taskcompletion

        # TODO: need to add completion date, or status, or display class to the tasks returned
        return self.dte.get_response_data(thistask)

    def _get_localuser(self):
        # TODO: process request.args to see if different user is needed
        return LocalUser.query.filter_by(user_id=current_user.id, **self.queryparams).one()

    def _validate(self, action, formdata):
        results = []

        # kludge to get task.id
        # NOTE: this is only called from 'edit' / put function, and there will be only one id
        thisid = list(get_request_data(request.form).keys())[0]
        thistask = Task.query.filter_by(id=thisid).one()

        # build lists of required and shared fields
        required = []
        one_of = []
        for tasktaskfield in thistask.fields:
            taskfield = tasktaskfield.taskfield
            if tasktaskfield.need == NEED_REQUIRED:
                required.append(taskfield.fieldname)
            elif tasktaskfield.need == NEED_ONE_OF:
                one_of.append(taskfield.fieldname)

        # verify required fields were supplied
        for field in required:
            if not formdata[field]:
                results.append({'name': field, 'status': 'please supply'})

        # verify one of the one_of fields was supplied
        onefound = False
        for field in one_of:
            if formdata[field]:
                onefound = True
        if not onefound:
            for field in one_of:
                results.append({'name':field, 'status': 'one of these must be supplied'})

        return results


taskchecklist = TaskChecklist()
taskchecklist.register()
