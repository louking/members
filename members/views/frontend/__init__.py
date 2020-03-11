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

# create blueprint first
bp = Blueprint('frontend', __name__.split('.')[0], url_prefix='', static_folder='static/frontend', template_folder='templates/frontend')
