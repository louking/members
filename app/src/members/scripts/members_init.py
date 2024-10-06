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
from members.model import db
from members.applogging import setlogging
from members.model import update_local_tables

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

    update_local_tables()

    db.session.commit()

