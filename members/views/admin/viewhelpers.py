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

# homegrown
from ...model import TaskCompletion, LocalUser, LocalInterest
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
PERIOD_WINDOW_DISPLAY = 7 # number of days, i.e., on view 2 would be stored as 2*PERIOD_WINDOW_DISPLAY days

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

        if self.active != None:
            localusers = [lu for lu in localusers if lu.active == self.active]

        options = [{'label': lu.name, 'value': lu.id} for lu in localusers]
        return options


def get_task_completion(task, user):
    start = time()
    # if completion is by position and this user is in the task's position, return the latest task completion for this position
    localuser = user2localuser(user)
    if task.isbyposition:
        taskcompletion = TaskCompletion.query.filter_by(task=task, position=task.position).order_by(TaskCompletion.update_time.desc()).first()
    # if by member, return the latest task completion for the indicated user
    else:
        taskcompletion = TaskCompletion.query.filter_by(task=task, user=localuser).order_by(TaskCompletion.update_time.desc()).first()
    if timingdebug: current_app.logger.debug(f',get_task_completion() execution time,,,{time()-start:0.3f}')
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
    if timingdebug: current_app.logger.debug(f',lastcompleted() execution time,,{time()-start:0.3f}')
    return completed

# TODO: move these next two functions to User definition
def has_oneof_roles(user, roles):
    allowed = False
    for role in roles:
        if user.has_role(role):
            allowed = True
            break
    return allowed

def has_all_roles(user, roles):
    allowed = True
    for role in roles:
        if not user.has_role(role):
            allowed = False
            break
    return allowed

class PositionTaskgroupCacheMixin():
    # @profile
    def init_position_taskgroup_cache(self, localusers, ondate):
        """initialize cache of positions and taskgroups

        Args:
            localusers (list): list of LocalUser records
            ondate (str or datetime): date for which we're interested
        """
        self.activepositions = {}
        self.position2taskgroups = {}
        self.localuser2taskgroups = {}
        self.taskgroup2tasks = {}
        localusertask2positions = {}
        localusers_cache = {}
        self.localusertask2earliest = {}
        for localuser in localusers:
            localusers_cache[localuser.id] = localuser
            self.activepositions[localuser.id] = positions_active(localuser, ondate)
            self.localuser2taskgroups[localuser.id] = set(localuser.taskgroups)
            for position in self.activepositions[localuser.id]:
                if position.id not in self.position2taskgroups:
                    self.position2taskgroups[position.id] = set()
                    get_position_taskgroups(position, self.position2taskgroups[position.id])
                for taskgroup in self.position2taskgroups[position.id]:
                    if taskgroup.id not in self.taskgroup2tasks:
                        self.taskgroup2tasks[taskgroup.id] = set()
                        get_taskgroup_tasks(taskgroup, self.taskgroup2tasks[taskgroup.id])
                    # this is used to calculate earliest start date for tasks for this user in these positions
                    for task in self.taskgroup2tasks[taskgroup.id]:
                        localusertask2positions.setdefault((localuser.id, task.id), []).append(position)
            
        # find earliest start date for any positions held by each user for given task
        for localuser_id, task_id in localusertask2positions:
            earliest = dtrender.asc2dt('2999-12-31').date()
            for position in localusertask2positions[localuser_id, task_id]:
                localuser = localusers_cache[localuser_id]
                # member_positions returns list sorted by startdate
                thisstart = member_positions(localuser, position)[0].startdate
                if thisstart < earliest:
                    earliest = thisstart
            self.localusertask2earliest[localuser_id, task_id] = earliest        
            
    def get_activepositions(self, localuser):
        """return list of active positions for a user
    
        Args:
            localuser (LocalUser): LocalUser instance

        Returns:
            list: [position, position, ...]
        """
        activepositions = self.activepositions[localuser.id]
        return activepositions
    
    def get_position_taskgroups(self, position):
        """return set of taskgroups for a position

        Args:
            position (Position): position for which taskgroups are to be returned

        Returns:
            set: {taskgroup, taskgroup, ...}
        """
        return self.position2taskgroups[position.id]
    
    def get_localuser_taskgroups(self, localuser):
        """return set of taskgroups for a position

        Args:
            localuser (LocalUser): localuser for which taskgroups are to be returned

        Returns:
            set: {taskgroup, taskgroup, ...}
        """
        return self.localuser2taskgroups[localuser.id]
    
    def get_taskgroup_tasks(self, taskgroup):
        """return set of tasks for taskgroup

        Args:
            taskgroup (TaskGroup): TaskGroup instance

        Returns:
            set: {task, task, ...}
        """
        return self.taskgroup2tasks[taskgroup.id]

    def get_earliestposition(self, localuser, task):
        """return earliest start date that user would have had to do this task

        Args:
            localuser (LocalUser): LocalUser instance
            task (Task): Task instance

        Returns:
            date: earliest start time for any position user held for which they would have had to do this task
        """
        return self.localusertask2earliest[localuser.id, task.id]

# @profile
def _get_expiration(view, localuser, task, taskcompletion):
    '''
    task expiration depends on configuration type
        if configured with a period
            initially task expires based on configured value
            after completion task expires at completion date + period
        if configured with a date of year
            task expires at the configured date of year
            if task was completed between date of year + expiry starts
    :param task: task to check
    :param taskcompletion: last task completion, or None
    :param localuser: LocalUser for whom task completion should be
    :return: date
    '''
    start = time()
    timingdebug = False
    
    # task is optional
    if task.isoptional:
        expires = None

    # task expires yearly on a specific date
    elif task.dateofyear:
        month, day = [int(md) for md in task.dateofyear.split('-')]
        expirystarts = relativedelta(**{task.expirystarts_units:task.expirystarts})
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

            if debug: current_app.logger.debug('not completed: today {} doy {} windowstarts {} windowends {}'.format(todaymmdd, task.dateofyear,
                                                                         windowstarts.isoformat(),
                                                                         windowends.isoformat()))

            # we want the dateofyear / year to fall within the window
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

            if debug: current_app.logger.debug('completed: today {} doy {} compl {} windowstarts {} windowends {}'.format(todaymmdd, task.dateofyear,
                                                                         completiondate.isoformat(),
                                                                         windowstarts.isoformat(),
                                                                         windowends.isoformat()))

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
            expires = dtrender.dt2asc(taskcompletion.completion + relativedelta(**{task.period_units: task.period}))

        # task not completed, return default
        else:
            if debug: current_app.logger.debug(f'{localuser2user(localuser).name}: task {task.task} not completed')

            earliest = view.get_earliestposition(localuser, task)
            if earliest:
                # return earliest start date for this user in any position which requires this task
                expires = dtrender.dt2asc(earliest)
            
            # seems like this shouldn't be reachable
            else:
                li = localinterest()
                if li.initial_expiration:
                    expires = dtrender.dt2asc(li.initial_expiration)
                else:
                    expires = None
    
    if timingdebug: current_app.logger.debug(f',_get_expiration() execution time,,,,{time()-start:0.3f}')
    return expires

# @profile
def _get_status(view, localuser, task, taskcompletion):
    # task is optional
    if task.isoptional:
        if not taskcompletion:
            thisstatus = STATUS_OPTIONAL
        else:
            thisstatus = STATUS_DONE
        thisexpires = STATUS_NO_EXPIRATION

    # task is managed periodically
    elif task.period:
        if not task.period and taskcompletion:
            thisstatus = STATUS_DONE
            thisexpires = STATUS_NO_EXPIRATION
        elif not taskcompletion or taskcompletion.completion + relativedelta(**{task.period_units: task.period}) < datetime.today():
            thisstatus = STATUS_OVERDUE
            thisexpires = _get_expiration(view, localuser, task, taskcompletion)
        elif taskcompletion.completion + (relativedelta(**{task.period_units: task.period}) - relativedelta(**{task.expirysoon_units: task.expirysoon})) < datetime.today():
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
        if today >= expiresdate-expiressoon and today < expiresdate:
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

    return {'status': thisstatus, 'order': STATUS_DISPLAYORDER.index(thisstatus), 'expires': thisexpires}

def get_status(view, user, task):
    start = time()
    taskcompletion = get_task_completion(task, user)
    status = _get_status(view, user2localuser(user), task, taskcompletion)['status']
    if timingdebug: current_app.logger.debug(f',get_status() execution time,,{time()-start:0.3f}')
    return status

def get_order(view, user, task):
    start = time()
    taskcompletion = get_task_completion(task, user)
    order = _get_status(view, user2localuser(user), task, taskcompletion)['order']
    if timingdebug: current_app.logger.debug(f',get_order() execution time,,{time()-start:0.3f}')
    return order

def get_expires(view, user, task):
    start = time()
    taskcompletion = get_task_completion(task, user)
    expires = _get_status(view, user2localuser(user), task, taskcompletion)['expires']
    if timingdebug: current_app.logger.debug(f',get_expires() execution time,,{time()-start:0.3f}')
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

    # normal case is task is completed for the individual, so record the individual's completion
    taskcompletion.user = localuser
    
    # if it's by position, record the position's completion
    # if user doesn't have this position, then skip recording the position as this is for the individual
    #  >> this is an odd case, not sure if it's needed, actually, but may be some reason for this case
    # if task.isbyposition and task.position in localuser.positions:
    if task.isbyposition:
        taskcompletion.position = task.position
    
    db.session.add(taskcompletion)
    db.session.flush()

    # save the additional fields
    for ttf in task.fields:
        f = ttf.taskfield
        # it's possible the field isn't there but the value
        # set by the user earlier would be there (fieldname + '-val')
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
    else:
        return dbrow.fieldoptions.split(SEPARATOR)

TASKFIELD_KEYS = 'taskfield,fieldname,displayvalue,displaylabel,inputtype,fieldinfo,priority,uploadurl'
def get_taskfields(tc, task):
    '''
    returns the taskfields for a task completion
    :param tc: TaskCompletion instance
    :param task: Task instance
    :return: taskfields (list)
    '''
    taskfields = []
    
    # check for task as this might be null https://github.com/louking/members/issues/590
    if task:
        for ttf in task.fields:
            f = ttf.taskfield
            thistaskfield = {}
            for key in TASKFIELD_KEYS.split(','):
                thistaskfield[key] = getattr(f, key)
                # displayvalue gets markdown translation
                if key == 'displayvalue' and getattr(f, key):
                    thistaskfield[key] = markdown(getattr(f, key), extensions=['md_in_html', 'attr_list'])
            thistaskfield['fieldoptions'] = get_fieldoptions(f)
            if tc:
                # field may exist now but maybe didn't before
                field = InputFieldData.query.filter_by(field=f, taskcompletion=tc).one_or_none()

                # field was found
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
                        thistaskfield['fileid'] = value

                # field wasn't found
                else:
                    thistaskfield['value'] = None
            else:
                thistaskfield['value'] = None
            taskfields.append(thistaskfield)

    return taskfields

def get_member_tasks(member, ondate):
    '''
    get all tasks for a member

    :param member: LocalUser record for member
    :param ondate: date for which positions are effective for this member
    :return: set of tasks
    '''
    tasks = set()

    # collect all the tasks which are referenced by positions and taskgroups for this member
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
    for taskgroup in taskgroup.taskgroups:
        get_taskgroup_tasks(taskgroup, tasks)

def get_taskgroup_taskgroups(taskgroup, taskgroups):
    '''
    get members recursively for this task group
    :param taskgroup: TaskGroup instance
    :param taskgroups: input and output set of tasks
    :return: None
    '''
    taskgroups |= {taskgroup} | set(taskgroup.taskgroups)
    # for tg in taskgroup.taskgroups:
    #     taskgroups |= {tg}
    if taskgroupsdebug: current_app.logger.debug(f'get_taskgroup_taskgroups(): taskgroups before recursion {taskgroups}')
    ## the recursion isn't needed apparently
    # for tg in taskgroup.taskgroups:
    #     get_taskgroup_taskgroups(tg, taskgroups)
    # if taskgroupsdebug: current_app.logger.debug(f'get_taskgroup_taskgroups(): taskgroups after recursion {taskgroups}')

def get_position_taskgroups(position, taskgroups):
    '''
    get task groups for this position
    :param position: Position instance
    :param taskgroups: input and output set of task groups
    :return: None
    '''
    if taskgroupsdebug: current_app.logger.debug(f'get_position_taskgroups() position.taskgroups: {position.taskgroups}')
    for taskgroup in position.taskgroups:
        if taskgroupsdebug: current_app.logger.debug('get_position_taskgroups() calling get_taskgroup_taskgroups()')
        get_taskgroup_taskgroups(taskgroup, taskgroups)
        if taskgroupsdebug: current_app.logger.debug('get_position_taskgroups() return from get_taskgroup_taskgroups()')

def get_tags_users(tags, users, ondate):
    '''
    get users which have specified tags (following position)

    :param tags: list of tags to search for
    :param users: input and output set of localusers
    :param ondate: date for which positions are effective for this member
    :return: None
    '''

    # collect all the users which have the indicated tags
    for tag in tags:
        for position in tag.positions:
            for member in members_active(position, ondate):
                users.add(member)
        for user in tag.users:
            users.add(user)

def get_tags_positions(tags):
    '''
    get positions which have specified tags

    :param tags: list of tags to search for
    :return: set(position, ...)
    '''
    # collect all the positions which have the indicated tags
    positions = set()
    for tag in tags:
        positions |= set(tag.positions)
    return positions