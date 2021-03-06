'''
users_init - command line database initialization - clean database initialize users
=========================================================================================
run from 3 levels up, like python -m members.scripts.users_init

'''
# standard
from os.path import join, dirname
from copy import deepcopy

# pypi

# homegrown
from loutilities.transform import Transform
from loutilities.user import create_app
from loutilities.user.settings import Development
from loutilities.user.model import db
from loutilities.user.applogging import setlogging
from loutilities.user.model import User, Role, Interest, Application
from loutilities.user.model import APP_ALL
from loutilities.user.roles import all_roles

class parameterError(Exception): pass

#--------------------------------------------------------------------------
def init_db(defineowner=True):
#--------------------------------------------------------------------------

    # must wait until user_datastore is initialized before import
    from loutilities.user import user_datastore
    from flask_security import hash_password

    # special processing for user roles because need to remember the roles when defining the owner
    # define user roles here

    interests = [
        {'interest':'fsrc', 'description':'Frederick Steeplechasers Running Club', 'public':True}
    ]

    # initialize applications, remembering what applications we have
    allapps = []
    appname2db = {}
    for app in APP_ALL:
        thisapp = Application(application=app)
        db.session.add(thisapp)
        db.session.flush()
        allapps.append(thisapp)
        appname2db[app] = thisapp

    # initialize roles, remembering what roles we have
    combinedroles = {}
    local_all_roles = deepcopy(all_roles)
    for approles in local_all_roles:
        for approle in approles:
            apps = approle.pop('apps')
            rolename = approle['name']
            thisrole = Role.query.filter_by(name=rolename).one_or_none() or user_datastore.create_role(**approle)
            for thisapp in apps:
                thisrole.applications.append(appname2db[thisapp])
            combinedroles[rolename] = thisrole

    allinterests = []
    # initialize interests, remembering what interests we have
    # common interests are associated with all applications
    for interest in interests:
        thisinterest = Interest(**interest)
        for thisapp in allapps:
            thisinterest.applications.append(thisapp)
        db.session.flush()
        allinterests.append(thisinterest)

    # define owner if desired
    if defineowner:
        from flask import current_app
        rootuser = current_app.config['APP_OWNER']
        rootpw = current_app.config['APP_OWNER_PW']
        name = current_app.config['APP_OWNER_NAME']
        given_name = current_app.config['APP_OWNER_GIVEN_NAME']
        owner = User.query.filter_by(email=rootuser).first()
        if not owner:
            owner = user_datastore.create_user(email=rootuser, password=hash_password(rootpw), name=name, given_name=given_name)
            for rolename in combinedroles:
                user_datastore.add_role_to_user(owner, combinedroles[rolename])
        db.session.flush()
        owner = User.query.filter_by(email=rootuser).one()
        if not owner.interests:
            for thisinterest in allinterests:
                owner.interests.append(thisinterest)

    # and we're done, let's accept what we did
    db.session.commit()


scriptdir = dirname(__file__)
# two levels up
scriptfolder = dirname(dirname(scriptdir))
configdir = join(scriptfolder, 'config')
configfile = "users.cfg"
configpath = join(configdir, configfile)

# create app and get configuration
app = create_app(Development(configpath), configpath)

# set up database
db.init_app(app)

# set up scoped session
with app.app_context():
    # turn on logging
    setlogging()

    # clear and initialize the user database
    db.drop_all(bind='users')
    db.create_all(bind='users')
    init_db()
    db.session.commit()

