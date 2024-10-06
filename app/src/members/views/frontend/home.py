'''
home - frontend views
=================================
'''

# pypi
from flask import render_template
from flask.views import MethodView

# homegrown
from . import bp

#######################################################################
class FrontendHome(MethodView):

    def get(self):
        return render_template('home.jinja2',
                               pagename='Home',
                               frontend_page=True,
                               # causes redirect to current interest if bare url used
                               url_rule='/<interest>',
                               )

home_view = FrontendHome.as_view('home')
bp.add_url_rule('/', view_func=home_view, methods=['GET',])
bp.add_url_rule('/<interest>', view_func=home_view, methods=['GET',])

