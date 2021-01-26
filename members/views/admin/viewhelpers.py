'''
viewhelpers - helpers for admin views
'''

# standard
from datetime import datetime, date

# pypi
from flask import g, current_app, url_for
from dateutil.relativedelta import relativedelta
from markdown import markdown
from dominate.tags import a

# homegrown
from members.model import TaskCompletion, LocalUser, LocalInterest
from ...model import db, InputFieldData, Files, INPUT_TYPE_DATE, INPUT_TYPE_UPLOAD
from ...helpers import positions_active, members_active, localinterest
from loutilities.user.model import User, Interest
from loutilities.tables import SEPARATOR

from loutilities.timeu import asctime

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

def get_task_completion(task, user):
    localuser = user2localuser(user)
    return TaskCompletion.query.filter_by(task=task, user=localuser).order_by(TaskCompletion.update_time.desc()).first()

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
    taskcompletion = get_task_completion(task, user)
    return dtrender.dt2asc(taskcompletion.completion) if taskcompletion else None

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
            return dtrender.dt2asc(taskcompletion.completion + relativedelta(**{task.period_units: task.period}))

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
            thisexpires = _get_expiration(task, taskcompletion)
        elif taskcompletion.completion + (relativedelta(**{task.period_units: task.period}) - relativedelta(**{task.expirysoon_units: task.expirysoon})) < datetime.today():
            thisstatus = STATUS_EXPIRES_SOON
            thisexpires = _get_expiration(task, taskcompletion)
        else:
            thisstatus = STATUS_UP_TO_DATE
            thisexpires = _get_expiration(task, taskcompletion)

    # task expires yearly on a specific date
    elif task.dateofyear:
        thisexpires = _get_expiration(task, taskcompletion)
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
            thisexpires = _get_expiration(task, taskcompletion)

    return {'status': thisstatus, 'order': STATUS_DISPLAYORDER.index(thisstatus), 'expires': thisexpires}

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
    taskgroups |= {taskgroup}
    for tg in taskgroup.taskgroups:
        taskgroups |= {tg}
    for tg in taskgroup.taskgroups:
        get_taskgroup_taskgroups(tg, taskgroups)

def get_position_taskgroups(position, taskgroups):
    '''
    get task groups for this position
    :param position: Position instance
    :param taskgroups: input and output set of task groups
    :return: None
    '''
    for taskgroup in position.taskgroups:
        get_taskgroup_taskgroups(taskgroup, taskgroups)

def get_tags_users(tags, users, ondate):
    '''
    get users which have specified tag

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
