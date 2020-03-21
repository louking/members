from loutilities.user.views.userrole import UserView, InterestView, RoleView
from ...model import update_local_tables

class LocalUserView(UserView):
    def editor_method_postcommit(self, form):
        update_local_tables()
user = LocalUserView()
user.register()

class LocalInterestView(InterestView):
    def editor_method_postcommit(self, form):
        update_local_tables()
interest = LocalInterestView()
interest.register()

class LocalRoleView(RoleView):
    def editor_method_postcommit(self, form):
        update_local_tables()
role = LocalRoleView()
role.register()
