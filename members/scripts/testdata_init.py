'''
testdata_init - command line database initialization - initialize test data
=========================================================================================
run from 3 levels up, like python -m members.scripts.scripts.testdata_init

'''
# standard
from os.path import join, dirname
from datetime import timedelta, date, datetime

# pypi
from flask import url_for

# homegrown
from loutilities.transform import Transform
from members import create_app
from members.settings import Development
from members.model import db
from members.applogging import setlogging
from members.model import LocalUser, LocalInterest, Task, TaskGroup, TaskField, TaskTaskField, TaskCompletion
from members.model import input_type_all, gen_fieldname, FIELDNAME_ARG, INPUT_TYPE_UPLOAD, INPUT_TYPE_DATE
from loutilities.user.model import User, Interest

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

    testuser = User.query.filter_by(email='lou.king@steeplechasers.org').one()
    testinterest = Interest.query.filter_by(interest='fsrc').one()
    localtestinterest = LocalInterest.query.filter_by(interest_id=testinterest.id).one()
    localtestuser = LocalUser.query.filter_by(user_id=testuser.id, interest_id=localtestinterest.id).one()
    localtestinterest.initial_expiration = date(2020, 4, 1)
    localtestinterest.from_email = "volunteer@steeplechasers.org"

    eventaskgroup = TaskGroup(taskgroup='Even Tasks', description='even tasks description', interest=localtestinterest)
    db.session.add(eventaskgroup)
    oddtaskgroup = TaskGroup(taskgroup='Odd Tasks', description='odd tasks description', interest=localtestinterest)
    db.session.add(oddtaskgroup)
    doytaskgroup = TaskGroup(taskgroup='Date of Year Tasks', description='date of year tasks', interest=localtestinterest)
    db.session.add(oddtaskgroup)
    db.session.flush()
    eventaskgroup.users.append(localtestuser)
    oddtaskgroup.users.append(localtestuser)
    doytaskgroup.users.append(localtestuser)

    priority = 1
    for fieldtype in input_type_all:
        fieldname = gen_fieldname()
        thisfield = TaskField(taskfield='test {}'.format(fieldtype),
                              fieldname=fieldname,
                              interest=localtestinterest,
                              inputtype=fieldtype,
                              priority=priority,
                              displaylabel='Display Label {}'.format(fieldtype),
                              uploadurl=(url_for('admin.fieldupload', interest='fsrc')
                                            + '?{}={}'.format(FIELDNAME_ARG, fieldname)
                                         if fieldtype==INPUT_TYPE_UPLOAD else None)
                              )
        if fieldtype == INPUT_TYPE_DATE:
            thisfield.override_completion = True
        db.session.add(thisfield)
        db.session.flush()

        thistask = Task(task='Task {}'.format(fieldtype),
                        interest=localtestinterest,
                        description='Task description for {}'.format(fieldtype),
                        period=timedelta(52*7),
                        isoptional=False,
                        priority=priority,
                        # fields=[thisfield],
                        )
        task_taskfield = TaskTaskField(need='required', taskfield=thisfield)
        thistask.fields.append(task_taskfield)
        db.session.add(thistask)
        db.session.flush()

        if int(priority) % 2 == 0:
            eventaskgroup.tasks.append(thistask)
        else:
            oddtaskgroup.tasks.append(thistask)

        priority += 1

    doytests = [
        '01-01',
        '03-01',
        '05-01',
        '07-01',
        '09-01',
        '11-01',
    ]
    compls = [None, '01-02', '06-02', '12-15']
    today = date.today()
    todaymmdd = today.isoformat()[-5:]

    todayplus = today + timedelta(10)
    compls.append(todayplus.isoformat()[-5:])

    do_doytests = False
    if do_doytests:
        for doytest in doytests:
            for compl in compls:
                tasktext = 'Task compl {} (for {})'.format(compl, doytest)
                thistask = Task(task=tasktext,
                                description='Task compl {} (for {})'.format(compl, doytest),
                                interest=localtestinterest,
                                dateofyear=doytest,
                                isoptional=False,
                                priority=1,
                                expirystarts=timedelta(39*7),
                                expirysoon=timedelta(8*7),
                                )
                db.session.add(thistask)
                db.session.flush()
                doytaskgroup.tasks.append(thistask)

                taskmonth, taskday = [int(md) for md in doytest.split('-')]
                if compl:
                    complmonth, complday = [int(md) for md in compl.split('-')]
                    if compl <= todaymmdd:
                        year = today.year
                    else:
                        year = today.year - 1
                    taskcompletion = TaskCompletion(
                        interest=localtestinterest,
                        task=thistask,
                        user=localtestuser,
                        update_time = datetime.now(),
                        updated_by=localtestuser.id,
                        completion = datetime(year, complmonth, complday)
                    )
                    db.session.add(taskcompletion)

    db.session.commit()