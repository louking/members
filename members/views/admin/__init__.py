###########################################################################################
# blueprint for this view folder
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/04/20        Lou King        Create
#
#   Copyright 2020 Lou King
###########################################################################################

from flask import Blueprint

bp = Blueprint('admin', __name__.split('.')[0], url_prefix='/admin', static_folder='static/admin', template_folder='templates/admin')

# common
from . import home
from . import local_user_interest
from . import files
from . import sysinfo

# leadership task module
from . import leadership_tasks_superadmin
from . import leadership_tasks_admin
from . import leadership_tasks_member

