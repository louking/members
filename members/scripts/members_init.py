###########################################################################################
# members_init - command line database initialization - clean database initialize tasks
#
#       Date            Author          Reason
#       ----            ------          ------
#       12/20/18        Lou King        Create
#
#   Copyright 2018 Lou King.  All rights reserved
###########################################################################################
'''
members_init - command line database initialization - clean database initialize tasks
=========================================================================================
run from 3 levels up, like python -m members.scripts.scripts.members_init

'''
# standard
from os.path import join, dirname

# pypi

# homegrown
from loutilities.transform import Transform
from members import create_app
from members.settings import Development
from members.model import db, InputType
from members.applogging import setlogging
from members.model import update_local_tables, input_type_all

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

    # clear and initialize the members database
    # bind=None per https://flask-sqlalchemy.palletsprojects.com/en/2.x/binds/
    db.drop_all(bind=None)
    db.create_all(bind=None)

    # create initial input types (not per Interest)
    for input_type in input_type_all:
        thisinputtype = InputType(inputtype=input_type)
        db.session.add(thisinputtype)

    # initialize LocalUser table based on User table
    update_local_tables()

    db.session.commit()

