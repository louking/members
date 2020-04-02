'''
testdata_init - command line database initialization - initialize test data
=========================================================================================
run from 3 levels up, like python -m members.scripts.scripts.testdata_init

'''
# standard
from os.path import join, dirname
from datetime import timedelta

# pypi
from flask import url_for

# homegrown
from loutilities.transform import Transform
from members import create_app
from members.settings import Development
from members.model import db
from members.applogging import setlogging
from members.model import LocalInterest, Task, TaskGroup, TaskField, TaskTaskField
from members.model import input_type_all, gen_fieldname, FIELDNAME_ARG, INPUT_TYPE_UPLOAD
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

    eventaskgroup = TaskGroup(taskgroup='Even Tasks', description='even tasks description', interest=localtestinterest)
    db.session.add(eventaskgroup)
    oddtaskgroup = TaskGroup(taskgroup='Odd Tasks', description='odd tasks description', interest=localtestinterest)
    db.session.add(oddtaskgroup)

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
        db.session.flush()

        if int(priority) % 2 == 0:
            eventaskgroup.tasks.append(thistask)
        else:
            oddtaskgroup.tasks.append(thistask)

        priority += 1

    db.session.commit()