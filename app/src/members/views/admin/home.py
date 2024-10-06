'''
home - administrative views
=================================
'''

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
        return render_template('home.jinja2',
                               pagename='Admin Home',
                               # causes redirect to current interest if bare url used
                               url_rule='/admin/<interest>',
                               )

admin_view = AdminHome.as_view('home')
bp.add_url_rule('/', view_func=admin_view, methods=['GET',])
bp.add_url_rule('/<interest>', view_func=admin_view, methods=['GET',])

