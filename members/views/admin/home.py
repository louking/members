###########################################################################################
# home - administrative views
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/09/20        Lou King        Create
#
#   Copyright 2020 Lou King.  All rights reserved
###########################################################################################

# pypi
from flask import render_template
from flask.views import MethodView
from flask_security import auth_required

# homegrown
from . import bp

#######################################################################
class AdminHome(MethodView):
    decorators = [auth_required()]

    def get(self):
        return render_template('admin.jinja2',
                               pagename='Admin Home',
                               # causes redirect to current interest if bare url used
                               url_rule='/admin/<interest>',
                               )

admin_view = AdminHome.as_view('home')
bp.add_url_rule('/', view_func=admin_view, methods=['GET',])
bp.add_url_rule('/<interest>', view_func=admin_view, methods=['GET',])

