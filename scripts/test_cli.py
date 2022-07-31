"""
test_cli - test functions
"""

# standard
from re import T
from time import time
from datetime import datetime
from csv import DictWriter

# pypi
from flask import g
from flask.cli import with_appcontext
from click import argument, group
from sqlalchemy.orm import aliased
from sqlalchemy import and_, or_, func
from sqlparse import format as sqlformat
from tabulate import tabulate
from loutilities.timeu import asctime
from loutilities.csvwt import wlist

# homegrown
from scripts import catch_errors, ParameterError
from members.model import db, Task, TaskGroup, LocalUser, Position, TaskCompletion, UserPosition, taskgroup_taskgroup_table
from members.views.admin.viewhelpers import localinterest, get_taskgroup_taskgroups

# set up datatabase date formatter
dbdate = asctime('%Y-%m-%d')
isodate = asctime('%Y-%m-%d')

# debug
debug = False

# needs to be before any commands
@group()
def test():
    """Perform task module tasks"""
    pass


@test.command()
@argument('interest')
@with_appcontext
@catch_errors
def taskgroupdepth(interest):
    """determine max depth of taskgroup tree"""
    # set local interest to requested interest
    g.interest = interest
    linterest = localinterest()

    def countlevels(tg, count, path):
        maxcount = 0
        path.append(tg.taskgroup)
        if tg.taskgroups:
            for subtg in tg.taskgroups:
                thiscount = countlevels(subtg, count+1, path)
                if thiscount > maxcount:
                    maxcount = thiscount
            path.pop()
            return maxcount
        else:
            print(path)
            path.pop()
            return count
    
    starttime = time()
    maxcount = 0
    for tg in TaskGroup.query.filter_by(interest=linterest).all():
        path = []
        thiscount = countlevels(tg, 1, path)
        if thiscount > maxcount:
            maxcount = thiscount
    endtime = time()
    print(f'search duration {endtime - starttime}')
    
    print(f'max levels seen {maxcount}')

@test.command()
@argument('interest')
@with_appcontext
@catch_errors
def taskdetailsquery(interest):
    """test query used in task details view"""
    
    def countlevels(tg, count):
        """count the level depth for a TaskGroup instance

        Args:
            tg (TaskGroup): TaskGroup instance
            count (int): current depth

        Returns:
            int: depth of this instance
        """
        maxcount = 0
        if tg.taskgroups:
            for subtg in tg.taskgroups:
                thiscount = countlevels(subtg, count+1)
                if thiscount > maxcount:
                    maxcount = thiscount
            return maxcount
        else:
            return count

    # set up interest
    g.interest = interest

    # determine max depth of any taskgroups in this interest
    tgdepth = 0
    linterest = localinterest()
    for tg in TaskGroup.query.filter_by(interest=linterest).all():
        thiscount = countlevels(tg, 1)
        if thiscount > tgdepth:
            tgdepth = thiscount

    # set base query
    task = {}
    taskgroup = {}
    taskgroup_taskgroup = {}
    for i in range(tgdepth):
        task[i] = aliased(Task)
        taskgroup[i] = aliased(TaskGroup)
        taskgroup_taskgroup[i] = aliased(taskgroup_taskgroup_table)
    up_1 = aliased(UserPosition)
    
    # when position is active
    active_on = isodate.dt2asc(datetime.today())

    # maybe this can be copied
    
    # subquery to find max TaskCompletion.update_time. 
    # * https://stackoverflow.com/questions/9144677/left-join-on-max-value
    # * https://stackoverflow.com/questions/45775724/sqlalchemy-group-by-and-return-max-date
    def tcfilter(tbl):
        return or_(and_(tbl.position_id!=None, tbl.position_id==Position.id), tbl.user_id==LocalUser.id)
    tc2 = aliased(TaskCompletion)
    subquery = db.session.query(
        TaskCompletion.id, 
        TaskCompletion.user_id, 
        TaskCompletion.position_id, 
        TaskCompletion.task_id, 
        func.max(TaskCompletion.update_time).label('max_update_time'),
    ).group_by(
        TaskCompletion.user_id,
        TaskCompletion.position_id, 
        TaskCompletion.task_id, 
    ).subquery('latest_update')
    
    query = db.session.query().select_from(LocalUser)
    query = query.filter(LocalUser.interest==linterest)
    query = query.join(up_1, LocalUser.userpositions).filter(up_1.is_active_on(active_on))
    query = query.join(Position, Position.id==up_1.position_id)
    # filters required to avoid cartesian products in SELECT statement
    # see https://docs.sqlalchemy.org/en/14/changelog/migration_14.html#built-in-from-linting-will-warn-for-any-potential-cartesian-products-in-a-select-statement
    query = query.join(taskgroup[1], Position.taskgroups).filter(TaskGroup.id==taskgroup[1].id)
    query = query.join(task[1], taskgroup[1].tasks).filter(Task.id==task[1].id)

    # get latest taskcompletion
    # query = query.join(TaskCompletion).filter(tcfilter(TaskCompletion)).group_by(
    #     TaskCompletion.task_id,
    #     TaskCompletion.position_id,
    #     TaskCompletion.user_id,
    #     TaskCompletion.update_time,
    # )
    query = query.join(TaskCompletion).filter(tcfilter(TaskCompletion)).distinct()
    # query = query.outerjoin(subquery, TaskCompletion.id==subquery.c.id)
    # query = query.filter(
    #     TaskCompletion.user_id==subquery.c.user_id, 
    #     TaskCompletion.position_id==subquery.c.position_id, 
    #     TaskCompletion.task_id==subquery.c.task_id, 
    #     TaskCompletion.update_time==subquery.c.max_update_time, 
    # )
    
    # filter duplicates (see https://stackoverflow.com/questions/12188027/mysql-select-distinct-multiple-columns)
    # query = query.group_by(LocalUser.name, Task.task)
    # end copy
    
    # ColumnDT: add columns
    columns = [
        {'name': 'name',        'sqla_expr': LocalUser.name}, 
        {'name': 'task',        'sqla_expr': Task.task}, 
        {'name': 'tc_position', 'sqla_expr': TaskCompletion.position_id}, 
        {'name': 'completion',  'sqla_expr': func.date_format(TaskCompletion.completion, '%Y-%m-%d')}, 
        {'name': 'update_time', 'sqla_expr': TaskCompletion.update_time},
    ]
    query = query.add_columns(
        *[c['sqla_expr'] for c in columns]
    )
    
    print(sqlformat(str(query), reindent=True, keyword_case='upper'))
    
    column_names = [c['name'] for c in columns]
    rows = query.all()
    results = [{k: v
                for k, v in zip(column_names, row)}
                for row in rows]
    
    print(tabulate(results, headers='keys', tablefmt='psql'))
    print(f'{len(rows)} rows')
    
@test.command()
@argument('interest')
@with_appcontext
@catch_errors
def taskcompletionquery(interest):
    """test subquery for taskcompletions used in task details view"""

    # set up interest
    g.interest = interest
    
    subquery = db.session.query(
        TaskCompletion.id, 
        TaskCompletion.user_id, 
        TaskCompletion.position_id, 
        TaskCompletion.task_id, 
        func.max(TaskCompletion.update_time).label('max_update_time'),
    ).group_by(
        TaskCompletion.user_id,
        TaskCompletion.position_id, 
        TaskCompletion.task_id, 
    ).subquery('latest_update')
    
    query = db.session.query().select_from(TaskCompletion)
    query = query.join(subquery, TaskCompletion.id==subquery.c.id)
    # .filter(
        # TaskCompletion.user_id==subquery.c.user_id, 
        # TaskCompletion.position_id==subquery.c.position_id, 
        # TaskCompletion.task_id==subquery.c.task_id, 
    #     TaskCompletion.update_time==subquery.c.max_update_time
    # )
    query = query.outerjoin(Task, Task.id==TaskCompletion.task_id)
    query = query.outerjoin(LocalUser, LocalUser.id==TaskCompletion.user_id)
    query = query.outerjoin(Position, Position.id==TaskCompletion.position_id)
    
    # ColumnDT: add columns
    columns = [
        {'name': 'update_time', 'sqla_expr': subquery.c.max_update_time},
        {'name': 'task', 'sqla_expr': Task.task},
        {'name': 'user', 'sqla_expr': LocalUser.name},
        {'name': 'position', 'sqla_expr': Position.position},
        # {'name': 'completion',  'sqla_expr': func.date_format(subquery.c.completion, '%Y-%m-%d')}, 
        {'name': 'id',  'sqla_expr': subquery.c.id}, 
    ]
    query = query.add_columns(
        *[c['sqla_expr'] for c in columns]
    )
    # query = query.group_by(TaskCompletion.position_id, TaskCompletion.user_id, TaskCompletion.task_id)
    # query = query.order_by(TaskCompletion.update_time.desc())

    print(sqlformat(str(query), reindent=True, keyword_case='upper'))
    
    column_names = [c['name'] for c in columns]
    rows = query.all()
    results = [{k: v
                for k, v in zip(column_names, row)}
                for row in rows]
    
    print(tabulate(results, headers='keys', tablefmt='psql'))
    print(f'{len(rows)} rows')

    