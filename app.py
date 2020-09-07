'''
app.py is only used to support flask commands

develop execution from run.py; production execution from members.wsgi
'''
# standard
import os.path

# pypi
from flask_migrate import Migrate
from sqlalchemy.orm import scoped_session, sessionmaker

# homegrown
from members import create_app
from members.settings import Production
from members.model import db
from members.applogging import setlogging
from scripts import Members

abspath = os.path.abspath(__file__)
configpath = os.path.join(os.path.dirname(abspath), 'config', 'members.cfg')
userconfigpath = os.path.join(os.path.dirname(abspath), 'config', 'users.cfg')
# userconfigpath first so configpath can override
configfiles = [userconfigpath, configpath]

# local_update=False because when we create app this would use database and cause
# sqlalchemy.exc.OperationalError if one of the updating tables needs migration
app = create_app(Production(configfiles), configfiles, local_update=False)

# set up scoped session
with app.app_context():
# this causes SQLALCHEMY_BINDS not to work ('user' bind missing)
#     db.session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=db.engine))
#     db.query = db.session.query_property()

    # turn on logging
    setlogging()

migrate = Migrate(app, db, compare_type=True)
members = Members(app, db)


