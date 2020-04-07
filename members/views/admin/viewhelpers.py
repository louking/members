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

from loutilities.timeu import asctime

dtrender = asctime('%Y-%m-%d')
EXPIRES_SOON = 14 #days

def _get_task_completion(task, user):
    localuser = user2localuser(user)
    return TaskCompletion.query.filter_by(task=task, user=localuser).order_by(TaskCompletion.update_time.desc()).first()

def localuser2user(localuser):
    return User.query.filter_by(id=localuser.user_id, active=True).one()

def user2localuser(user):
    interest = Interest.query.filter_by(interest=g.interest).one()
    localinterest = LocalInterest.query.filter_by(interest_id=interest.id).one()
    return LocalUser.query.filter_by(user_id=user.id, active=True, interest=localinterest).one()

def localinterest():
    interest = Interest.query.filter_by(interest=g.interest).one()
    return LocalInterest.query.filter_by(interest_id=interest.id).one()

def lastcompleted(task, user):
    taskcompletion = _get_task_completion(task, user)
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
        thisstatus = 'optional'
        thisexpires = None
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
    taskcompletion = _get_task_completion(task, user)
    return _get_status(task, taskcompletion)['status']

def get_order(task, user):
    taskcompletion = _get_task_completion(task, user)
    return _get_status(task, taskcompletion)['order']

def get_expires(task, user):
    taskcompletion = _get_task_completion(task, user)
    return _get_status(task, taskcompletion)['expires']

