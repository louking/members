'''
racingteam_admin - racingteam administrative handling
===========================================
'''
# standard

# pypi
from datetime import datetime, timedelta
from formencode.schema import Schema
from formencode.validators import Email, DateConverter, Number, OneOf, StringBool, NotEmpty
from loutilities.tables import DteFormValidate, TimeOptHoursConverter
from loutilities.timeu import asctime

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, RacingTeamConfig, RacingTeamDateRange, RacingTeamApplication, RacingTeamMember, RacingTeamResult, RacingTeamVolunteer
from ...model import rt_config_openbehaviors, RT_CONFIG_OPEN_AUTO, monthname
from ...model import localinterest_query_params
from ...version import __docversion__

from loutilities.user.roles import ROLE_SUPER_ADMIN
from loutilities.user.roles import ROLE_RACINGTEAM_ADMIN, ROLE_LEADERSHIP_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

class ParameterError(Exception): pass

debug = False
isodate = asctime('%Y-%m-%d')
timestamp = asctime('%Y-%m-%d %H:%M')

racingteam_roles = [ROLE_SUPER_ADMIN, ROLE_RACINGTEAM_ADMIN, ROLE_LEADERSHIP_ADMIN]
adminguide = 'https://members.readthedocs.io/en/{docversion}/racingteam-admin-guide.html'.format(
    docversion=__docversion__)

##########################################################################################
# rt_members endpoint
###########################################################################################

rt_member_dbattrs = 'id,interest_id,name,gender,dateofbirth,email,active'.split(',')
rt_member_formfields = 'rowid,interest_id,name,gender,dateofbirth,email,active'.split(',')
rt_member_dbmapping = dict(zip(rt_member_dbattrs, rt_member_formfields))
rt_member_formmapping = dict(zip(rt_member_formfields, rt_member_dbattrs))
rt_member_dbmapping['dateofbirth'] = lambda formrow: isodate.asc2dt(formrow['dateofbirth']).date()
rt_member_formmapping['dateofbirth'] = lambda dbrow: isodate.dt2asc(dbrow.dateofbirth)

class RacingTeamMembersValidator(Schema):
    name = NotEmpty()
    dateofbirth = DateConverter(month_style='iso')
    gender = OneOf(['M', 'F'])
    email = Email()
    active = StringBool()
    
rt_members_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=racingteam_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=RacingTeamMember,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Racing Team Members',
    endpoint='admin.rt_members',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/rt_members',
    dbmapping=rt_member_dbmapping,
    formmapping=rt_member_formmapping,
    checkrequired=True,
    formencode_validator=RacingTeamMembersValidator(allow_extra_fields=True),
    clientcolumns=[
        {'data': 'name', 'name': 'name', 'label': 'Name',
         'className': 'field_req',
         },
        {'data': 'gender', 'name': 'gender', 'label': 'Gender',
         'className': 'field_req',
         'type': 'select2',
         'options': ['M', 'F'],
         },
        {'data': 'dateofbirth', 'name': 'dateofbirth', 'label': 'DOB',
         'className': 'field_req',
         'type': 'datetime',
         'ed': {
             'opts': {
                 'maxDate': {'eval': f'new Date(\'{isodate.dt2asc(datetime.now())}\')'},
                 # 90 years old seems sufficient
                 'minDate': {'eval': f'new Date(\'{isodate.dt2asc(datetime(datetime.now().year-90, 1, 1))}\')'},
             }
         }
         },
        {'data': 'email', 'name': 'email', 'label': 'Email',
         'className': 'field_req',
         },
        {'data': 'active', 'name': 'active', 'label': 'Active',
            '_treatment': {'boolean': {'formfield': 'active', 'dbfield': 'active'}},
            'ed': {'def': 'yes'},
            },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'remove', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
rt_members_view.register()

##########################################################################################
# rt_inforesults endpoint
###########################################################################################

rt_inforesult_dbattrs = 'id,interest_id,info.logtime,info.member,eventdate,eventname,distance,units,time,agegrade,awards'.split(',')
rt_inforesult_formfields = 'rowid,interest_id,logtime,name,eventdate,eventname,distance,units,time,agegrade,awards'.split(',')
rt_inforesult_dbmapping = dict(zip(rt_inforesult_dbattrs, rt_inforesult_formfields))
rt_inforesult_formmapping = dict(zip(rt_inforesult_formfields, rt_inforesult_dbattrs))
rt_inforesult_formmapping['name'] = lambda dbrow: dbrow.info.member.name
rt_inforesult_formmapping['eventdate'] = lambda dbrow: isodate.dt2asc(dbrow.eventdate)
rt_inforesult_formmapping['logtime'] = lambda dbrow: timestamp.dt2asc(dbrow.info.logtime)

class RacingTeamInfoResultsValidator(Schema):
    name = NotEmpty()
    eventdate = DateConverter(month_style='iso')
    eventname = NotEmpty()
    distance = Number(min=0, max=200)
    units = OneOf(['miles', 'km'])
    time = TimeOptHoursConverter()
    agegrade = Number(min=0, max=100)
    
class RacingTeamInfoResultsView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        super().beforequery()
        self.queryfilters.append(RacingTeamResult.info != None)
    
    def validate_form(self, action, formdata):
        val = DteFormValidate(RacingTeamInfoResultsValidator(allow_extra_fields=True))
        results = val.validate(formdata)
        self.formdata = results['python']
        return results['results']

rt_inforesults_view = RacingTeamInfoResultsView(
    roles_accepted=racingteam_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=RacingTeamResult,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Racing Team Info Results',
    endpoint='admin.rt_inforesults',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/rt_inforesults',
    dbmapping=rt_inforesult_dbmapping,
    formmapping=rt_inforesult_formmapping,
    checkrequired=True,
    validate=lambda action, formdata: rt_inforesults_view.validate_form(action, formdata),
    clientcolumns=[
        {'data': 'logtime', 'name': 'logtime', 'label': 'Timestamp',
         },
        {'data': 'name', 'name': 'name', 'label': 'Name',
         },
        {'data': 'eventdate', 'name': 'eventdate', 'label': 'Event Date',
         },
        {'data': 'eventname', 'name': 'eventname', 'label': 'Event Name',
         },
        {'data': 'distance', 'name': 'distance', 'label': 'Dist',
         },
        {'data': 'units', 'name': 'units', 'label': 'Units',
         },
        {'data': 'agegrade', 'name': 'agegrade', 'label': 'Age Grade',
         },
        {'data': 'awards', 'name': 'awards', 'label': 'Awards',
         },
      ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    # readonly
    buttons=['csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [['logtime:name', 'desc']],
    },
)
rt_inforesults_view.register()

##########################################################################################
# rt_infovols endpoint
###########################################################################################

rt_infovol_dbattrs = 'id,interest_id,info.logtime,info.member,eventdate,eventname,hours,comment'.split(',')
rt_infovol_formfields = 'rowid,interest_id,logtime,name,eventdate,eventname,hours,comment'.split(',')
rt_infovol_dbmapping = dict(zip(rt_infovol_dbattrs, rt_infovol_formfields))
rt_infovol_formmapping = dict(zip(rt_infovol_formfields, rt_infovol_dbattrs))
rt_infovol_formmapping['name'] = lambda dbrow: dbrow.info.member.name
rt_infovol_formmapping['eventdate'] = lambda dbrow: isodate.dt2asc(dbrow.eventdate)
rt_infovol_formmapping['logtime'] = lambda dbrow: timestamp.dt2asc(dbrow.info.logtime)

class RacingTeamInfoVolValidator(Schema):
    name = NotEmpty()
    eventdate = DateConverter(month_style='iso')
    eventname = NotEmpty()
    distance = Number(min=0, max=200)
    units = OneOf(['miles', 'km'])
    time = TimeOptHoursConverter()
    agegrade = Number(min=0, max=100)
    
class RacingTeamInfoVolView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        super().beforequery()
        self.queryfilters.append(RacingTeamResult.info != None)
    
    def validate_form(self, action, formdata):
        val = DteFormValidate(RacingTeamInfoVolValidator(allow_extra_fields=True))
        results = val.validate(formdata)
        self.formdata = results['python']
        return results['results']

rt_infovols_view = RacingTeamInfoVolView(
    roles_accepted=racingteam_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=RacingTeamVolunteer,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Racing Team Info Volunteer',
    endpoint='admin.rt_infovol',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/rt_infovol',
    dbmapping=rt_infovol_dbmapping,
    formmapping=rt_infovol_formmapping,
    checkrequired=True,
    validate=lambda action, formdata: rt_infovols_view.validate_form(action, formdata),
    clientcolumns=[
        {'data': 'logtime', 'name': 'logtime', 'label': 'Timestamp',
         },
        {'data': 'name', 'name': 'name', 'label': 'Name',
         },
        {'data': 'eventdate', 'name': 'eventdate', 'label': 'Event Date',
         },
        {'data': 'eventname', 'name': 'eventname', 'label': 'Event Name',
         },
        {'data': 'hours', 'name': 'hours', 'label': 'Hours',
         },
        {'data': 'comment', 'name': 'comment', 'label': 'Comment',
         },
      ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    # readonly
    buttons=['csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [['logtime:name', 'desc']],
    },
)
rt_infovols_view.register()

##########################################################################################
# rt_configs endpoint
###########################################################################################

rt_config_dbattrs = 'id,interest_id,openbehavior,fromemail,infoccemail,applnccemail,dateranges'.split(',')
rt_config_formfields = 'rowid,interest_id,openbehavior,fromemail,infoccemail,applnccemail,dateranges'.split(',')
rt_config_dbmapping = dict(zip(rt_config_dbattrs, rt_config_formfields))
rt_config_formmapping = dict(zip(rt_config_formfields, rt_config_dbattrs))

rt_configs_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=racingteam_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=RacingTeamConfig,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Racing Team Config',
    endpoint='admin.rt_config',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/rt_config',
    dbmapping=rt_config_dbmapping,
    formmapping=rt_config_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'openbehavior', 'name': 'openbehavior', 'label': 'Open Behavior',
         'className': 'field_req',
         'type': 'select2',
         'options': rt_config_openbehaviors,
         'ed': {
             'def': RT_CONFIG_OPEN_AUTO,
         }
         },
        {'data': 'dateranges', 'name': 'dateranges', 'label': 'Date Ranges',
         'fieldInfo': 'date ranges to open applications for *auto* behavior',
         '_treatment': {
             'relationship': {'fieldmodel': RacingTeamDateRange, 'labelfield': 'rangename', 'formfield': 'dateranges',
                              'dbfield': 'dateranges', 'uselist': True,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'fromemail', 'name': 'fromemail', 'label': 'From Email',
         'className': 'field_req',
         },
        {'data': 'infoccemail', 'name': 'infoccemail', 'label': 'Info Form CC Email',
         'className': 'field_req',
         },
        {'data': 'applnccemail', 'name': 'applnccemail', 'label': 'Application Form CC Email',
         'className': 'field_req',
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'remove', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
rt_configs_view.register()

##########################################################################################
# rt_daterange endpoint
###########################################################################################

rt_daterange_dbattrs = 'id,interest_id,rangename,start_month,start_date,end_month,end_date'.split(',')
rt_daterange_formfields = 'rowid,interest_id,rangename,start_month,start_date,end_month,end_date'.split(',')
rt_daterange_dbmapping = dict(zip(rt_daterange_dbattrs, rt_daterange_formfields))
rt_daterange_formmapping = dict(zip(rt_daterange_formfields, rt_daterange_dbattrs))

rt_daterange_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=racingteam_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=RacingTeamDateRange,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Racing Team Date Range',
    endpoint='admin.rt_daterange',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/rt_daterange',
    dbmapping=rt_daterange_dbmapping,
    formmapping=rt_daterange_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'rangename', 'name': 'rangename', 'label': 'Range Name',
         'className': 'field_req',
         },
        {'data': 'start_month', 'name': 'start_month', 'label': 'Start Month',
         'className': 'field_req',
         'type': 'select2',
         'options': monthname,
         },
        {'data': 'start_date', 'name': 'start_date', 'label': 'Start Date of Month',
         'className': 'field_req',
         },
        {'data': 'end_month', 'name': 'end_month', 'label': 'End Month',
         'className': 'field_req',
         'type': 'select2',
         'options': monthname,
         },
        {'data': 'end_date', 'name': 'end_date', 'label': 'End Date of Month',
         'className': 'field_req',
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'remove', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
rt_daterange_view.register()

