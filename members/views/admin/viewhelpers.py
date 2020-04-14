'''
get_status - get_status helpers for admin views
'''

# standard
from datetime import datetime, timedelta, date

# pypi
from flask import g, current_app

# homegrown
from members.model import TaskCompletion, LocalUser, LocalInterest
from loutilities.user.model import User, Interest
from ...model import db, InputFieldData, Files, INPUT_TYPE_DATE, INPUT_TYPE_UPLOAD

from loutilities.timeu import asctime

dtrender = asctime('%Y-%m-%d')
dttimerender = asctime('%Y-%m-%d %H:%M:%S')
EXPIRES_SOON = 14 #days
PERIOD_WINDOW_DISPLAY = 7 # number of days, i.e., on view 2 would be stored as 2*PERIOD_WINDOW_DISPLAY days

debug = True

def get_task_completion(task, user):
    localuser = user2localuser(user)
    return TaskCompletion.query.filter_by(task=task, user=localuser).order_by(TaskCompletion.update_time.desc()).first()

def localuser2user(localuser):
    if type(localuser) == int:
        localuser = LocalUser.query.filter_by(id=localuser, active=True).one()
    return User.query.filter_by(id=localuser.user_id, active=True).one()

def user2localuser(user):
    interest = Interest.query.filter_by(interest=g.interest).one()
    localinterest = LocalInterest.query.filter_by(interest_id=interest.id).one()
    if type(user) == int:
        user = User.query.filter_by(id=user, active=True).one()
    return LocalUser.query.filter_by(user_id=user.id, active=True, interest=localinterest).one()

def localinterest():
    interest = Interest.query.filter_by(interest=g.interest).one()
    return LocalInterest.query.filter_by(interest_id=interest.id).one()

def lastcompleted(task, user):
    taskcompletion = get_task_completion(task, user)
    return dtrender.dt2asc(taskcompletion.completion) if taskcompletion else None

def _get_year(thedate, month, day, expirystarts, completed):
    '''
    get the year for expiration

    :param thedate: completion date, or if not completed today's date
    :param month: task.dateofyear month
    :param day: task.dateofyear day
    :param expirystarts: timedelta window from month/year
    :param completed: True if the task completed
    :return: year
    '''
    if not completed:
        yearadjust = -1
    else:
        yearadjust = 0
    if (thedate > date(thedate.year - 1, month, day) + expirystarts
            and thedate <= date(thedate.year, month, day) + expirystarts):
        theyear = thedate.year + yearadjust
    else:
        theyear = thedate.year + 1 + yearadjust
    return theyear

def _get_expiration(task, taskcompletion):
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
    :return: date
    '''
    # task is optional
    if task.isoptional:
        return None

    # task is managed periodically
    elif task.period:
        # task completed, return expiration depending on task / completion date
        if taskcompletion:
            return dtrender.dt2asc(taskcompletion.completion + task.period)

        # task not completed, return default
        else:
            li = localinterest()
            if li.initial_expiration:
                return dtrender.dt2asc(li.initial_expiration)
            else:
                return None

    # task expires yearly on a specific date
    elif task.dateofyear:
        month, day = [int(md) for md in task.dateofyear.split('-')]
        expirystarts = task.expirystarts
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

            return expiry.isoformat()

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

            return date(theyear, month, day).isoformat()

    # no period or date of year configured, but not optional
    else:
        li = localinterest()
        if li.initial_expiration:
            return dtrender.dt2asc(li.initial_expiration)
        else:
            return None


def _get_status(task, taskcompletion):
    # displayorder needs to match values in beforedatatables.js fn set_cell_status_class.classes
    displayorder = ['overdue', 'expires soon', 'optional', 'up to date', 'done']

    # task is optional
    if task.isoptional:
        if not taskcompletion:
            thisstatus = 'optional'
        else:
            thisstatus = 'done'
        thisexpires = 'no expiration'


    # task is managed periodically
    elif task.period:
        if not task.period and taskcompletion:
            thisstatus = 'done'
            thisexpires = 'no expiration'
        elif not taskcompletion or taskcompletion.completion + task.period < datetime.today():
            thisstatus = 'overdue'
            thisexpires = _get_expiration(task, taskcompletion)
        elif taskcompletion.completion + (task.period - timedelta(EXPIRES_SOON)) < datetime.today():
            thisstatus = 'expires soon'
            thisexpires = _get_expiration(task, taskcompletion)
        else:
            thisstatus = 'up to date'
            thisexpires = _get_expiration(task, taskcompletion)

    # task expires yearly on a specific date
    elif task.dateofyear:
        thisexpires = _get_expiration(task, taskcompletion)
        year, month, day = [int(ymd) for ymd in thisexpires.split('-')]
        today = date.today()
        expiressoon = task.expirysoon
        expiresdate = date(year, month, day)
        if today >= expiresdate-expiressoon and today < expiresdate:
            thisstatus = 'expires soon'
        elif today > expiresdate:
            thisstatus = 'overdue'
        else:
            thisstatus = 'up to date'

    # no period or date of year configured, but not optional
    else:
        if taskcompletion:
            thisstatus = 'done'
            thisexpires = 'no expiration'
        else:
            thisstatus = 'overdue'
            thisexpires = _get_expiration(task, taskcompletion)

    return {'status': thisstatus, 'order': displayorder.index(thisstatus), 'expires': thisexpires}

def get_status(task, user):
    taskcompletion = get_task_completion(task, user)
    return _get_status(task, taskcompletion)['status']

def get_order(task, user):
    taskcompletion = get_task_completion(task, user)
    return _get_status(task, taskcompletion)['order']

def get_expires(task, user):
    taskcompletion = get_task_completion(task, user)
    return _get_status(task, taskcompletion)['expires']

def create_taskcompletion(task, localuser, localinterest, formdata):
    rightnow = datetime.now()
    taskcompletion = TaskCompletion(
        user=localuser,
        interest=localinterest,
        completion=rightnow,
        task=task,
        update_time=rightnow,
        updated_by=localuser.id,
    )
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

def get_member_tasks(member):
    '''
    get all tasks for a member
    :param member: LocalUser record for member
    :return: set of tasks
    '''
    tasks = set()

    # collect all the tasks which are referenced by positions and taskgroups for this member
    for position in member.positions:
        for taskgroup in position.taskgroups:
            get_tasks(taskgroup, tasks)
    for taskgroup in member.taskgroups:
        get_tasks(taskgroup, tasks)
    return tasks

def get_tasks(taskgroup, tasks):
    '''
    get tasks recursively for this task group
    :param taskgroup: TaskGroup instance
    :param tasks: input and output set of tasks
    :return: None
    '''
    for task in taskgroup.tasks:
        tasks |= {task}
    for taskgroup in taskgroup.taskgroups:
        get_tasks(taskgroup, tasks)