'''
membership_admin - membership administrative handling
===========================================
'''
# standard
from datetime import datetime, timedelta, date
from operator import and_
from platform import system

# pypi
from flask import request
from dominate.tags import div, span, i, button, input_
from loutilities.tables import DteDbOptionsPickerBase
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.filters import filtercontainerdiv, filterdiv
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN
from loutilities.timeu import asctime
from sqlalchemy import func

# homegrown
from . import bp
from ...model import db, LocalInterest
from ...model import Member, Membership, TableUpdateTime, MemberAlias
from ...version import __docversion__
from .viewhelpers import localinterest

class parameterError(Exception): pass
class dataError(Exception): pass

ymd = asctime('%Y-%m-%d')
isodate = asctime('%Y-%m-%d')

# https://stackoverflow.com/questions/49674902/datetime-object-without-leading-zero
if system() != 'Windows':
    cachet = asctime('%-m/%-d/%Y %-I:%M %p')
else:
    cachet = asctime('%#m/%#d/%Y %#I:%M %p')
    
adminguide = 'https://members.readthedocs.io/en/{docversion}/membership-admin-guide.html'.format(docversion=__docversion__)

##########################################################################################
# members endpoint
##########################################################################################

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
                input_(type='text', id='effective-date', name='effective-date' )
                button('Today', id='todays-date-button')
                cachetime = TableUpdateTime.query.filter_by(interest=localinterest(), tablename='member').one().lastchecked
                span(f'(last update time {cachet.dt2asc(cachetime)})')
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
                        'scrollY': '55vh',
                        'lengthMenu': [ [10, 25, 50, 100, -1], [10, 25, 50, 100, 'All'] ],
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

    def deleterow(self, thisid):
        membership = Membership.query.filter_by(id=thisid).one()

        # update member record(s) by recalculating contiguous membership dates
        if membership.member:
            member = membership.member

            # this membership will be deleted, so remove member association 
            # NOTE: this also removes membership from member.memberships
            membership.member = None

            # if membership is not wholly contained within member, there was some data error, probably in membership_cli
            if membership.start_date < member.start_date or membership.end_date > member.end_date:
                raise dataError(f'membership {membership.id} references member {member.id} but extent of membership goes beyond that of member')

            # if membership extent is same as member, this membership must have been the only membership referenced by member
            # NOTE: this membership was removed from member.memberships above, so checking against 0
            if membership.start_date == member.start_date and membership.end_date == member.end_date and len(member.memberships) != 0:
                raise dataError(f'member {member.id} has same extent as membership {membership.id} but has multiple memberships')

            # if membership extent is same as member, delete the member record
            if membership.start_date == member.start_date and membership.end_date == member.end_date:
                db.session.delete(member)
            
            # if membership extent starts member dates, change start of member to beyond the membership dates
            elif membership.start_date == member.start_date:
                member.start_date = membership.end_date + timedelta(1)
            
            # if membership extent finishes member dates, change end of member to before the membership dates
            elif membership.end_date == member.end_date:
                member.end_date = membership.start_date - timedelta(1)
            
            # otherwise membership extent must be in the middle, so create a new member record and update memberships to point to it
            else:
                # create new member record by copying data in member
                cols = [k for k in Member.__table__.columns.keys() if k != 'id']
                memberdata = {c: getattr(member, c) for c in cols}
                newmember = Member(**memberdata)
                db.session.add(newmember)
                member.end_date = membership.start_date - timedelta(1)
                newmember.start_date = membership.end_date + timedelta(1)

                # copy memberships as we'll be changing the list during the loop
                thesememberships = member.memberships[:]
                for mship in thesememberships:
                    if mship.start_date >= newmember.start_date and mship.end_date <= newmember.end_date:
                        mship.member = newmember
                
                # for completeness, update member record's hometown, email from latest membership record
                thesememberships = member.memberships[:]
                thesememberships.sort(key=lambda m: m.start_date)
                lastmship = thesememberships[-1]
                member.hometown = lastmship.hometown
                member.email = lastmship.email


        # use inherited class to delete the Membership instance
        return super().deleterow(thisid)

def memberships_pretablehtml():
    pretablehtml = div()
    with pretablehtml:
        # hide / show hidden rows
        with filtercontainerdiv(style='margin-bottom: 4px;'):
            cachetime = TableUpdateTime.query.filter_by(interest=localinterest(), tablename='member').one().lastchecked
            span(f'(last update time {cachet.dt2asc(cachetime)})')
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
                        'remove',
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
                        'scrollY': '55vh',
                        'lengthMenu': [ [10, 25, 50, 100, -1], [10, 25, 50, 100, 'All'] ],
                        'order': [
                            ['family_name:name', 'asc'],
                            ['given_name:name', 'asc'],
                            ['end_date:name', 'asc'],
                        ]
                    },
                    )
memberships_view.register()

##########################################################################################
# facebookaliases endpoint
###########################################################################################

facebookalias_dbattrs = 'id,interest_id,member,facebookalias'.split(',')
facebookalias_formfields = 'rowid,interest_id,member,facebookalias'.split(',')
facebookalias_dbmapping = dict(zip(facebookalias_dbattrs, facebookalias_formfields))
facebookalias_formmapping = dict(zip(facebookalias_formfields, facebookalias_dbattrs))

class MemberAgePicker(DteDbOptionsPickerBase):
    def __init__(self):
        super().__init__(
            labelfield='member',
            searchbox=True
        )

    def get_memberage(self, member):
        return f'{member.family_name}, {member.given_name} ({member.dob})'
    
    def get(self, dbrow_or_id):
        memberalias = self.get_dbrow(dbrow_or_id)
        memberage = self.get_memberage(memberalias.member)
        
        item = {'member': memberage, 'id': memberalias.member.id}
        return item

    def set(self, formrow):
        member = Member.query.filter_by(id=formrow['member']['id']).one()
        return member
    
    def options(self):
        members = Member.query.filter_by(interest=localinterest()).filter(
            Member.start_date<=date.today(), Member.end_date>=date.today()).all()
        members.sort(key=lambda m: self.get_memberage(m).lower())
        options = [{'label': self.get_memberage(m), 'value': m.id} for m in members]
        return options

    def col_options(self):
        col = {}
        col['type'] = 'select2'
        col['onFocus'] = 'focus'
        col['opts'] = {'minimumResultsForSearch': 0 if self.searchbox else 'Infinity'}
        return col

facebookalias_view = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = MemberAlias,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
                    pagename = 'Facebook Aliases',
                    endpoint = 'admin.facebookaliases',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/facebookaliases',
                    dbmapping = facebookalias_dbmapping, 
                    formmapping = facebookalias_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'member', 'name': 'member', 'label': 'Member',
                         'className': 'field_req',
                         '_treatment': {'relationship': { 'optionspicker': MemberAgePicker() } }
                         },
                        {'data': 'facebookalias', 'name': 'facebookalias', 'label': 'Alias',
                         'className': 'field_req',
                         # TODO: is this unique in the table or within an interest? Needs to be within an interest
                         '_unique': True,
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = ['create', 'editRefresh', 'remove', 'csv'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
facebookalias_view.register()

