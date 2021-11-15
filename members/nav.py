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
from flask_nav.elements import Navbar, View, Subgroup, Link, Separator
from flask_nav.renderers import SimpleRenderer
from dominate import tags
from flask_security import current_user
from slugify import slugify

# homegrown
from .version import __docversion__
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER
from loutilities.user.roles import ROLE_MEMBERSHIP_ADMIN
from loutilities.user.roles import ROLE_MEETINGS_ADMIN, ROLE_MEETINGS_MEMBER

thisnav = Nav()

@thisnav.renderer()
class NavRenderer(SimpleRenderer):
    '''
    this generates nav_renderer renderer, referenced in the jinja2 code which builds the nav
    '''
    def visit_Subgroup(self, node):
        # a tag required by smartmenus
        title = tags.a(node.title, href="#")
        group = tags.ul(_class='subgroup')

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
            self.basehelp = basehelp.format(docversion=__docversion__)

        def __call__(self, navmenu, text, endpoint, **kwargs):
            prelink = kwargs.pop('prelink', None)
            navmenu.items.append(View(text, endpoint, **kwargs))
            contexthelp[url_for(endpoint, **kwargs)] = self.basehelp + slugify(text + ' view')
            if not prelink:
                contexthelp[url_for(endpoint, **kwargs)] = self.basehelp + slugify(text + ' view')
            else:
                contexthelp[url_for(endpoint, **kwargs)] = self.basehelp + slugify(prelink + ' ' + text + ' view')

        def nomenu_help(self, text, endpoint, **kwargs):
            prelink = kwargs.pop('prelink', None)
            if not prelink:
                contexthelp[url_for(endpoint, **kwargs)] = self.basehelp + slugify(text + ' view')
            else:
                contexthelp[url_for(endpoint, **kwargs)] = self.basehelp + slugify(prelink + ' ' + text + ' view')


    org_admin_view = add_view('https://members.readthedocs.io/en/{docversion}/organization-admin-reference.html#')
    leadership_admin_view = add_view('https://members.readthedocs.io/en/{docversion}/leadership-task-admin-reference.html#')
    leadership_superadmin_view = add_view('https://members.readthedocs.io/en/{docversion}/super-admin-reference.html#')
    leadership_member_view = add_view('https://members.readthedocs.io/en/{docversion}/leadership-task-member-guide.html#')
    membership_admin_view = add_view('https://members.readthedocs.io/en/{docversion}/membership-admin-guide.html#')
    meetings_admin_view = add_view('https://members.readthedocs.io/en/{docversion}/meetings-admin-reference.html#')
    meetings_member_view = add_view('https://members.readthedocs.io/en/{docversion}/meetings-member-guide.html#')

    # create context help menu items for views which can't be navigated to from the main menu
    if g.interest:
        meetings_member_view.nomenu_help('My Status Report', 'admin.memberstatusreport', interest=g.interest)
        meetings_member_view.nomenu_help('RSVP', 'admin.rsvp', interest=g.interest)
        meetings_admin_view.nomenu_help('Meeting', 'admin.meeting', interest=g.interest)
        meetings_admin_view.nomenu_help('Meeting Status', 'admin.meetingstatus', interest=g.interest)

    if current_user.is_authenticated:
        navbar.items.append(View('Home', 'admin.home', interest=g.interest))
        # deeper functions are only accessible when interest is set
        if g.interest:
            # leadership member stuff
            if (current_user.has_role(ROLE_LEADERSHIP_MEMBER)
                    or current_user.has_role(ROLE_LEADERSHIP_ADMIN)
                    or current_user.has_role(ROLE_SUPER_ADMIN)):
                leadership_member_view(navbar, 'Task Checklist', 'admin.taskchecklist', interest=g.interest)

            # organization admin stuff visible to all members admins
            if (current_user.has_role(ROLE_MEETINGS_ADMIN)
                    or current_user.has_role(ROLE_LEADERSHIP_ADMIN)
                    or current_user.has_role(ROLE_MEMBERSHIP_ADMIN)
                    or current_user.has_role(ROLE_SUPER_ADMIN)):
                orgadmin = Subgroup('Organization')
                navbar.items.append(orgadmin)
                org_admin_view(orgadmin, 'Distribution List', 'admin.distribution', interest=g.interest)
                org_admin_view(orgadmin, 'Members', 'userrole.members')
                org_admin_view(orgadmin, 'Positions', 'admin.positions', interest=g.interest)
                org_admin_view(orgadmin, 'Position Dates', 'admin.positiondates', interest=g.interest)
                org_admin_view(orgadmin, 'Tags', 'admin.tags', interest=g.interest)

            # meetings member stuff
            if (current_user.has_role(ROLE_MEETINGS_MEMBER) or current_user.has_role(ROLE_MEETINGS_ADMIN)
                    or current_user.has_role(ROLE_SUPER_ADMIN)):
                meetingsviews = Subgroup('Meetings')
                navbar.items.append(meetingsviews)
               # meetings admin stuff
                if current_user.has_role(ROLE_MEETINGS_ADMIN) or current_user.has_role(ROLE_SUPER_ADMIN):
                    meetings_admin_view(meetingsviews, 'Meetings', 'admin.meetings', interest=g.interest)
                    meetings_admin_view(meetingsviews, 'Action Items', 'admin.actionitems', interest=g.interest)
                    meetings_admin_view(meetingsviews, 'Motions', 'admin.motions', interest=g.interest)
                    meetings_admin_view(meetingsviews, 'Motion Votes', 'admin.motionvotes', interest=g.interest)
                    meetings_admin_view(meetingsviews, 'Agenda Headings', 'admin.agendaheadings', interest=g.interest)
                    meetings_admin_view(meetingsviews, 'Invites', 'admin.invites', interest=g.interest)
                    meetings_admin_view(meetingsviews, 'Meeting Types', 'admin.meetingtypes', interest=g.interest)
                    meetingsviews.items.append(Separator())

                meetings_member_view(meetingsviews, 'My Meetings', 'admin.mymeetings', interest=g.interest)
                meetings_member_view(meetingsviews, 'My Action Items', 'admin.myactionitems', interest=g.interest)
                # todo: should this be disabled if no motionvotes for this user?
                meetings_member_view(meetingsviews, 'My Motion Votes', 'admin.mymotionvotes', interest=g.interest)
                # not sure there is any need for this
                # meetings_member_view(meetingsviews, 'My Discussion Items', 'admin.memberdiscussions', interest=g.interest)

                # meetings member, not admin
                if not (current_user.has_role(ROLE_MEETINGS_ADMIN) or current_user.has_role(ROLE_SUPER_ADMIN)):
                    meetings_member_view(meetingsviews, 'Action Items', 'admin.memberactionitems', interest=g.interest,
                                         prelink='member')
                    meetings_member_view(meetingsviews, 'Motions', 'admin.membermotions', interest=g.interest,
                                         prelink='member')

            # leadership admin stuff
            if current_user.has_role(ROLE_LEADERSHIP_ADMIN) or current_user.has_role(ROLE_SUPER_ADMIN):
                leadershipadmin = Subgroup('Tasks')
                navbar.items.append(leadershipadmin)
                leadership_admin_view(leadershipadmin, 'Member Summary', 'admin.membersummary', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Task Details', 'admin.taskdetails', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Task Groups', 'admin.taskgroups', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Tasks', 'admin.tasks', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'Task Fields', 'admin.taskfields', interest=g.interest)
                leadership_admin_view(leadershipadmin, 'History', 'admin.history', interest=g.interest)

            # membership admin stuff
            if current_user.has_role(ROLE_MEMBERSHIP_ADMIN) or current_user.has_role(ROLE_SUPER_ADMIN):
                membershipadmin = Subgroup('Membership')
                navbar.items.append(membershipadmin)
                membership_admin_view(membershipadmin, 'Club Members', 'admin.clubmembers', interest=g.interest)
                membership_admin_view(membershipadmin, 'Memberships', 'admin.memberships', interest=g.interest)
                membershipadmin.items.append(View('Membership Stats', 'frontend.membershipstats', interest=g.interest))

        # superadmin stuff
        if current_user.has_role(ROLE_SUPER_ADMIN):
            userroles = Subgroup('Super')
            navbar.items.append(userroles)
            leadership_superadmin_view(userroles, 'Interest Attributes', 'admin.interestattrs')

            if g.interest:
                leadership_superadmin_view(userroles, 'Email Templates', 'admin.emailtemplates', interest=g.interest)
                leadership_superadmin_view(userroles, 'Document Templates', 'admin.doctemplates', interest=g.interest)

            leadership_superadmin_view(userroles, 'Roles', 'userrole.roles')
            leadership_superadmin_view(userroles, 'Interests', 'userrole.interests')
            leadership_superadmin_view(userroles, 'Applications', 'userrole.applications')

            if g.interest:
                leadership_superadmin_view(userroles, 'Files', 'admin.files', interest=g.interest)

            navbar.items.append(View('My Account', 'security.change_password'))
            userroles.items.append(View('Debug', 'admin.debug'))

        # finally for non ROLE_SUPER_ADMIN
        else:
            navbar.items.append(View('My Account', 'security.change_password'))

    else:
        navbar.items.append(View('Home', 'frontend.home', interest=g.interest))
        if g.interest:
            usermemberssviews = Subgroup('Membership')
            navbar.items.append(usermemberssviews)
            usermemberssviews.items.append(View('Registered Members', 'frontend.members', interest=g.interest))
            usermemberssviews.items.append(View('Membership Stats', 'frontend.membershipstats', interest=g.interest))

    # common items
    if g.interest:
        pass
    navbar.items.append(View('About', 'admin.sysinfo'))
    if request.path in contexthelp:
        navbar.items.append(Link('Help', contexthelp[request.path]))

    return navbar

thisnav.init_app(current_app)
