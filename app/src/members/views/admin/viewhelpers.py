'''
viewhelpers - helpers for admin views
'''

# standard
from datetime import datetime, date
from time import time

# pypi
from loutilities.user.model import User, Interest, Role
from loutilities.tables import DteDbRelationship, SEPARATOR
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER
from flask import g, current_app, url_for
from dateutil.relativedelta import relativedelta
from markdown import markdown
from dominate.tags import a
from sqlalchemy.orm import joinedload

# homegrown
from ...model import TaskCompletion, LocalUser, LocalInterest, Task, UserPosition
from ...model import db, InputFieldData, Files, INPUT_TYPE_DATE, INPUT_TYPE_UPLOAD, localinterest_query_params
from ...helpers import positions_active, members_active, member_positions, localinterest

from loutilities.timeu import asctime

# profile slow code
from line_profiler import LineProfiler

profiler = LineProfiler()

def profile(func):
    def inner(*args, **kwargs):
        profiler.add_function(func)
        profiler.enable_by_count()
        return func(*args, **kwargs)
    return inner
# end profile

dtrender = asctime('%Y-%m-%d')
dttimerender = asctime('%Y-%m-%d %H:%M:%S')
EXPIRES_SOON = 14 #days
PERIOD_WINDOW_DISPLAY = 7

STATUS_EXPIRES_SOON = 'expires soon'
STATUS_OVERDUE = 'overdue'
STATUS_DONE = 'done'
STATUS_NO_EXPIRATION = 'no expiration'
STATUS_OPTIONAL = 'optional'
STATUS_UP_TO_DATE = 'up to date'

# STATUS_DISPLAYORDER needs to match values in beforedatatables.js fn set_cell_status_class.classes
STATUS_DISPLAYORDER = [STATUS_OVERDUE, STATUS_EXPIRES_SOON, STATUS_OPTIONAL, STATUS_UP_TO_DATE, STATUS_DONE]

debug = False
timingdebug = False
taskgroupsdebug = False

class ParameterError(Exception): pass

TASK_CHECKLIST_ROLES_ACCEPTED = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER]

class LocalUserPicker(DteDbRelationship):
    '''
    define user picker for users who have specific roles
    
    :param rolenames: set or list of role names. users who have any of these roles are included
    :param active: (optional) if only active (or inactive) users should be included, set this to True (or False)
    :param **kwargs: DteDbRelationship arguments
    '''
    def __init__(self, rolenames=set(), active=None, **kwargs):
        super().__init__(**kwargs)
        
        self.active = active
        self.rolenames = rolenames

        if not rolenames:
            raise ParameterError('LocalUserPicker rolenames parameter needs to be set')

    def options(self):
        roles = set()
        for rolename in self.rolenames:
            role = Role.query.filter_by(name=rolename).one()
            roles.add(role)

        interest = Interest.query.filter_by(interest=g.interest).one()
        users = [u for u in User.query.all() if interest in u.interests]
        users.sort(key=lambda l: l.name.lower())
        # only offer localuser as option if user has at least one of the requested roles
        localusers = [LocalUser.query.filter_by(user_id=user.id, **localinterest_query_params()).one() for user in users if roles & set(user.roles)]

        if self.active is not None:
            localusers = [lu for lu in localusers if lu.active == self.active]

        return [{'label': lu.name, 'value': lu.id} for lu in localusers]


def get_task_completion(task, user):
    '''
    Uncached DB lookup — use only in updaterow/refreshrows paths.
    During open() iteration use get_task_completion_cached() instead.
    '''
    start = time()
    localuser = user2localuser(user)
    if task.isbyposition:
        taskcompletion = (TaskCompletion.query
                          .filter_by(task=task, position=task.position)
                          .order_by(TaskCompletion.update_time.desc())
                          .first())
    else:
        taskcompletion = (TaskCompletion.query
                          .filter_by(task=task, user=localuser)
                          .order_by(TaskCompletion.update_time.desc())
                          .first())
    if timingdebug:
        current_app.logger.debug(f',get_task_completion() execution time,,,{time()-start:0.3f}')
    return taskcompletion


def localuser2user(localuser):
    if type(localuser) == int:
        localuser = LocalUser.query.filter_by(id=localuser).one()
    return User.query.filter_by(id=localuser.user_id).one()


def user2localuser(user):
    interest = Interest.query.filter_by(interest=g.interest).one()
    localinterest = LocalInterest.query.filter_by(interest_id=interest.id).one()
    if type(user) == int:
        user = User.query.filter_by(id=user).one()
    return LocalUser.query.filter_by(user_id=user.id, interest=localinterest).one()


def lastcompleted(task, user):
    start = time()
    taskcompletion = get_task_completion(task, user)
    completed = dtrender.dt2asc(taskcompletion.completion) if taskcompletion else None
    if timingdebug:
        current_app.logger.debug(f',lastcompleted() execution time,,{time()-start:0.3f}')
    return completed

# TODO: move these next two functions to User definition
def has_oneof_roles(user, roles):
    for role in roles:
        if user.has_role(role):
            return True
    return False


def has_all_roles(user, roles):
    for role in roles:
        if not user.has_role(role):
            return False
    return True


def _positions_active_from_preloaded(localuser, ondate, up_by_user):
    """
    Return active positions for localuser on ondate, using the pre-built
    UserPosition dict instead of querying the DB.

    Args:
        localuser (LocalUser): the user
        ondate (date|str): effective date
        up_by_user (dict): {localuser_id: [UserPosition, ...]} pre-loaded

    Returns:
        list[Position]
    """
    if isinstance(ondate, str):
        ondate = dtrender.asc2dt(ondate).date()

    positions = []
    for up in up_by_user.get(localuser.id, []):
        start = up.startdate
        finish = up.finishdate
        if start is None:
            continue
        if start <= ondate and (finish is None or finish >= ondate):
            positions.append(up.position)
    return positions


class PositionTaskgroupCacheMixin():

    def init_position_taskgroup_cache(self, localusers, ondate):
        """
        Initialise all caches needed for open() iteration.

        Query inventory (regardless of number of users/tasks):
          1. UserPosition bulk load (all active positions for all users)
          2. LocalUser.taskgroups eager load
          3. Position.taskgroups eager load  (only positions actually used)
          4. Task eager load with taskgroups + fields  (only tasks actually used)
          5. TaskCompletion bulk load — user-based
          6. TaskCompletion bulk load — position-based
          7. member_positions() calls for earliest-start calculation
             (one per unique (localuser, position) pair — unavoidable without
              deeper refactoring of helpers.positions_active / member_positions)
        """
        localuser_ids = [lu.id for lu in localusers]
        locinterest = localinterest()

        # ------------------------------------------------------------------ #
        # 1. Bulk-load UserPosition for every user                           #
        # ------------------------------------------------------------------ #
        all_up = (
            UserPosition.query
            .filter(UserPosition.user_id.in_(localuser_ids))
            .filter_by(interest=locinterest)
            .options(joinedload(UserPosition.position))  # ← pre-load Position
            .all()
        )       
        up_by_user = {}
        for up in all_up:
            up_by_user.setdefault(up.user_id, []).append(up)

        # ------------------------------------------------------------------ #
        # 2. Eager-load LocalUser.taskgroups for all users in one query      #
        # ------------------------------------------------------------------ #
        localusers_with_tg = (
            LocalUser.query
            .filter(LocalUser.id.in_(localuser_ids))
            .options(joinedload(LocalUser.taskgroups))
            .all()
        )
        localuser_tg_map = {lu.id: lu.taskgroups for lu in localusers_with_tg}

        # ------------------------------------------------------------------ #
        # Build active-positions and position-set for all users              #
        # ------------------------------------------------------------------ #
        self.activepositions = {}
        all_position_ids = set()
        for lu in localusers:
            # WAS: active = positions_active(lu, ondate)   ← per-user DB query
            active = _positions_active_from_preloaded(lu, ondate, up_by_user)  # ← uses bulk dict
            self.activepositions[lu.id] = active
            for pos in active:
                all_position_ids.add(pos.id)
                
        # ------------------------------------------------------------------ #
        # 3. Eager-load Position.taskgroups for all active positions         #
        # ------------------------------------------------------------------ #
        from ...model import Position
        if all_position_ids:
            positions_with_tg = (
                Position.query
                .filter(Position.id.in_(list(all_position_ids)))
                .options(joinedload(Position.taskgroups))
                .all()
            )
            position_tg_map = {p.id: p.taskgroups for p in positions_with_tg}
        else:
            position_tg_map = {}

        # ------------------------------------------------------------------ #
        # Build position2taskgroups and taskgroup2tasks caches               #
        # ------------------------------------------------------------------ #
        self.position2taskgroups = {}
        self.localuser2taskgroups = {}
        self.taskgroup2tasks = {}
        localusertask2positions = {}
        localusers_by_id = {lu.id: lu for lu in localusers}

        for lu in localusers:
            self.localuser2taskgroups[lu.id] = set(localuser_tg_map.get(lu.id, []))
            for position in self.activepositions[lu.id]:
                if position.id not in self.position2taskgroups:
                    self.position2taskgroups[position.id] = set()
                    # use pre-loaded taskgroups — no lazy load
                    for tg in position_tg_map.get(position.id, []):
                        get_taskgroup_taskgroups(tg, self.position2taskgroups[position.id])
                for taskgroup in self.position2taskgroups[position.id]:
                    if taskgroup.id not in self.taskgroup2tasks:
                        self.taskgroup2tasks[taskgroup.id] = set()
                        get_taskgroup_tasks(taskgroup, self.taskgroup2tasks[taskgroup.id])
                    for task in self.taskgroup2tasks[taskgroup.id]:
                        localusertask2positions.setdefault(
                            (lu.id, task.id), []
                        ).append(position)

            # also gather tasks from direct user taskgroups
            for tg in self.localuser2taskgroups[lu.id]:
                if tg.id not in self.taskgroup2tasks:
                    self.taskgroup2tasks[tg.id] = set()
                    get_taskgroup_tasks(tg, self.taskgroup2tasks[tg.id])

        # ------------------------------------------------------------------ #
        # Earliest-start per (localuser, task)                               #
        # ------------------------------------------------------------------ #
        self.localusertask2earliest = {}
        for (localuser_id, task_id) in localusertask2positions:
            earliest = dtrender.asc2dt('2999-12-31').date()
            lu = localusers_by_id[localuser_id]
            for position in localusertask2positions[localuser_id, task_id]:
                thisstart = member_positions(lu, position)[0].startdate
                if thisstart < earliest:
                    earliest = thisstart
            self.localusertask2earliest[localuser_id, task_id] = earliest

        # ------------------------------------------------------------------ #
        # 4. Collect all task ids and eager-load Task.taskgroups + fields    #
        # ------------------------------------------------------------------ #
        all_task_ids = set()
        for tg_tasks in self.taskgroup2tasks.values():
            for t in tg_tasks:
                all_task_ids.add(t.id)

        if all_task_ids:
            tasks_eager = (
                Task.query
                .filter(Task.id.in_(list(all_task_ids)))
                .options(
                    joinedload(Task.taskgroups),
                    joinedload(Task.fields),     # avoids lazy load in taskdetails_addlfields
                )
                .all()
            )
            self._tasks_by_id = {t.id: t for t in tasks_eager}
        else:
            self._tasks_by_id = {}

        # Replace task references in taskgroup2tasks with the eager-loaded versions
        # so relationship access during row iteration is pre-populated.
        for tg_id in self.taskgroup2tasks:
            self.taskgroup2tasks[tg_id] = {
                self._tasks_by_id[t.id]
                for t in self.taskgroup2tasks[tg_id]
                if t.id in self._tasks_by_id
            }

        # ------------------------------------------------------------------ #
        # 5 + 6. Bulk-load TaskCompletions                                   #
        # ------------------------------------------------------------------ #
        self._completions_by_user_task = {}
        self._completions_by_position_task = {}

        if localuser_ids:
            user_completions = (
                TaskCompletion.query
                .filter(TaskCompletion.user_id.in_(localuser_ids))
                .order_by(
                    TaskCompletion.user_id,
                    TaskCompletion.task_id,
                    TaskCompletion.update_time.desc(),
                )
                .all()
            )
            for tc in user_completions:
                key = (tc.user_id, tc.task_id)
                if key not in self._completions_by_user_task:
                    self._completions_by_user_task[key] = tc

        if all_position_ids:
            position_completions = (
                TaskCompletion.query
                .filter(TaskCompletion.position_id.in_(list(all_position_ids)))
                .order_by(
                    TaskCompletion.position_id,
                    TaskCompletion.task_id,
                    TaskCompletion.update_time.desc(),
                )
                .all()
            )
            for tc in position_completions:
                key = (tc.position_id, tc.task_id)
                if key not in self._completions_by_position_task:
                    self._completions_by_position_task[key] = tc

    # ---------------------------------------------------------------------- #
    # Cache accessors                                                         #
    # ---------------------------------------------------------------------- #

    def get_task_completion_cached(self, task, localuser):
        """Zero-query completion lookup from bulk-loaded cache."""
        if task.isbyposition:
            if task.position_id is None:
                return None
            return self._completions_by_position_task.get((task.position_id, task.id))
        else:
            return self._completions_by_user_task.get((localuser.id, task.id))

    def get_status_order_expires(self, task, localuser):
        """Compute status/order/expires in one call using the cached completion."""
        tc = self.get_task_completion_cached(task, localuser)
        return _get_status(self, localuser, task, tc)

    def get_activepositions(self, localuser):
        return self.activepositions[localuser.id]

    def get_position_taskgroups(self, position):
        return self.position2taskgroups.get(position.id, set())

    def get_localuser_taskgroups(self, localuser):
        return self.localuser2taskgroups[localuser.id]

    def get_taskgroup_tasks(self, taskgroup):
        return self.taskgroup2tasks.get(taskgroup.id, set())

    def get_tasks_for_localuser(self, localuser):
        """
        Return the set of Task objects for a localuser using only the
        already-built cache — no DB calls, no repeated graph traversal.
        Replaces get_member_tasks() in the open() hot path.
        """
        tasks = set()
        for position in self.activepositions[localuser.id]:
            for tg in self.position2taskgroups.get(position.id, set()):
                tasks |= self.taskgroup2tasks.get(tg.id, set())
        for tg in self.localuser2taskgroups[localuser.id]:
            tasks |= self.taskgroup2tasks.get(tg.id, set())
        return tasks

    def get_earliestposition(self, localuser, task):
        return self.localusertask2earliest[localuser.id, task.id]


# -------------------------------------------------------------------------- #
# Core status/expiry logic — unchanged from original                         #
# -------------------------------------------------------------------------- #

def _get_expiration(view, localuser, task, taskcompletion):
    start = time()
    timingdebug = False

    # task is optional
    if task.isoptional:
        expires = None

    # task expires yearly on a specific date
    elif task.dateofyear:
        month, day = [int(md) for md in task.dateofyear.split('-')]
        expirystarts = relativedelta(**{task.expirystarts_units: task.expirystarts})
        today = date.today()
        todaymmdd = today.isoformat()[-5:]

        # if task has never been completed
        if not taskcompletion:
            # determine window based on today -- today must be within the window
            windowends = date(today.year - 2, month, day) + expirystarts
            while windowends <= today:
                windowends = date(windowends.year + 1, windowends.month, windowends.day)
            windowstarts = date(windowends.year - 1, windowends.month, windowends.day)
            windowendmmdd = windowends.isoformat()[-5:]

            if debug:
                current_app.logger.debug(
                    'not completed: today {} doy {} windowstarts {} windowends {}'.format(
                        todaymmdd, task.dateofyear, windowstarts.isoformat(), windowends.isoformat()))

            theyear = windowstarts.year
            expiry = date(theyear, month, day)
            while expiry < windowstarts:
                theyear += 1
                expiry = date(theyear, month, day)
            expires = expiry.isoformat()

        else:
            completion = taskcompletion.completion
            completiondate = date(completion.year, completion.month, completion.day)

            # determine window based on last completion -- last completion must be within the window
            windowends = date(completion.year - 2, month, day) + expirystarts
            while windowends <= completiondate:
                windowends = date(windowends.year + 1, windowends.month, windowends.day)
            windowstarts = date(windowends.year - 1, windowends.month, windowends.day)
            windowendmmdd = windowends.isoformat()[-5:]

            if debug:
                current_app.logger.debug(
                    'completed: today {} doy {} compl {} windowstarts {} windowends {}'.format(
                        todaymmdd, task.dateofyear, completiondate.isoformat(),
                        windowstarts.isoformat(), windowends.isoformat()))

            # if dayofyear and windowends in same year, expires the following year
            if task.dateofyear <= windowendmmdd:
                theyear = windowends.year + 1

            # if dayofyear and windowends in different year, expires the year window ends
            else:
                theyear = windowends.year

            # but if the completion was before the window started, need to back off a year
            # NOTE: completion not allowed after today's date, so must be in or before window
            if completiondate <= windowstarts:
                theyear -= 1

            expires = date(theyear, month, day).isoformat()

    # periodic or no period or date of year configured, but not optional
    else:
        # task completed, return expiration depending on task / completion date
        if taskcompletion:
            expires = dtrender.dt2asc(
                taskcompletion.completion + relativedelta(**{task.period_units: task.period}))
        # task not completed, return default
        else:
            if debug:
                current_app.logger.debug(
                    f'{localuser2user(localuser).name}: task {task.task} not completed')

            earliest = view.get_earliestposition(localuser, task)
            if earliest:
                expires = dtrender.dt2asc(earliest)
            
            # seems like this shouldn't be reachable
            else:
                li = localinterest()
                expires = dtrender.dt2asc(li.initial_expiration) if li.initial_expiration else None

    if timingdebug:
        current_app.logger.debug(f',_get_expiration() execution time,,,,{time()-start:0.3f}')
    return expires


def _get_status(view, localuser, task, taskcompletion):
    """
    Core status/order/expiry calculation.  No DB I/O.
    Returns dict with keys 'status', 'order', 'expires'.
    """
    if task.isoptional:
        thisstatus = STATUS_DONE if taskcompletion else STATUS_OPTIONAL
        thisexpires = STATUS_NO_EXPIRATION

    elif task.period:
        if not task.period and taskcompletion:
            thisstatus = STATUS_DONE
            thisexpires = STATUS_NO_EXPIRATION
        elif (not taskcompletion or
              taskcompletion.completion + relativedelta(**{task.period_units: task.period})
              < datetime.today()):
            thisstatus = STATUS_OVERDUE
            thisexpires = _get_expiration(view, localuser, task, taskcompletion)
        elif (taskcompletion.completion +
              (relativedelta(**{task.period_units: task.period}) -
               relativedelta(**{task.expirysoon_units: task.expirysoon}))
              < datetime.today()):
            thisstatus = STATUS_EXPIRES_SOON
            thisexpires = _get_expiration(view, localuser, task, taskcompletion)
        else:
            thisstatus = STATUS_UP_TO_DATE
            thisexpires = _get_expiration(view, localuser, task, taskcompletion)

    # task expires yearly on a specific date
    elif task.dateofyear:
        thisexpires = _get_expiration(view, localuser, task, taskcompletion)
        year, month, day = [int(ymd) for ymd in thisexpires.split('-')]
        today = date.today()
        expiressoon = relativedelta(**{task.expirysoon_units: task.expirysoon})
        expiresdate = date(year, month, day)
        if today >= expiresdate - expiressoon and today < expiresdate:
            thisstatus = STATUS_EXPIRES_SOON
        elif today > expiresdate:
            thisstatus = STATUS_OVERDUE
        else:
            thisstatus = STATUS_UP_TO_DATE

    # no period or date of year configured, but not optional
    else:
        if taskcompletion:
            thisstatus = STATUS_DONE
            thisexpires = STATUS_NO_EXPIRATION
        else:
            thisstatus = STATUS_OVERDUE
            thisexpires = _get_expiration(view, localuser, task, taskcompletion)

    return {
        'status': thisstatus,
        'order': STATUS_DISPLAYORDER.index(thisstatus),
        'expires': thisexpires,
    }


# Public helpers retained for call sites outside the hot path
def get_status(view, user, task):
    start = time()
    taskcompletion = get_task_completion(task, user)
    status = _get_status(view, user2localuser(user), task, taskcompletion)['status']
    if timingdebug:
        current_app.logger.debug(f',get_status() execution time,,{time()-start:0.3f}')
    return status

def get_order(view, user, task):
    start = time()
    taskcompletion = get_task_completion(task, user)
    order = _get_status(view, user2localuser(user), task, taskcompletion)['order']
    if timingdebug:
        current_app.logger.debug(f',get_order() execution time,,{time()-start:0.3f}')
    return order

def get_expires(view, user, task):
    start = time()
    taskcompletion = get_task_completion(task, user)
    expires = _get_status(view, user2localuser(user), task, taskcompletion)['expires']
    if timingdebug:
        current_app.logger.debug(f',get_expires() execution time,,{time()-start:0.3f}')
    return expires


def create_taskcompletion(task, localuser, localinterest, formdata):
    rightnow = datetime.now()
    taskcompletion = TaskCompletion(
        interest=localinterest,
        completion=rightnow,
        task=task,
        update_time=rightnow,
        updated_by=localuser.id,
    )
    taskcompletion.user = localuser
    if task.isbyposition:
        taskcompletion.position = task.position
    db.session.add(taskcompletion)
    db.session.flush()

    # save the additional fields
    for ttf in task.fields:
        f = ttf.taskfield
        if f.fieldname in formdata:
            value = formdata[f.fieldname]
        else:
            value = formdata[f.fieldname + '-val']
        inputfielddata = InputFieldData(
            field=f,
            taskcompletion=taskcompletion,
            value=value,
        )
        db.session.add(inputfielddata)
        db.session.flush()

        if f.inputtype == INPUT_TYPE_UPLOAD:
            file = Files.query.filter_by(fileid=formdata[f.fieldname]).one()
            file.taskcompletion = taskcompletion
        elif f.inputtype == INPUT_TYPE_DATE:
            if f.override_completion:
                taskcompletion.completion = dtrender.asc2dt(inputfielddata.value)

    return taskcompletion


def get_fieldoptions(dbrow):
    if not dbrow.fieldoptions:
        return []
    return dbrow.fieldoptions.split(SEPARATOR)


TASKFIELD_KEYS = 'taskfield,fieldname,displayvalue,displaylabel,inputtype,fieldinfo,priority,uploadurl'

def get_taskfields(tc, task):
    taskfields = []
    if task:
        for ttf in task.fields:
            f = ttf.taskfield
            thistaskfield = {}
            for key in TASKFIELD_KEYS.split(','):
                thistaskfield[key] = getattr(f, key)
                if key == 'displayvalue' and getattr(f, key):
                    thistaskfield[key] = markdown(getattr(f, key), extensions=['md_in_html', 'attr_list'])
            thistaskfield['fieldoptions'] = get_fieldoptions(f)
            if tc:
                field = InputFieldData.query.filter_by(field=f, taskcompletion=tc).one_or_none()
                if field:
                    value = field.value
                    if f.inputtype != INPUT_TYPE_UPLOAD:
                        thistaskfield['value'] = value
                    else:
                        file = Files.query.filter_by(fileid=value).one()
                        thistaskfield['value'] = a(
                            file.filename,
                            href=url_for('admin.file', interest=g.interest, fileid=value),
                            target='_blank',
                        ).render()
                        thistaskfield['fileid'] = value
                else:
                    thistaskfield['value'] = None
            else:
                thistaskfield['value'] = None
            taskfields.append(thistaskfield)
    return taskfields


def get_member_tasks(member, ondate):
    """
    Retained for use outside the cached open() path (e.g. taskchecklist).
    In TaskDetails.open() use view.get_tasks_for_localuser() instead.

    :param member: LocalUser record for member
    :param ondate: date for which positions are effective for this member
    :return: set of tasks
    """
    tasks = set()
    for position in positions_active(member, ondate):
        for taskgroup in position.taskgroups:
            get_taskgroup_tasks(taskgroup, tasks)
    for taskgroup in member.taskgroups:
        get_taskgroup_tasks(taskgroup, tasks)
    return tasks


def get_taskgroup_tasks(taskgroup, tasks):
    '''
    get tasks recursively for this task group
    :param taskgroup: TaskGroup instance
    :param tasks: input and output set of tasks
    :return: None
    '''
    for task in taskgroup.tasks:
        tasks |= {task}
    for tg in taskgroup.taskgroups:
        get_taskgroup_tasks(tg, tasks)


def get_taskgroup_taskgroups(taskgroup, taskgroups):
    '''
    get members recursively for this task group
    :param taskgroup: TaskGroup instance
    :param taskgroups: input and output set of tasks
    :return: None
    '''
    taskgroups |= {taskgroup} | set(taskgroup.taskgroups)
    if taskgroupsdebug:
        current_app.logger.debug(
            f'get_taskgroup_taskgroups(): taskgroups before recursion {taskgroups}')


def get_position_taskgroups(position, taskgroups):
    '''
    get task groups for this position
    :param position: Position instance
    :param taskgroups: input and output set of task groups
    :return: None
    '''
    if taskgroupsdebug: current_app.logger.debug(f'get_position_taskgroups() position.taskgroups: {position.taskgroups}')
    for taskgroup in position.taskgroups:
        if taskgroupsdebug:
            current_app.logger.debug('get_position_taskgroups() calling get_taskgroup_taskgroups()')
        get_taskgroup_taskgroups(taskgroup, taskgroups)
        if taskgroupsdebug:
            current_app.logger.debug(
                'get_position_taskgroups() return from get_taskgroup_taskgroups()')


def get_tags_positions(tags):
    '''
    get positions which have specified tags

    :param tags: list of tags to search for
    :return: set(position, ...)
    '''
    positions = set()
    for tag in tags:
        positions |= set(tag.positions)
    return positions
