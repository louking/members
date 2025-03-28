'''
members - package
====================
'''

# standard
import os.path
from os import environ

# pypi
from flask import Flask, send_from_directory, g, session, request, url_for, render_template, current_app
from flask_mail import Mail
from jinja2 import ChoiceLoader, PackageLoader
from flask_security import SQLAlchemyUserDatastore, current_user
from werkzeug.local import LocalProxy

# homegrown
from .views.admin.viewhelpers import localinterest
from .model import update_local_tables, LocalUser, LocalInterest
from .views.admin.uploads import init_uploads
import loutilities
from loutilities.configparser import getitems
from loutilities.user import UserSecurity
from loutilities.user.model import Interest, Application, User, Role
from loutilities.flask_helpers.mailer import sendmail

# define security globals
user_datastore = None
security = None

# hold application here
app = None
appname = environ['APP_NAME']

# create application
def create_app(config_obj, configfiles=None, init_for_operation=True):
    '''
    apply configuration object, then configuration files
    '''
    global app
    # can't have hyphen in package name, so need to specify with underscore
    app = Flask(appname.replace('-', '_'))
    app.config.from_object(config_obj)
    if configfiles:
        for configfile in configfiles:
            appconfig = getitems(configfile, 'app')
            app.config.update(appconfig)

    # load any environment variables which start with FLASK_
    app.config.from_prefixed_env(prefix='FLASK')

    with app.app_context():
        # turn on logging
        from .applogging import setlogging
        setlogging()

    # tell jinja to remove linebreaks
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    # define product name (don't import nav until after app.jinja_env.globals['_productname'] set)
    app.jinja_env.globals['_productname'] = app.config['THISAPP_PRODUCTNAME']
    app.jinja_env.globals['_productname_text'] = app.config['THISAPP_PRODUCTNAME_TEXT']
    for configkey in ['SECURITY_EMAIL_SUBJECT_PASSWORD_RESET',
                      'SECURITY_EMAIL_SUBJECT_PASSWORD_CHANGE_NOTICE',
                      'SECURITY_EMAIL_SUBJECT_PASSWORD_NOTICE',
                      ]:
        app.config[configkey] = app.config[configkey].format(productname=app.config['THISAPP_PRODUCTNAME_TEXT'])

    # initialize database
    from .model import db
    db.init_app(app)

    # initialize uploads
    if init_for_operation:
        init_uploads(app)

    # handle <interest> in URL - https://flask.palletsprojects.com/en/1.1.x/patterns/urlprocessors/
    @app.url_value_preprocessor
    def pull_interest(endpoint, values):
        try:
            g.interest = values.pop('interest', None)
        except AttributeError:
            g.interest = None
        finally:
            if not g.interest:
                g.interest = request.args.get('interest', None)

    # add loutilities tables-assets for js/css/template loading
    # see https://adambard.com/blog/fresh-flask-setup/
    #    and https://webassets.readthedocs.io/en/latest/environment.html#webassets.env.Environment.load_path
    # loutilities.__file__ is __init__.py file inside loutilities; os.path.split gets package directory
    loutilitiespath = os.path.join(os.path.split(loutilities.__file__)[0], 'tables-assets', 'static')

    @app.route('/loutilities/static/<path:filename>')
    def loutilities_static(filename):
        return send_from_directory(loutilitiespath, filename)

    # bring in js, css assets here, because app needs to be created first
    from .assets import asset_env, asset_bundles
    with app.app_context():
        # needs to be set before update_local_tables called and before UserSecurity() instantiated
        g.loutility = Application.query.filter_by(application=app.config['APP_LOUTILITY']).one()

        # update LocalUser and LocalInterest tables
        if init_for_operation:
            update_local_tables()

        # js/css files
        asset_env.append_path(app.static_folder)
        asset_env.append_path(loutilitiespath, '/loutilities/static')

        # templates
        loader = ChoiceLoader([
            app.jinja_loader,
            PackageLoader('loutilities', 'tables-assets/templates')
        ])
        app.jinja_loader = loader

    # initialize assets
    asset_env.init_app(app)
    asset_env.register(asset_bundles)

    # Set up Flask-Mail [configuration in <application>.cfg] and security mailer
    mail = Mail(app)

    def security_send_mail(subject, recipient, template, **context):
        # this may be called from view which doesn't reference interest
        # if so pick up user's first interest to get from_email address
        if not g.interest:
            g.interest = context['user'].interests[0].interest if context['user'].interests else None
        if g.interest:
            from_email = localinterest().from_email
        # use default if user didn't have any interests
        else:
            from_email = current_app.config['SECURITY_EMAIL_SENDER']
            # copied from flask_security.utils.send_mail
            if isinstance(from_email, LocalProxy):
                from_email = from_email._get_current_object()
        ctx = ('security/email', template)
        html = render_template('%s/%s.html' % ctx, **context)
        text = render_template('%s/%s.txt' % ctx, **context)
        sendmail(subject, from_email, recipient, html=html, text=text)

    # Set up Flask-Security
    global user_datastore, security
    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    security = UserSecurity(app, user_datastore, send_mail=security_send_mail)

    # activate views
    from .views import userrole as userroleviews
    from loutilities.user.views import bp as userrole
    app.register_blueprint(userrole)
    from .views.frontend import bp as frontend
    app.register_blueprint(frontend)
    from .views.admin import bp as admin
    app.register_blueprint(admin)

    # need to force app context else get
    #    RuntimeError: Working outside of application context.
    #    RuntimeError: Attempted to generate a URL without the application context being pushed.
    # see http://kronosapiens.github.io/blog/2014/08/14/understanding-contexts-in-flask.html
    with app.app_context():
        # import navigation after views created
        from . import nav
       
        # set up scoped session
        from sqlalchemy.orm import scoped_session, sessionmaker
        # see https://github.com/pallets/flask-sqlalchemy/blob/706982bb8a096220d29e5cef156950237753d89f/flask_sqlalchemy/__init__.py#L990
        db.session = scoped_session(sessionmaker(autocommit=False,
                                                 autoflush=False,
                                                 binds=db.get_binds()))
        db.query = db.session.query_property()

        # handle favicon request for old browsers
        app.add_url_rule('/favicon.ico', endpoint='favicon',
                        redirect_to=url_for('static', filename='favicon.ico'))

    # ----------------------------------------------------------------------
    @app.before_request
    def before_request():
        g.loutility = Application.query.filter_by(application=app.config['APP_LOUTILITY']).one()

        if current_user.is_authenticated:
            user = current_user
            email = user.email

            # used in layout.jinja2
            app.jinja_env.globals['user_interests'] = sorted([{'interest': i.interest, 'description': i.description}
                                                              for i in user.interests if g.loutility in i.applications],
                                                             key=lambda a: a['description'].lower())
            session['user_email'] = email

        else:
            # used in layout.jinja2
            pubinterests = Interest.query.filter_by(public=True).all()
            app.jinja_env.globals['user_interests'] = sorted([{'interest': i.interest, 'description': i.description}
                                                              for i in pubinterests if g.loutility in i.applications],
                                                             key=lambda a: a['description'].lower())
            session.pop('user_email', None)

    # ----------------------------------------------------------------------
    @app.after_request
    def after_request(response):
        # # check if there are any changes needed to LocalUser table
        # userupdated = User.query.order_by(desc('updated_at')).first().updated_at
        # localuserupdated = LocalUser.query.order_by(desc('updated_at')).first().updated_at
        # interestupdated = Interest.query.order_by(desc('updated_at')).first().updated_at
        # localinterestupdated = LocalInterest.query.order_by(desc('updated_at')).first().updated_at
        # if userupdated > localuserupdated or interestupdated > localinterestupdated:
        #     update_local_tables()

        if not app.config['DEBUG']:
            app.logger.info(
                '{}: {} {} {}'.format(request.remote_addr, request.method, request.url, response.status_code))
        return response

    # app back to caller
    return app




