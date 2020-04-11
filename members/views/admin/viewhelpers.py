'''
get_status - get_status helpers for admin views
'''

# standard
from datetime import datetime, timedelta

# pypi
from flask import g

# homegrown
from members.model import TaskCompletion, LocalUser, LocalInterest
from loutilities.user.model import User, Interest
from ...model import db, InputFieldData, Files, INPUT_TYPE_DATE, INPUT_TYPE_UPLOAD

from loutilities.timeu import asctime

dtrender = asctime('%Y-%m-%d')
dttimerender = asctime('%Y-%m-%d %H:%M:%S')
EXPIRES_SOON = 14 #days

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

def _get_expiration(task, taskcompletion):
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

def _get_status(task, taskcompletion):
    # displayorder needs to match values in beforedatatables.js fn set_cell_status_class.classes
    displayorder = ['overdue', 'expires soon', 'optional', 'up to date', 'done']
    if task.isoptional:
        if not taskcompletion:
            thisstatus = 'optional'
        else:
            thisstatus = 'done'
        thisexpires = 'no expiration'
    elif not task.period and taskcompletion:
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