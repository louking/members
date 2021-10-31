'''
membership_admin - membership administrative handling
===========================================
'''
# standard
from datetime import datetime
from operator import and_

# pypi
from flask import g, url_for, current_app, request
from flask_security import current_user
from dominate.tags import div, span, i, button, input
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN
from loutilities.timeu import asctime
from sqlalchemy import func

# homegrown
from . import bp
from ...model import db, LocalInterest, LocalUser, CLUB_SERVICE_RUNSIGNUP
from ...model import Member, Membership
from ...version import __docversion__
from .viewhelpers import localinterest
from running.runsignup import RunSignUp, ClubMemberships

class parameterError(Exception): pass

ymd = asctime('%Y-%m-%d')

adminguide = 'https://members.readthedocs.io/en/{docversion}/membership-admin-guide.html'.format(docversion=__docversion__)

##########################################################################################
# members endpoint
###########################################################################################

clubmembers_dbattrs = 'id,svc_member_id,given_name,family_name,gender,dob,email,hometown,start_date,end_date,'.split(',')
clubmembers_formfields = 'rowid,svc_member_id,given_name,family_name,gender,dob,email,hometown,start_date,end_date'.split(',')
clubmembers_dbmapping = dict(zip(clubmembers_dbattrs, clubmembers_formfields))
clubmembers_formmapping = dict(zip(clubmembers_formfields, clubmembers_dbattrs))

class ClubMembers(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        '''
        add update query parameters based on ondate
        '''
        self.queryfilters = []
        super().beforequery()
        ondate = request.args.get('ondate', ymd.dt2asc(datetime.now()))
        ondatedt = ymd.asc2dt(ondate)
        self.queryfilters += [Member.start_date <= ondatedt, Member.end_date >= ondatedt]

def clubmembers_filters():
    pretablehtml = div()
    with pretablehtml:
        # hide / show hidden rows
        with filtercontainerdiv(style='margin-bottom: 4px;'):
            datefilter = filterdiv('fsrcmembers-external-filter-asof', 'As Of')
            with datefilter:
                with span(id='spinner', style='display:none;'):
                    i(cls='fas fa-spinner fa-spin')
                input(type='text', id='effective-date', name='effective-date' )
                button('Today', id='todays-date-button')
            # filterdiv('members-external-filter-level', 'Levels')
    return pretablehtml.render()

clubmembers_yadcf_options = [
    # yadcfoption('club_membership_level_name:name', 'members-external-filter-level', 'multi_select', placeholder='Select levels', width='200px'),
]

clubmembers_view = ClubMembers(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Member,
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
                    pretablehtml = clubmembers_filters,
                    yadcfoptions = clubmembers_yadcf_options,
                    pagename = 'Club Members',
                    endpoint = 'admin.clubmembers',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/members',
                    dbmapping = clubmembers_dbmapping,
                    formmapping = clubmembers_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'family_name', 'name': 'family_name', 'label': 'Last Name',
                         'type':'readonly',
                         },
                        {'data': 'given_name', 'name': 'given_name', 'label': 'First Name',
                         'type': 'readonly',
                         },
                        {'data': 'gender', 'name': 'gender', 'label': 'Gender',
                         'type': 'readonly',
                         },
                        {'data': 'dob', 'name': 'dob', 'label': 'DOB',
                         'type': 'readonly',
                         '_ColumnDT_args' :
                             {'sqla_expr': func.date_format(Member.dob, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'},
                         },
                        {'data': 'svc_member_id', 'name': 'svc_member_id', 'label': 'Member ID',
                         'type': 'readonly',
                         },
                        {'data': 'email', 'name': 'email', 'label': 'Email',
                         'type': 'readonly',
                         },
                        {'data': 'hometown', 'name': 'hometown', 'label': 'Hometown',
                         'type': 'readonly',
                         },
                        {'data': 'start_date', 'name': 'start_date', 'label': 'Start',
                         'type': 'readonly',
                         '_ColumnDT_args' :
                             {'sqla_expr': func.date_format(Member.start_date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'},
                         },
                        {'data': 'end_date', 'name': 'end_date', 'label': 'End',
                         'type': 'readonly',
                         '_ColumnDT_args' :
                             {'sqla_expr': func.date_format(Member.end_date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'},
                         },
                    ],
                    serverside = True,
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
clubmembers_view.register()


##########################################################################################
# memberships endpoint
###########################################################################################

memberships_dbattrs = 'id,svc_membership_id,svc_member_id,membershiptype,member.given_name,member.family_name,member.gender,member.dob,hometown,email,start_date,end_date,primary,last_modified'.split(',')
memberships_formfields = 'rowid,svc_membership_id,svc_member_id,membershiptype,given_name,family_name,gender,dob,hometown,email,start_date,end_date,primary,last_modified'.split(',')
memberships_dbmapping = dict(zip(memberships_dbattrs, memberships_formfields))
memberships_formmapping = dict(zip(memberships_formfields, memberships_dbattrs))

class MembershipsView(DbCrudApiInterestsRolePermissions):
    def open(self):
        linterest = localinterest()
        return super().open()

def memberships_pretablehtml():
    pretablehtml = div()
    return pretablehtml.render()

memberships_view = MembershipsView(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Membership,
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
                    pretablehtml = memberships_pretablehtml,
                    pagename = 'Memberships',
                    endpoint = 'admin.memberships',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/memberships',
                    dbmapping = memberships_dbmapping,
                    formmapping = memberships_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'family_name', 'name': 'family_name', 'label': 'Last Name',
                         'type':'readonly',
                         },
                        {'data': 'given_name', 'name': 'given_name', 'label': 'First Name',
                         'type': 'readonly',
                         },
                        {'data': 'gender', 'name': 'gender', 'label': 'Gender',
                         'type': 'readonly',
                         },
                        {'data': 'dob', 'name': 'dob', 'label': 'DOB',
                         'type': 'readonly',
                         '_ColumnDT_args' :
                             {'sqla_expr': func.date_format(Member.dob, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'},
                         },
                        {'data': 'hometown', 'name': 'hometown', 'label': 'Hometown',
                         'type': 'readonly',
                         },
                        {'data': 'email', 'name': 'email', 'label': 'Email',
                         'type': 'readonly',
                         },
                        {'data': 'svc_membership_id', 'name': 'svc_membership_id', 'label': 'Membership ID',
                         'type': 'readonly',
                         },
                        {'data': 'svc_member_id', 'name': 'svc_member_id', 'label': 'Member ID',
                         'type': 'readonly',
                         },
                        {'data': 'membershiptype', 'name': 'membershiptype', 'label': 'Membership Type',
                         'class': 'TextCenter',
                         'type':'readonly',
                         },
                        {'data': 'primary', 'name': 'primary', 'label': 'Primary',
                         'class': 'TextCenter',
                         'type': 'readonly',
                         },
                        {'data': 'start_date', 'name': 'start_date', 'label': 'Start',
                         'type': 'readonly',
                         '_ColumnDT_args' :
                             {'sqla_expr': func.date_format(Membership.start_date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'},
                         },
                        {'data': 'end_date', 'name': 'end_date', 'label': 'End',
                         'type': 'readonly',
                         '_ColumnDT_args' :
                             {'sqla_expr': func.date_format(Membership.end_date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'},
                         },
                        {'data': 'last_modified', 'name': 'last_modified', 'label': 'Last Updated',
                         'type': 'readonly',
                         '_ColumnDT_args' :
                             {'sqla_expr': func.date_format(Membership.last_modified, '%Y-%m-%d %H:%i:%S'), 'search_method': 'yadcf_range_date'},
                         },
                    ],
                    serverside=True,
                    idSrc = 'rowid', 
                    buttons=[
                        # 'remove',
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
                        'order': [
                            ['family_name:name', 'asc'],
                            ['given_name:name', 'asc'],
                            ['end_date:name', 'asc'],
                        ]
                    },
                    )
memberships_view.register()

