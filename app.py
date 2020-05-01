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
app = create_app(Production(configfiles), configfiles)

migrate = Migrate(app, db)


