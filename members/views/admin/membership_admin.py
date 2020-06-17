'''
membership_admin - membership administrative handling
===========================================
'''
# standard

# pypi
from flask import g, url_for, current_app, request
from flask_security import current_user

# homegrown
from . import bp
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN
from ...model import db, LocalInterest, LocalUser, CLUB_SERVICE_RUNSIGNUP
from .viewhelpers import localinterest
from running.runsignup import RunSignUp, ClubMemberships

class parameterError(Exception): pass

##########################################################################################
# members endpoint
###########################################################################################

clubmembers_dbattrs = 'id,membership_id,club_membership_level_name,first_name,last_name,email,membership_start,membership_end,primary_member,zipcode'.split(',')
clubmembers_formfields = 'rowid,membership_id,club_membership_level_name,first_name,last_name,email,membership_start,membership_end,primary_member,zipcode'.split(',')
clubmembers_dbmapping = dict(zip(clubmembers_dbattrs, clubmembers_formfields))
clubmembers_formmapping = dict(zip(clubmembers_formfields, clubmembers_dbattrs))

class ClubMembers(DbCrudApiInterestsRolePermissions):
    def open(self):
        linterest = localinterest()
        if linterest.club_service == CLUB_SERVICE_RUNSIGNUP:
            # get all data from RunSignUp
            with RunSignUp(key=current_app.config['RSU_KEY'], secret=current_app.config['RSU_SECRET']) as rsu:
                allmemberships = rsu.members(linterest.service_id, current_members_only='F')
            mships = ClubMemberships(allmemberships)

            # flatten some attributes
            members = [m for m in mships.members()]
            for member in members:
                # memberships (mships) are in order most recent to least recent
                latest = member.mships[0]
                earliest = member.mships[-1]
                member.id = latest.membership_id
                member.membership_id = latest.membership_id
                member.membership_start = earliest.membership_start
                member.membership_end = latest.membership_end
                member.club_membership_level_name = latest.club_membership_level_name
                member.zipcode = latest.zipcode

        # didn't find club service
        else:
            raise parameterError("Interest Attributes data error: could not find club service '{}'".format(linterest.club_service))

        self.rows = iter(members)

clubmembers_filters = filtercontainerdiv()
clubmembers_filters += filterdiv('members-external-filter-membership_start', 'Start')
clubmembers_filters += filterdiv('members-external-filter-membership_end', 'End')
clubmembers_filters += filterdiv('members-external-filter-level', 'Levels')

clubmembers_yadcf_options = [
    yadcfoption('membership_start:name', 'members-external-filter-membership_start', 'range_date'),
    yadcfoption('membership_end:name', 'members-external-filter-membership_end', 'range_date'),
    yadcfoption('club_membership_level_name:name', 'members-external-filter-level', 'multi_select', placeholder='Select levels', width='200px'),
]

clubmembers = ClubMembers(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = LocalUser,
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/membership-admin-guide.html'},
                    pretablehtml = clubmembers_filters.render(),
                    yadcfoptions = clubmembers_yadcf_options,
                    pagename = 'Club Members',
                    endpoint = 'admin.clubmembers',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/members',
                    dbmapping = clubmembers_dbmapping,
                    formmapping = clubmembers_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'last_name', 'name': 'last_name', 'label': 'Last Name',
                         'type':'readonly',
                         },
                        {'data': 'first_name', 'name': 'first_name', 'label': 'First Name',
                         'type': 'readonly',
                         },
                        {'data': 'email', 'name': 'email', 'label': 'email',
                         'type': 'readonly',
                         },
                        {'data': 'membership_id', 'name': 'membership_id', 'label': 'Membership ID',
                         'class': 'TextCenter',
                         'type':'readonly',
                         },
                        {'data': 'club_membership_level_name', 'name': 'club_membership_level_name', 'label': 'Level',
                         'type': 'readonly',
                         },
                        {'data': 'membership_start', 'name': 'membership_start', 'label': 'Start',
                         'type': 'readonly',
                         },
                        {'data': 'membership_end', 'name': 'membership_end', 'label': 'End',
                         'type': 'readonly',
                         },
                        {'data': 'primary_member', 'name': 'primary_member', 'label': 'Primary',
                         'class': 'TextCenter',
                         'type': 'readonly',
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons=[
                        {
                            'extend': 'csv',
                            'exportOptions': {
                                'columns': ':visible'
                            }
                        },
                    ],

                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
clubmembers.register()



