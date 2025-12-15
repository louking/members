'''
app.py is only used to support flask commands

app_server.py for webserver execution
    must match with app.py except for under "flask command processing"
'''
# standard
import os.path
from os import environ

# pypi
from flask_migrate import Migrate

# homegrown
from members import create_app
from members.settings import Production
from members.model import db
from members.applogging import setlogging
from scripts import MembersCli, MembershipCli, TaskCli, CommunityCli

appname = environ['APP_NAME']

abspath = os.path.abspath('/config')
configpath = os.path.join(abspath, f'{appname}.cfg')
userconfigpath = os.path.join(abspath, 'users.cfg')
# userconfigpath first so configpath can override
configfiles = [userconfigpath, configpath]

# init_for_operation=False because when we create app this would use database and cause
# sqlalchemy.exc.OperationalError if one of the updating tables needs migration
app = create_app(Production(configfiles), configfiles, init_for_operation=False)

# set up flask command processing (not needed within app_server.py)
migrate = Migrate(app, db, compare_type=True)
members = MembersCli(app, db)
membership = MembershipCli(app, db)
task = TaskCli(app, db)
community = CommunityCli(app, db)

# Needed only if serving web pages
# implement proxy fix (https://github.com/sjmf/reverse-proxy-minimal-example)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_port=1, x_proto=1, x_prefix=1)


