'''
app.py is only used to support flask-migrate

develop execution from run.py; production execution from members.wsgi
'''
# standard
import os.path

# pypi
from flask_migrate import Migrate

# homegrown
from members import create_app
from members.settings import Production
from members.model import db

abspath = os.path.abspath(__file__)
configpath = os.path.join(os.path.dirname(abspath), 'config', 'members.cfg')
userconfigpath = os.path.join(os.path.dirname(abspath), 'config', 'users.cfg')
# userconfigpath first so configpath can override
configfiles = [userconfigpath, configpath]

# can't do local update when we create app as this would use database and cause
# sqlalchemy.exc.OperationalError if one of the updating tables needs migration
app = create_app(Production(configfiles), configfiles, local_update=False)

migrate = Migrate(app, db, compare_type=True)


