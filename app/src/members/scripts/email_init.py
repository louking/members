'''
email_init - command line database initialization - initialize emails
=========================================================================================
run from 3 levels up, like python -m members.scripts.email_init

'''
# standard
from os.path import join, dirname

# pypi
from flask import url_for

# homegrown
from loutilities.transform import Transform
from members import create_app
from members.settings import Development
from members.model import db
from members.applogging import setlogging
from members.model import LocalInterest, EmailTemplate, Base
from loutilities.user.model import Interest

class parameterError(Exception): pass

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

    fsrcinterest = Interest.query.filter_by(interest='fsrc').one()
    localfsrcinterest = LocalInterest.query.filter_by(interest_id=fsrcinterest.id).one()

    # drop and create EmailTemplate table
    binds = db.get_binds(app)
    thisbind = binds[EmailTemplate.__table__]
    Base.metadata.drop_all(bind=thisbind, tables=[EmailTemplate.__table__], checkfirst=True)
    Base.metadata.create_all(bind=thisbind, tables=[EmailTemplate.__table__])

    # configure emails for member and leader
    memberemail = EmailTemplate(
        templatename='member-email',
        subject='membertility: please review your upcoming and overdue tasks',
        interest=localfsrcinterest,
    )
    memberemail.template = '\n'.join([
        '<p>',
        'As a volunteer with the Frederick Steeplechasers Running Club, you are responsible for completing a set of',
        'tasks (some periodically) to ensure that you are as effective as possible in your assigned role.',
        'This email is a friendly reminder that you have one or more tasks that are either due soon or overdue.',
        'For more information on these tasks and to mark them as complete, visit',
        '{{ refurl }}.',
        '</p>',
        '<p>',
        'Thank you for your service to FSRC<br>',
        'Your FSRC Volunteer Management Team',
        '</p>',
        '<table>',
        '   <thead><tr><th>Task</th><th>Status</th><th>Expiration Date</th></tr></thead>',
        '   <tbody>',
        '   {# only sending this member\'s tasks to template #}',
        '   {% for task in tasks if task.status in statuses %}',
        '       <tr><td>{{ task.task }}</td><td>{{ task.status }}</td><td>{{ task.expires }}</td></tr>',
        '   {% endfor %}',
        '   </tbody>',
        '</table>',
    ])
    db.session.add(memberemail)

    leaderemail = EmailTemplate(
        templatename='leader-email',
        subject='membertility: overdue tasks for members reporting to you',
        interest=localfsrcinterest,
    )
    leaderemail.template = '\n'.join([
        '<p>',
        'In your role as a team lead for FSRC Volunteers, you are responsible for ensuring that the volunteers under',
        'your direction are completing the tasks required to carry out their role(s) effectively.',
        'The following tasks are overdue for the members that you are responsible for.',
        'Please follow up as needed. Note that each member has also received a reminder email listing their overdue ',
        'tasks. For more details please see {{ refurl }}.',
        '</p>',
        '<ul>',
        '   {% for member in members %}',
        '   <li><b>{{ member.name }}</b>',
        '       <table>',
        '          <thead><tr><th>Task</th><th>Expiration Date</th></tr></thead>',
        '          <tbody>',
        '          {% for task in member.tasks %}',
        '              <tr><td>{{ task.task }}</td><td>{{ task.expires }}</td></tr>',
        '          {% endfor %}',
        '          </tbody>',
        '       </table>',
        '   </li>',
        '   {% endfor %}',
        '</ul>',

    ])
    db.session.add(leaderemail)

    db.session.commit()
