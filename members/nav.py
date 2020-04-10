###########################################################################################
# nav - navigation 
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/04/20        Lou King        Create
#
#   Copyright 2020 Lou King.  All rights reserved
#
###########################################################################################
'''
nav - navigation
======================
define navigation bar based on privileges
'''

# standard

# pypi
from flask import g, current_app
from flask_nav import Nav
from flask_nav.elements import Navbar, View, Subgroup
from flask_nav.renderers import SimpleRenderer
from dominate import tags
from flask_security import current_user

# homegrown
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER

thisnav = Nav()

@thisnav.renderer()
class NavRenderer(SimpleRenderer):
    def visit_Subgroup(self, node):
        group = tags.ul(_class='subgroup')
        title = tags.div(node.title)

        if node.active:
            title.attributes['class'] = 'active'

        for item in node.items:
            group.add(tags.li(self.visit(item)))

        return [title, group]

@thisnav.navigation()
def nav_menu():
    navbar = Navbar('nav_menu')

    if current_user.is_authenticated:
        navbar.items.append(View('Home', 'admin.home', interest=g.interest))
        # deeper functions are only accessible when interest is set
        if g.interest:
            # leadership admin stuff
            if current_user.has_role(ROLE_LEADERSHIP_ADMIN) or current_user.has_role(ROLE_SUPER_ADMIN):
                leadershipadmin = Subgroup('Leadership Admin')
                navbar.items.append(leadershipadmin)
                leadershipadmin.items.append(View('Task Summary', 'admin.tasksummary', interest=g.interest))
                leadershipadmin.items.append(View('Assign Positions', 'admin.assignpositions', interest=g.interest))
                leadershipadmin.items.append(View('Positions', 'admin.positions', interest=g.interest))
                leadershipadmin.items.append(View('Task Groups', 'admin.taskgroups', interest=g.interest))
                leadershipadmin.items.append(View('Tasks', 'admin.tasks', interest=g.interest))
                leadershipadmin.items.append(View('Task Fields', 'admin.taskfields', interest=g.interest))
                leadershipadmin.items.append(View('History', 'admin.history', interest=g.interest))

            # leadership member stuff
            if (current_user.has_role(ROLE_LEADERSHIP_MEMBER)
                    or current_user.has_role(ROLE_LEADERSHIP_ADMIN)
                    or current_user.has_role(ROLE_SUPER_ADMIN)):
                # leadershipmember = Subgroup('Leadership Member')
                # navbar.items.append(leadershipmember)
                navbar.items.append(View('Task Checklist', 'admin.taskchecklist', interest=g.interest))

        # superadmin stuff
        if current_user.has_role(ROLE_SUPER_ADMIN):
            userroles = Subgroup('Members/Roles')
            navbar.items.append(userroles)
            userroles.items.append(View('Members', 'userrole.members'))
            userroles.items.append(View('Interest Attributes', 'admin.interestattrs'))
            userroles.items.append(View('Roles', 'userrole.roles'))
            userroles.items.append(View('Interests', 'userrole.interests'))
            userroles.items.append(View('Applications', 'userrole.applications'))

            if g.interest:
                navbar.items.append(View('Files', 'admin.files', interest=g.interest))

            navbar.items.append(View('My Account', 'security.change_password'))
            navbar.items.append(View('Debug', 'admin.debug'))

        # finally for non ROLE_SUPER_ADMIN
        else:
            navbar.items.append(View('My Account', 'security.change_password'))

    # common items
    if g.interest:
        pass
    navbar.items.append(View('About', 'admin.sysinfo'))

    return navbar

thisnav.init_app(current_app)
