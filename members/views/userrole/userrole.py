'''
userrole - specific user/role management for this application

This is needed to update local database tables when using common database for single sign-on
'''

# homegrown
from members import user_datastore
from ...model import update_local_tables
from loutilities.user.views.userrole import UserView, InterestView, RoleView
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN, ROLE_MEETINGS_ADMIN
from loutilities.user.roles import ROLE_LEADERSHIP_ADMIN

class LocalUserView(UserView):
    def editor_method_postcommit(self, form):
        update_local_tables()
user = LocalUserView(
    pagename='members',
    user_datastore=user_datastore,
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_LEADERSHIP_ADMIN],
    endpoint='userrole.members',
    rule='/members',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-superadmin-guide.html'},
)
user.register()

class LocalInterestView(InterestView):
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        args = dict(
            templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-superadmin-guide.html'},
        )
        args.update(kwargs)

        # initialize inherited class, and a couple of attributes
        super().__init__(**args)

    def editor_method_postcommit(self, form):
        update_local_tables()
interest = LocalInterestView()
interest.register()

class LocalRoleView(RoleView):
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        args = dict(
            templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-superadmin-guide.html'},
        )
        args.update(kwargs)

        # initialize inherited class, and a couple of attributes
        super().__init__(**args)

    def editor_method_postcommit(self, form):
        update_local_tables()
role = LocalRoleView()
role.register()
