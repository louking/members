"""
task_cli - background tasks needed for task management
"""

# standard

# pypi
from flask import g
from flask.cli import with_appcontext
from click import argument, group

# homegrown
from scripts import catch_errors, ParameterError
from members.model import db, Task
from members.views.admin.viewhelpers import localinterest, get_taskgroup_taskgroups
from loutilities.timeu import asctime

# set up datatabase date formatter
dbdate = asctime('%Y-%m-%d')

# debug
debug = False

# needs to be before any commands
@group()
def task():
    """Perform task module tasks"""
    pass

@task.command()
@argument('interest')
@with_appcontext
@catch_errors
def checkpositionconfig(interest):
    """verify configuration for position based tasks"""
    # set local interest to requested interest
    g.interest = interest
    linterest = localinterest()
    
    # check each task
    for task in Task.query.filter_by(interest=linterest).all():
        # we only care about position based tasks
        if not task.isbyposition:
            continue
        
        # there should be exactly one taskgroup
        if len(task.taskgroups) != 1:
            print(f'task "{task.task}", interest "{interest}", is by position and is configured with multiple task groups {[t.taskgroup for t in task.taskgroups]}')
            continue
        
        # taskgroup should not reference other taskgroups
        taskgroups = set()
        get_taskgroup_taskgroups(task.taskgroups[0], taskgroups)
        if len(taskgroups) != 1:
            print(f'task "{task.task}", interest "{interest}", is by position and references multiple task groups {[t.taskgroup for t in taskgroups]}')
            continue
        
        # the taskgroup referenced by this task should be used only by the position referenced in this task
        taskgroup = task.taskgroups[0]
        if len(taskgroup.positions) != 1 or taskgroup.positions[0] != task.position:
            positions = [p.position for p in taskgroup.positions]
            print(f'task "{task.task}", interest "{interest}", is by position "{task.position.position}" but taskgroup "{taskgroup.taskgroup}" is referenced by {positions}')
            continue
        