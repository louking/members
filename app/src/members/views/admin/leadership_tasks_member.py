'''
leadership_tasks_member - member task handling
===========================================
'''

# standard
from datetime import date
from time import time

# pypi
from flask import g, current_app, request, url_for
from flask_security import current_user
from markdown import markdown
from dominate.tags import a, div, input_, button
from loutilities.tables import SEPARATOR, get_request_data
from loutilities.filters import filtercontainerdiv, filterdiv
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.user.tablefiles import FieldUpload

# homegrown
from . import bp
from ...model import db, LocalInterest, LocalUser, Task, Files, InputFieldData, TaskCompletion
from ...model import FIELDNAME_ARG, NEED_ONE_OF, NEED_REQUIRED, INPUT_TYPE_UPLOAD, INPUT_TYPE_DISPLAY
from ...version import __docversion__
from .viewhelpers import lastcompleted, get_status, get_order, get_expires
from .viewhelpers import create_taskcompletion, get_task_completion, get_member_tasks
from .viewhelpers import PositionTaskgroupCacheMixin
from .viewhelpers import TASK_CHECKLIST_ROLES_ACCEPTED
from .viewhelpers import dtrender, _get_status

from ...helpers import positions_active

debug = False
timingdebug = False

adminguide = 'https://members.readthedocs.io/en/{docversion}/leadership-task-member-guide.html'.format(docversion=__docversion__)

# field upload endpoint
fieldupload = FieldUpload(
                app=bp,  # use blueprint instead of app
                db=db,
                local_interest_model=LocalInterest,
                roles_accepted=TASK_CHECKLIST_ROLES_ACCEPTED,
                uploadendpoint='admin.fieldupload',
                endpointvalues={'interest': '<interest>'},
                uploadrule='/<interest>/fieldupload',
                fieldname = lambda: request.args.get(FIELDNAME_ARG),
                filesdirectory=lambda: current_app.config['APP_FILE_FOLDER'],
                localinterestmodel=LocalInterest,
                filesmodel=Files
            )
fieldupload.register()

def mdrow(dbrow):
    start = time()
    if dbrow.description:
        description = markdown(dbrow.description, extensions=['md_in_html', 'attr_list'])
    else:
        description = ''
    if timingdebug: current_app.logger.debug(f',mdrow() execution time,,{time()-start:0.3f}')
    return description

def get_options(f):
    if not f.fieldoptions:
        return []
    else:
        return f.fieldoptions.split(SEPARATOR)

def addlfields(task):
    start = time()
    taskfields = []
    tc = get_task_completion(task, current_user)

    for ttf in task.fields:
        f = ttf.taskfield
        thistaskfield = {}
        for key in 'taskfield,fieldname,displaylabel,displayvalue,inputtype,fieldinfo,priority,uploadurl'.split(','):
            thistaskfield[key] = getattr(f, key)
            if key == 'displayvalue' and getattr(f, key):
                thistaskfield[key] = markdown(getattr(f, key), extensions=['md_in_html', 'attr_list'])
        thistaskfield['fieldoptions'] = get_options(f)

        if tc:
            field = InputFieldData.query.filter_by(field=f, taskcompletion=tc).one_or_none()
            if field:
                value = field.value
                if f.inputtype != INPUT_TYPE_UPLOAD:
                    thistaskfield['value'] = value
                else:
                    file = Files.query.filter_by(fileid=value).one()
                    thistaskfield['value'] = a(file.filename,
                                               href=url_for('admin.file',
                                                            interest=g.interest,
                                                            fileid=value),
                                               target='_blank').render()
            else:
                thistaskfield['value'] = None

        taskfields.append(thistaskfield)
    if timingdebug: current_app.logger.debug(f',addlfields() execution time,,{time()-start:0.3f}')
    return taskfields

def taskchecklist_pretablehtml():
    pretablehtml = div()
    with pretablehtml:
        with filtercontainerdiv(style='margin-bottom: 4px;'):
            datefilter = filterdiv('positiondate-external-filter-startdate', 'In Position On')
            with datefilter:
                input_(type='text', id='effective-date', name='effective-date' )
                button('Today', id='todays-date-button')
    return pretablehtml.render()

taskchecklist_dbattrs = 'id,task,description,priority,__readonly__,__readonly__,__readonly__,__readonly__,__readonly__'.split(',')
taskchecklist_formfields = 'rowid,task,description,priority,lastcompleted,addlfields,status,order,expires'.split(',')
taskchecklist_dbmapping = dict(zip(taskchecklist_dbattrs, taskchecklist_formfields))
taskchecklist_formmapping = dict(zip(taskchecklist_formfields, taskchecklist_dbattrs))
# see TaskChecklist.__init__ for updates to formmapping

class TaskChecklist(DbCrudApiInterestsRolePermissions, PositionTaskgroupCacheMixin):
    
    def __init__(self, formmapping=taskchecklist_formmapping, **kwargs):
        self.kwargs = kwargs
        args = dict(
            app=bp,
            db=db,
            model=Task,
            local_interest_model=LocalInterest,
            roles_accepted=TASK_CHECKLIST_ROLES_ACCEPTED,
            template='datatables.jinja2',
            templateargs={'adminguide': adminguide},
            pagename='Task Checklist',
            endpoint='admin.taskchecklist',
            endpointvalues={'interest': '<interest>'},
            rule='/<interest>/taskchecklist',
            dbmapping=taskchecklist_dbmapping,
            pretablehtml=taskchecklist_pretablehtml,
            validate = self._validate,
            clientcolumns=[
                {'data': '',
                 'name': 'view-task',
                 'className': 'view-task shrink-to-fit',
                 'orderable': False,
                 'defaultContent': '',
                 'label': '',
                 'type': 'hidden',
                 'title': 'View',
                 'render': {'eval': 'render_icon("fas fa-eye")'},
                 },
                {'data': 'order', 'name': 'order', 'label': 'Display Order',
                 'type':'hidden',
                 'className': 'Hidden',
                 },
                {'data': 'priority', 'name': 'priority', 'label': 'Priority',
                 'type':'hidden',
                 'className': 'Hidden',
                 },
                {'data': 'task', 'name': 'task', 'label': 'Task',
                 'type': 'display',
                 'orderable': False,
                 'className': 'editorFullWidthField task_bold',
                 },
                {'data': 'description', 'name': 'description', 'label': '',
                 'type': 'display',
                 'className': 'editorFullWidthField',
                 'edonly': True,
                 },
                {'data': 'status', 'name': 'status', 'label': 'Status',
                 'orderable': False,
                 'type': 'readonly',
                 'className': 'status-field',
                 },
                {'data': 'lastcompleted', 'name': 'lastcompleted', 'label': 'Last Completed',
                 'orderable': False,
                 'type': 'readonly',
                 },
                {'data': 'expires', 'name': 'expires', 'label': 'Expiration Date',
                 'orderable': False,
                 'type': 'readonly',
                 'className': 'status-field',
                 },
            ],
            servercolumns=None,
            idSrc='rowid',
            buttons=[
                {
                    'extend':'edit',
                    'name': 'view-task',
                    'text':'View Task',
                    'editor': {'eval':'editor'},
                    'className': 'Hidden',
                },
                'csv'
            ],
            dtoptions={
                'scrollCollapse': True,
                'scrollX': True,
                'scrollXInner': "100%",
                'scrollY': True,
                'rowCallback': {'eval': 'set_cell_status_class'},
                'order': [['order:name', 'asc'], ['expires:name', 'asc'], ['priority:name', 'asc']],
                'lengthMenu': [10, 25, 50, 100],
                'pageLength': 25,
            },
            edoptions={
                'i18n': {
                    'edit' :
                         {
                             'title'  : 'Task',
                             'submit' : 'Mark Complete'
                         }
                },
                'formOptions': {
                    'main': {
                        'focus': None
                    }
                },
            }
        )
        args.update(kwargs)

        # ------------------------------------------------------------------
        # Cached formmapping lambdas
        #
        # For the single-user checklist view the cache covers one member, so
        # the two bulk queries become very fast.  The key gain is eliminating
        # the triple get_task_completion() call (one each for status / order /
        # expires) that previously fired on every row.
        #
        # _soe_cache is stored per task object (keyed by task.id) so that
        # the three lambda reads (status, order, expires) each trigger only
        # one _get_status() call.
        # ------------------------------------------------------------------
        formmapping['description'] = mdrow
        formmapping['addlfields']  = addlfields

        def _lastcompleted(task):
            tc = self._get_task_completion_for(task)
            return dtrender.dt2asc(tc.completion) if tc else None

        def _soe(task):
            if not hasattr(self, '_soe_task_cache'):
                self._soe_task_cache = {}
            if task.id not in self._soe_task_cache:
                localuser = self._get_localuser()
                tc = self._get_task_completion_for(task)
                self._soe_task_cache[task.id] = _get_status(self, localuser, task, tc)
            return self._soe_task_cache[task.id]

        formmapping['lastcompleted'] = _lastcompleted
        formmapping['status']  = lambda task: _soe(task)['status']
        formmapping['order']   = lambda task: _soe(task)['order']
        formmapping['expires'] = lambda task: _soe(task)['expires']

        super().__init__(formmapping=formmapping, **args)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_task_completion_for(self, task):
        """Return latest TaskCompletion from the in-memory cache for the
        current user and given task.  Falls back gracefully if the cache
        hasn't been built yet (e.g., called from _validate before open).
        """
        if hasattr(self, '_completions_by_user_task') or hasattr(self, '_completions_by_position_task'):
            localuser = self._get_localuser()
            return self.get_task_completion_cached(task, localuser)
        # fallback — should only happen outside of open() iteration
        return get_task_completion(task, current_user)

    def _get_localuser(self):
        # TODO: process request.args to see if different user is needed
        return LocalUser.query.filter_by(user_id=current_user.id, **self.queryparams).one()

    # ------------------------------------------------------------------
    # View lifecycle
    # ------------------------------------------------------------------

    def open(self):
        start = time()

        member = self._get_localuser()

        ondate = request.args.get('ondate', date.today())
        tasks = get_member_tasks(member, ondate)

        # init_position_taskgroup_cache now bulk-loads all TaskCompletions
        # for this member, so status/order/expires require zero DB queries
        # per row during iteration.
        self.init_position_taskgroup_cache([member], ondate)

        # Reset the per-open soe cache
        self._soe_task_cache = {}

        self.rows = iter(tasks)
        if timingdebug: current_app.logger.debug(f',open() execution time,{time()-start:0.3f}')
        
    def nexttablerow(self):
        start = time()
        row = super().nexttablerow()
        if timingdebug: current_app.logger.debug(f',nexttablerow() execution time,{time()-start:0.3f}')
        return row
    
    def close(self):
        return super().close()
    
    def updaterow(self, thisid, formdata):
        # find the task and local user
        thistask = Task.query.filter_by(id=thisid).one()
        localuser = self._get_localuser()

        create_taskcompletion(thistask, localuser, self.localinterest, formdata)

        # Invalidate the per-task soe cache for this task so the response
        # reflects the new completion rather than the pre-write cached value.
        if hasattr(self, '_soe_task_cache'):
            self._soe_task_cache.pop(thistask.id, None)

        # Also invalidate the completion cache entry so _get_task_completion_for
        # returns the new record.  Re-query and update in-place.
        if thistask.isbyposition and thistask.position_id:
            from ...model import TaskCompletion as TC
            tc_new = TC.query.filter_by(task=thistask, position=thistask.position).order_by(TC.update_time.desc()).first()
            if hasattr(self, '_completions_by_position_task'):
                self._completions_by_position_task[(thistask.position_id, thistask.id)] = tc_new
        else:
            from ...model import TaskCompletion as TC
            tc_new = TC.query.filter_by(task=thistask, user=localuser).order_by(TC.update_time.desc()).first()
            if hasattr(self, '_completions_by_user_task'):
                self._completions_by_user_task[(localuser.id, thistask.id)] = tc_new

        return self.dte.get_response_data(thistask)

    def _validate(self, action, formdata):
        results = []

        thisid = list(get_request_data(request.form).keys())[0]
        thistask = Task.query.filter_by(id=thisid).one()

        required = []
        one_of = []
        override_completion = []
        for tasktaskfield in thistask.fields:
            taskfield = tasktaskfield.taskfield
            if taskfield.inputtype == INPUT_TYPE_DISPLAY:
                continue
            if tasktaskfield.need == NEED_REQUIRED:
                required.append(taskfield.fieldname)
            elif tasktaskfield.need == NEED_ONE_OF:
                one_of.append(taskfield.fieldname)
            if taskfield.override_completion:
                override_completion.append(taskfield.fieldname)

        for field in required:
            if not formdata[field]:
                results.append({'name': field, 'status': 'please supply'})

        onefound = False
        for field in one_of:
            if formdata[field]:
                onefound = True
        if not onefound:
            for field in one_of:
                results.append({'name':field, 'status': 'one of these must be supplied'})

        for field in override_completion:
            if formdata[field] > date.today().isoformat():
                results.append({'name':field, 'status': 'cannot specify date later than today'})

        return results


taskchecklist_view = TaskChecklist()
taskchecklist_view.register()
