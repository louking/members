'''
userrole - specific user/role management for this application

This is needed to update local database tables when using common database for single sign-on
'''

# homegrown
from members import user_datastore
from ...model import update_local_tables
from ...version import __docversion__
from loutilities.user.views.userrole import UserView, InterestView, RoleView
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN, ROLE_MEETINGS_ADMIN
from loutilities.user.roles import ROLE_LEADERSHIP_ADMIN

orgadminguide = 'https://members.readthedocs.io/en/{docversion}/organization-admin-guide.html'.format(docversion=__docversion__)
superadminguide = 'https://members.readthedocs.io/en/{docversion}/super-admin-guide.html'.format(docversion=__docversion__)

class LocalUserView(UserView):
    def editor_method_postcommit(self, form):
        update_local_tables()
user_view = LocalUserView(
    pagename='members',
    user_datastore=user_datastore,
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_LEADERSHIP_ADMIN],
    endpoint='userrole.members',
    rule='/members',
    templateargs={'adminguide': orgadminguide},
)
user_view.register()

class LocalInterestView(InterestView):
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        args = dict(
            templateargs={'adminguide': superadminguide},
        )
        args.update(kwargs)

        # initialize inherited class, and a couple of attributes
        super().__init__(**args)

    def editor_method_postcommit(self, form):
        update_local_tables()
interest_view = LocalInterestView()
interest_view.register()

class LocalRoleView(RoleView):
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        args = dict(
            templateargs={'adminguide': superadminguide},
        )
        args.update(kwargs)

        # initialize inherited class, and a couple of attributes
        super().__init__(**args)

    def editor_method_postcommit(self, form):
        update_local_tables()
role_view = LocalRoleView()
role_view.register()
