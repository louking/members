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
from flask import g, current_app, url_for, request
from flask_nav import Nav
from flask_nav.elements import Navbar, View, Subgroup, Link
from flask_nav.renderers import SimpleRenderer
from dominate import tags
from flask_security import current_user
from slugify import slugify

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

    contexthelp = {}
    class add_view():
        def __init__(self, basehelp):
            self.basehelp = basehelp

        def __call__(self, navmenu, text, endpoint, **kwargs):
            navmenu.items.append(View(text, endpoint, **kwargs))
            contexthelp[url_for(endpoint, **kwargs)] = self.basehelp + slugify(text + ' view')

    leadership_admin_view = add_view('https://members.readthedocs.io/en/latest/leadership-task-admin-reference.html#')
    leadership_superadmin_view = add_view('https://members.readthedocs.io/en/latest/leadership-task-superadmin-reference.html#')
    leadership_member_view = add_view('https://members.readthedocs.io/en/latest/leadership-task-member-guide.html#')

    if current_user.is_authenticated:
        navbar.items.append(View('Home', 'admin.home', interest=g.interest))
        # deeper functions are only accessible when interest is set
        if g.interest:
            # leadership member stuff
            if (current_user.has_role(ROLE_LEADERSHIP_MEMBER)
                    or current_user.has_role(ROLE_LEADERSHIP_ADMIN)
                    or current_user.has_role(ROLE_SUPER_ADMIN)):
                # leadershipmember = Subgroup('Leadership Member')
                # navbar.items.append(leadershipmember)
                leadership_member_view(navbar, 'Task Checklist', 'admin.taskchecklist', interest=g.interest)

            # leadership admin stuff
            if current_user.has_role(ROLE_LEADERSHIP_ADMIN) or current_user.has_role(ROLE_SUPER_ADMIN):
                leadershipadmin = Subgroup('Leadership Admin')
                navbar.items.append(leadershipadmin)
                leadership_admin_view(leadershipadmin, 'Member Summary', 'admin.membersummary', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Task Details', 'admin.taskdetails', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Assign Tasks', 'admin.assigntasks', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Positions', 'admin.positions', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Task Groups', 'admin.taskgroups', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Tasks', 'admin.tasks', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Task Fields', 'admin.taskfields', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'History', 'admin.history', interest=g.interest)

        # superadmin stuff
        if current_user.has_role(ROLE_SUPER_ADMIN):
            userroles = Subgroup('Members/Roles')
            navbar.items.append(userroles)
            leadership_superadmin_view(userroles, 'Members', 'userrole.members')
            leadership_superadmin_view(userroles, 'Interest Attributes', 'admin.interestattrs')
            leadership_superadmin_view(userroles, 'Roles', 'userrole.roles')
            leadership_superadmin_view(userroles, 'Interests', 'userrole.interests')
            leadership_superadmin_view(userroles, 'Applications', 'userrole.applications')

            if g.interest:
                leadership_superadmin_view(navbar, 'Email Templates', 'admin.emailtemplates', interest=g.interest)
                leadership_superadmin_view(navbar, 'Files', 'admin.files', interest=g.interest)

            navbar.items.append(View('My Account', 'security.change_password'))
            navbar.items.append(View('Debug', 'admin.debug'))

        # finally for non ROLE_SUPER_ADMIN
        else:
            navbar.items.append(View('My Account', 'security.change_password'))

    # common items
    if g.interest:
        pass
    navbar.items.append(View('About', 'admin.sysinfo'))
    if request.path in contexthelp:
        navbar.items.append(Link('Help', contexthelp[request.path]))

    return navbar

thisnav.init_app(current_app)
