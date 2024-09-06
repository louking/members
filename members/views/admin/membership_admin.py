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
from loutilities.transform import Transform
from sqlalchemy import func, select

# homegrown
from . import bp
from ...model import db, LocalInterest
from ...model import Member, Membership, TableUpdateTime, MemberAlias, MemberDates
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

module_roles = [ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN]

##########################################################################################
# clubmembers endpoint
##########################################################################################

clubmembers_dbattrs = 'id,svc_member_id,given_name,family_name,gender,dob,email,hometown,memberalias.facebookalias,memberdates.start_date,memberdates.end_date,'.split(',')
clubmembers_formfields = 'rowid,svc_member_id,given_name,family_name,gender,dob,email,hometown,facebookalias,start_date,end_date'.split(',')
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
        self.queryfilters += [MemberDates.start_date <= ondatedt, MemberDates.end_date >= ondatedt]

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
                    roles_accepted = module_roles,
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
                        {'data': 'facebookalias', 'name': 'facebookalias', 'label': 'Facebook',
                         'type': 'readonly',
                         '_ColumnDT_args' :
                             {'sqla_expr': MemberAlias.facebookalias, 'search_method': 'yadcf_range_date'},
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
                             {'sqla_expr': func.date_format(MemberDates.start_date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'},
                         },
                        {'data': 'end_date', 'name': 'end_date', 'label': 'End',
                         'type': 'readonly',
                         '_ColumnDT_args' :
                             {'sqla_expr': func.date_format(MemberDates.end_date, '%Y-%m-%d'), 'search_method': 'yadcf_range_date'},
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

        # update memberdates record(s) by recalculating contiguous membership dates
        if membership.memberdates:
            memberdates = membership.memberdates

            # this membership will be deleted, so remove memberdates association 
            # NOTE: this also removes membership from memberdates.memberships
            membership.memberdates = None

            # if membership is not wholly contained within memberdates, there was some data error, probably in membership_cli
            if membership.start_date < memberdates.start_date or membership.end_date > memberdates.end_date:
                raise dataError(f'membership {membership.id} references memberdates {memberdates.id} but extent of membership goes beyond that of memberdates')

            # if membership extent is same as memberdates, this membership must have been the only membership referenced by memberdates
            # NOTE: this membership was removed from memberdates.memberships above, so checking against 0
            if membership.start_date == memberdates.start_date and membership.end_date == memberdates.end_date and len(memberdates.memberships) != 0:
                raise dataError(f'memberdates {memberdates.id} has same extent as membership {membership.id} but has multiple memberships')

            # if membership extent is same as memberdates, delete the memberdates record
            if membership.start_date == memberdates.start_date and membership.end_date == memberdates.end_date:
                db.session.delete(memberdates)
            
            # if membership extent starts memberdates dates, change start of memberdates to beyond the membership dates
            elif membership.start_date == memberdates.start_date:
                memberdates.start_date = membership.end_date + timedelta(1)
            
            # if membership extent finishes memberdates dates, change end of memberdates to before the membership dates
            elif membership.end_date == memberdates.end_date:
                memberdates.end_date = membership.start_date - timedelta(1)
            
            # otherwise membership extent must be in the middle, so create a new memberdates record and update memberships to point to it
            else:
                # create new memberdates record by copying data in memberdates
                cols = [k for k in MemberDates.__table__.columns.keys() if k != 'id']
                memberdatesdata = {c: getattr(memberdates, c) for c in cols}
                newmemberdates = MemberDates(**memberdatesdata)
                db.session.add(newmemberdates)
                memberdates.end_date = membership.start_date - timedelta(1)
                newmemberdates.start_date = membership.end_date + timedelta(1)

                # copy memberships as we'll be changing the list during the loop
                thesememberships = memberdates.memberships[:]
                for mship in thesememberships:
                    if mship.start_date >= newmemberdates.start_date and mship.end_date <= newmemberdates.end_date:
                        mship.memberdates = newmemberdates

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
                    roles_accepted = module_roles,
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

def get_memberdob(member):
    middlename = f'{member.middle_name} ' if member.middle_name else ''
    return f'{member.family_name}, {member.given_name} {middlename}({member.dob})'
    

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

    def get(self, dbrow_or_id):
        memberalias = self.get_dbrow(dbrow_or_id)
        memberage = get_memberdob(memberalias.member)
        
        item = {'member': memberage, 'id': memberalias.member.id}
        return item

    def set(self, formrow):
        member = Member.query.filter_by(id=formrow['member']['id']).one()
        return member
    
    def options(self):
        stmt = (
            select(Member.id, Member.family_name, Member.middle_name, Member.given_name, Member.dob)
        )
        all_members = db.session.execute(stmt).all()
        if all_members:
            all_members.sort(key=lambda m: get_memberdob(m).lower())
            members = [all_members[0]]
            for i in range(1, len(all_members)):
                # skip duplicates
                if get_memberdob(all_members[i-1]) == get_memberdob(all_members[i]):
                    continue
                members.append(all_members[i])
        options = [{'label': get_memberdob(m), 'value': m.id} for m in members]
        return options

    def col_options(self):
        col = {}
        col['type'] = 'select2'
        col['onFocus'] = 'focus'
        col['opts'] = {'minimumResultsForSearch': 0 if self.searchbox else 'Infinity'}
        return col

facebookalias_view = DbCrudApiInterestsRolePermissions(
                    roles_accepted = module_roles,
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

##########################################################################################
# expired_members endpoint
##########################################################################################

expired_members_dbattrs = 'id,svc_member_id,given_name,family_name,gender,dob,email,hometown,end_date,facebookalias'.split(',')
expired_members_formfields = 'rowid,svc_member_id,given_name,family_name,gender,dob,email,hometown,end_date,facebookalias'.split(',')
expired_members_dbmapping = dict(zip(expired_members_dbattrs, expired_members_formfields))
expired_members_formmapping = dict(zip(expired_members_formfields, expired_members_dbattrs))

expired_members_formmapping['dob'] = lambda m: ymd.dt2asc(m.dob)
expired_members_formmapping['end_date'] = lambda m: ymd.dt2asc(m.end_date)

class ExpiredMember():
    '''
    allows creation of "ExpiredMember" object to simulate database behavior
    '''
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

member2expired_member = Transform(
    {
        'id': 'id',
        'family_name': 'family_name',
        'given_name': 'given_name',
        'gender': 'gender',
        'dob': 'dob',
        'end_date': 'end_date',
        'hometown': 'hometown',
        'svc_member_id': 'svc_member_id',
        'email': 'email',
        'facebookalias': 'facebookalias',
    }
)
class ExpiredMembers(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        '''
        add update query parameters based on sincedate
        '''
        self.queryfilters = []
        super().beforequery()
        self.sincedate = request.args.get('ondate', None)
        if self.sincedate:
            self.sincedated = ymd.asc2dt(self.sincedate).date()
        else:
            self.sincedated = datetime.today().date()

    def open(self):
        locinterest = localinterest()
        # memberships = (
        #     Member.query
        #     .outerjoin(MemberAlias, Member.id==MemberAlias.member_id)
        #     .join(Membership, Member.id==Membership.member_id)
        #     .filter_by(interest=locinterest)
        #     .filter(Membership.end_date>=self.sincedated)
        # ).all()
        stmt = (
            select(
                Membership.id, 
                Member.svc_member_id, 
                Member.family_name, 
                Member.given_name, 
                Member.middle_name, 
                Member.gender, 
                Member.dob, 
                Member.hometown, 
                Member.email,
                MemberAlias.facebookalias,
                Membership.member_id,
                Membership.end_date
            )
            .outerjoin(MemberAlias, Member.id==MemberAlias.member_id)
            .join(Membership, Member.id==Membership.member_id)
            .order_by(Membership.member_id, Membership.end_date)
            .filter_by(interest=locinterest)
            .filter(Membership.end_date>=self.sincedated)            
        )
        memberships = db.session.execute(stmt).all()
        membershipsi = iter(memberships)
        
        expired_members_lookup = {}
        try:
            membership = next(membershipsi)
            while True:
                # top of loop is new member
                # create/add expired_member
                expired_member = ExpiredMember()
                member2expired_member.transform(membership, expired_member)
                expired_member.end_date = membership.end_date

                # check all the memberships for this member
                while True:
                    if membership.end_date > expired_member.end_date:
                        expired_member.end_date = membership.end_date
                    
                    # only use member record with latest membership
                    member_dob = get_memberdob(membership)
                    if member_dob not in expired_members_lookup or expired_member.end_date > expired_members_lookup[member_dob].end_date:
                        expired_members_lookup[member_dob] = expired_member
                    
                    last_member_id = membership.member_id
                    membership = next(membershipsi)
                    if membership.member_id != last_member_id: break
                
        except StopIteration:
            pass
        
        # collect interesting expired members for display
        expired_members = []
        for member_dob in expired_members_lookup:
            expired_member = expired_members_lookup[member_dob]
            # save members whose end_dates are interesting
            if expired_member.end_date >= self.sincedated and expired_member.end_date < date.today():
                expired_members.append(expired_member)

        self.rows = iter(expired_members)
        

def expired_members_filters():
    pretablehtml = div()
    with pretablehtml:
        # hide / show hidden rows
        with filtercontainerdiv(style='margin-bottom: 4px;'):
            datefilter = filterdiv('fsrcmembers-external-filter-since', 'Since')
            with datefilter:
                with span(id='spinner', style='display:none;'):
                    i(cls='fas fa-spinner fa-spin')
                input_(type='text', id='effective-date', name='effective-date' )
    return pretablehtml.render()

expired_members_view = ExpiredMembers(
                    roles_accepted = module_roles,
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Member,
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
                    pretablehtml = expired_members_filters,
                    pagename = 'Expired Members',
                    endpoint = 'admin.expired_members',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/expired_members',
                    dbmapping = expired_members_dbmapping,
                    formmapping = expired_members_formmapping,
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
                         },
                        {'data': 'facebookalias', 'name': 'facebookalias', 'label': 'Facebook',
                         'type': 'readonly',
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
                        {'data': 'end_date', 'name': 'end_date', 'label': 'Expired',
                         'type': 'readonly',
                         },
                    ],
                    serverside = False,
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
expired_members_view.register()
