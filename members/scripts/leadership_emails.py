'''
leadership_emails - command line to send emails for leadership module
=========================================================================================
run from 3 levels up, like python -m members.scripts.leadership_emails
'''
# standard
from os.path import join, dirname
from argparse import ArgumentParser

#pypi
from flask import g, url_for
from jinja2 import Template

# homegrown
from members import create_app
from members.settings import Development
from members.applogging import setlogging
# this is a little trick as the emails have the same information as the Task Details view
from members.views.admin.leadership_tasks_admin import TaskDetails, taskdetails_dbmapping, taskdetails_formmapping
from members.views.admin import bp
from members.model import db, LocalUser, LocalInterest, Task, EmailTemplate, Position
from members.views.admin.viewhelpers import localuser2user, localinterest, get_taskgroup_tasks
from members.views.admin.viewhelpers import get_position_taskgroups, get_taskgroup_taskgroups
from members.views.admin.viewhelpers import STATUS_EXPIRES_SOON, STATUS_OVERDUE
from loutilities.flask_helpers.mailer import sendmail

class ParameterError(Exception): pass

taskdetails = TaskDetails(
    app=bp,  # use blueprint instead of app
    db=db,
    model=Task,
    local_interest_model=LocalInterest,
    dbmapping=taskdetails_dbmapping,
    formmapping=taskdetails_formmapping,
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

def main():
    parser = ArgumentParser()
    parser.add_argument('interest')
    parser.add_argument('--nomembers', default=False, action='store_const', const=True, help='use --nomembers to skip members')
    parser.add_argument('--nomanagers', default=False, action='store_const', const=True, help='use --nomanagers to skip managers')
    args = parser.parse_args()

    scriptdir = dirname(__file__)
    # two levels up
    scriptfolder = dirname(dirname(scriptdir))
    configdir = join(scriptfolder, 'config')
    memberconfigfile = "members.cfg"
    memberconfigpath = join(configdir, memberconfigfile)
    userconfigfile = "users.cfg"
    userconfigpath = join(configdir, userconfigfile)

    # create app and get configuration
    # use this order so members.cfg overrrides users.cfg
    configfiles = [userconfigpath, memberconfigpath]
    app = create_app(Development(configfiles), configfiles)

    # set up database
    db.init_app(app)

    # set up scoped session
    with app.app_context():
        # turn on logging
        setlogging()

        # g has to be set within app context
        g.interest = args.interest

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
        if not args.nomembers:
            emailtemplate = EmailTemplate.query.filter_by(templatename='member-email', interest=localinterest()).one()
            template = Template(emailtemplate.template)
            subject = emailtemplate.subject
            if emailtemplate.from_email:
                fromlist = emailtemplate.from_email
            refurl = url_for('admin.taskchecklist', interest=g.interest)

            for emailaddr in mem2tasks:
                # only send email if there are tasks overdue or upcoming
                sendforstatus = [STATUS_EXPIRES_SOON, STATUS_OVERDUE]
                if len([t for t in mem2tasks[emailaddr]['tasks'] if t['status'] in sendforstatus]) > 0:
                    html = template.render(**mem2tasks[emailaddr], statuses=sendforstatus, refurl=refurl)
                    tolist = emailaddr
                    cclist = None
                    sendmail(subject, fromlist, tolist, html, ccaddr=cclist)

        # allows for debugging of each section separately
        if not args.nomanagers:
            # what groups are each member a part of?
            member2groups = {}
            for memberlocal in LocalUser.query.filter_by(active=True, interest=localinterest()).all():
                memberglobal = localuser2user(memberlocal)
                member2groups[memberglobal.email] = {'worker': memberlocal, 'taskgroups': set()}
                # drill down to get all taskgroups the member is responsible for
                for position in memberlocal.positions:
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
                    for manager in position.users:
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
            refurl = url_for('admin.taskdetails', interest=g.interest)

            # loop through responsible managers, setting up their email
            for manager in responsibility:
                manager2members = {'members':[]}
                # need to convert to ids which are given by taskdetails
                for positionworker in responsibility[manager]['workers']:
                    resptasks = [taskdetails.setid(positionworker.id, t.id) for t in responsibility[manager]['tasks']]
                    positionuser = localuser2user(positionworker)
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


if __name__ == "__main__":
    main()