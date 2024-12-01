"""
task_cli - background tasks needed for task management
"""

# standard
from datetime import date

# pypi
from flask import g, url_for, current_app
from jinja2 import Template
from flask.cli import with_appcontext
from click import argument, group, option

# homegrown
from scripts import catch_errors
from members.model import db, Task
from members.views.admin.viewhelpers import localinterest, get_taskgroup_taskgroups
# this is a little trick as the emails have the same information as the Task Details view
from members.views.admin.leadership_tasks_admin import TaskDetails, taskdetails_dbmapping
from members.views.admin import bp
from members.model import db, LocalUser, LocalInterest, Task, EmailTemplate, Position
from members.views.admin.viewhelpers import localuser2user, localinterest, get_taskgroup_tasks
from members.views.admin.viewhelpers import get_position_taskgroups, get_taskgroup_taskgroups
from members.views.admin.viewhelpers import STATUS_EXPIRES_SOON, STATUS_OVERDUE
from members.helpers import positions_active, members_active
from loutilities.flask_helpers.mailer import sendmail

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

taskdetails = TaskDetails(
    app=bp,  # use blueprint instead of app
    db=db,
    model=Task,
    local_interest_model=LocalInterest,
    dbmapping=taskdetails_dbmapping,
    # formmapping=taskdetails_formmapping,
    rule='unused',
    clientcolumns=[
        {'data': 'member', 'name': 'member', 'label': 'Member',
         'type': 'readonly',
         },
        {'data': 'status', 'name': 'status', 'label': 'Status',
         'type': 'readonly',
         'className': 'status-field',
         },
        {'data': 'task', 'name': 'task', 'label': 'Task',
         'type': 'readonly',
         },
        {'data': 'lastcompleted', 'name': 'lastcompleted', 'label': 'Last Completed',
         'type': 'datetime',
         # 'ed': {'opts':{'maxDate':date.today().isoformat()}}
         },
        {'data': 'expires', 'name': 'expires', 'label': 'Expires',
         'type': 'readonly',
         'className': 'status-field',
         },
    ],
)

@task.command()
@argument('interest')
@option('--nomembers', default=False, is_flag=True, help='Use this to disable members processing')
@option('--nomanagers', default=False, is_flag=True, help='Use this to disable managers processing')
@with_appcontext
@catch_errors
def sendreminders(interest, nomembers, nomanagers):
    with current_app.test_request_context():
        # g has to be set within app context
        g.interest = interest

        membertasks = []
        taskdetails.open()
        for row in taskdetails.rows:
            membertask = taskdetails.dte.get_response_data(row)

            # add user record
            localuserid, taskid = taskdetails.getids(row.id)
            membertask['User'] = localuser2user(localuserid)
            membertask['Task'] = Task.query.filter_by(id=taskid).one()
            membertasks.append(membertask)

        # create member based data structure
        mem2tasks = {}
        for membertask in membertasks:
            mem2tasks.setdefault(membertask['User'].email, {'tasks':[]})
            mem2tasks[membertask['User'].email]['tasks'].append(membertask)

        for member in mem2tasks:
            mem2tasks[member]['tasks'].sort(key=lambda t: t['order'])

        # default is from interest, may be overridden below, based on emailtemplate configuration
        fromlist = localinterest().from_email

        # allows for debugging of each section separately
        if not nomembers:
            emailtemplate = EmailTemplate.query.filter_by(templatename='member-email', interest=localinterest()).one()
            template = Template(emailtemplate.template)
            subject = emailtemplate.subject
            if emailtemplate.from_email:
                fromlist = emailtemplate.from_email
            refurl = url_for('admin.taskchecklist', interest=g.interest, _external=True)

            for emailaddr in mem2tasks:
                # only send email if there are tasks overdue or upcoming
                sendforstatus = [STATUS_EXPIRES_SOON, STATUS_OVERDUE]
                if len([t for t in mem2tasks[emailaddr]['tasks'] if t['status'] in sendforstatus]) > 0:
                    html = template.render(**mem2tasks[emailaddr], statuses=sendforstatus, refurl=refurl)
                    tolist = emailaddr
                    cclist = None
                    sendmail(subject, fromlist, tolist, html, ccaddr=cclist)

        # allows for debugging of each section separately
        if not nomanagers:
            # what groups are each member a part of?
            member2groups = {}
            for memberlocal in LocalUser.query.filter_by(active=True, interest=localinterest()).all():
                memberglobal = localuser2user(memberlocal)
                member2groups[memberglobal.email] = {'worker': memberlocal, 'taskgroups': set()}
                # drill down to get all taskgroups the member is responsible for
                for position in positions_active(memberlocal, date.today()):
                    get_position_taskgroups(position, member2groups[memberglobal.email]['taskgroups'])
                for taskgroup in memberlocal.taskgroups:
                    get_taskgroup_taskgroups(taskgroup, member2groups[memberglobal.email]['taskgroups'])

            # get list of responsible managers
            responsibility = {}
            positions = Position.query.filter_by(interest=localinterest()).all()
            for position in positions:
                positiontasks = set()
                positionworkers = set()
                theseemailgroups = set(position.emailgroups)
                for workeremail in member2groups:
                    # add worker if the worker's taskgroups intersect with these email groups
                    if theseemailgroups & member2groups[workeremail]['taskgroups']:
                        positionworkers |= {member2groups[workeremail]['worker']}
                for emailgroup in position.emailgroups:
                    get_taskgroup_tasks(emailgroup, positiontasks)
                # only set responsibility if this position has management for some groups
                if position.emailgroups:
                    for manager in members_active(position, date.today()):
                        manageruser = localuser2user(manager)
                        responsibility.setdefault(manageruser.email, {'tasks':set(), 'workers':set()})
                        responsibility[manageruser.email]['tasks'] |= positiontasks
                        responsibility[manageruser.email]['workers'] |= positionworkers

            # set up template engine
            emailtemplate = EmailTemplate.query.filter_by(templatename='leader-email', interest=localinterest()).one()
            template = Template(emailtemplate.template)
            subject = emailtemplate.subject
            if emailtemplate.from_email:
                fromlist = emailtemplate.from_email
            refurl = url_for('admin.taskdetails', interest=g.interest, _external=True)

            # loop through responsible managers, setting up their email
            for manager in responsibility:
                manager2members = {'members':[]}
                # need to convert to ids which are given by taskdetails
                for positionworker in responsibility[manager]['workers']:
                    resptasks = [taskdetails.setid(positionworker.id, t.id) for t in responsibility[manager]['tasks']]
                    positionuser = localuser2user(positionworker)
                    thesetasks = []
                    if positionuser.email in mem2tasks:
                        thesetasks = [t for t in mem2tasks[positionuser.email]['tasks']
                                    if t['rowid'] in resptasks and t['status'] in [STATUS_OVERDUE]]
                    if thesetasks:
                        manager2members['members'].append({'name':positionuser.name,
                                                            'tasks':thesetasks})

                # only send if something to send
                if manager2members['members']:
                    html = template.render(**manager2members, refurl=refurl)
                    tolist = manager
                    cclist = None

                    sendmail(subject, fromlist, tolist, html, ccaddr=cclist)
