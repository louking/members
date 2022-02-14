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
from loutilities.transform import Transform
from sortedcontainers import SortedKeyList

# homegrown
from . import bp
from .viewhelpers import LocalUserPicker
from ...model import LocalUser, db
from ...model import LocalInterest, RacingTeamConfig, RacingTeamDateRange, RacingTeamApplication, RacingTeamMember, RacingTeamResult, RacingTeamVolunteer
from ...model import rt_config_openbehaviors, RT_CONFIG_OPEN_AUTO, monthname
from ...model import localinterest_query_params
from ...version import __docversion__

from loutilities.user.roles import ROLE_SUPER_ADMIN
from loutilities.user.roles import ROLE_RACINGTEAM_ADMIN, ROLE_RACINGTEAM_MEMBER
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

class ParameterError(Exception): pass

debug = False
isodate = asctime('%Y-%m-%d')
timestamp = asctime('%Y-%m-%d %H:%M')

racingteam_roles = [ROLE_SUPER_ADMIN, ROLE_RACINGTEAM_ADMIN]
adminguide = 'https://members.readthedocs.io/en/{docversion}/racingteam-admin-guide.html'.format(
    docversion=__docversion__)

##########################################################################################
# rt_members endpoint
###########################################################################################

rt_member_dbattrs = 'id,interest_id,localuser,gender,dateofbirth'.split(',')
rt_member_formfields = 'rowid,interest_id,localuser,gender,dateofbirth'.split(',')
rt_member_dbmapping = dict(zip(rt_member_dbattrs, rt_member_formfields))
rt_member_formmapping = dict(zip(rt_member_formfields, rt_member_dbattrs))
rt_member_dbmapping['dateofbirth'] = lambda formrow: isodate.asc2dt(formrow['dateofbirth']).date()
rt_member_formmapping['dateofbirth'] = lambda dbrow: isodate.dt2asc(dbrow.dateofbirth)

class RacingTeamMembersValidator(Schema):
    dateofbirth = DateConverter(month_style='iso')
    gender = OneOf(['M', 'F'])

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
        {'data': 'localuser', 'name': 'localuser', 'label': 'Member',
         'className': 'field_req',
         '_treatment': {
             'relationship': 
                 {'optionspicker': LocalUserPicker(
                     active=True,
                     rolenames=[ROLE_RACINGTEAM_MEMBER],
                     **{'fieldmodel': LocalUser, 'labelfield': 'name',
                     'formfield': 'localuser', 'dbfield': 'localuser',
                     'searchbox': True,
                     'uselist': False}
                 )
                 }
         }
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
    edoptions={
        # https://datatables.net/forums/discussion/comment/181763/#Comment_181763
        'formOptions': {
            'main': {
                'focus': None
            }
    },    
        
    }
)
rt_members_view.register()

##########################################################################################
# rt_inforesults endpoint
###########################################################################################

rt_inforesult_dbattrs = 'id,interest_id,info.logtime,info.member,eventdate,age,eventname,distance,units,time,agegrade,awards'.split(',')
rt_inforesult_formfields = 'rowid,interest_id,logtime,name,eventdate,age,eventname,distance,units,time,agegrade,awards'.split(',')
rt_inforesult_dbmapping = dict(zip(rt_inforesult_dbattrs, rt_inforesult_formfields))
rt_inforesult_formmapping = dict(zip(rt_inforesult_formfields, rt_inforesult_dbattrs))
rt_inforesult_formmapping['name'] = lambda dbrow: dbrow.info.member.localuser.name
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
        {'data': 'age', 'name': 'age', 'label': 'Age',
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
rt_infovol_formmapping['name'] = lambda dbrow: dbrow.info.member.localuser.name
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
# rt_applnresults endpoint
###########################################################################################

rt_applnresult_dbattrs = 'id,interest_id,application.logtime,application.name,application.email,application.comments,eventdate,eventname,location,distance,units,time,agegrade,age,url'.split(',')
rt_applnresult_formfields = 'rowid,interest_id,logtime,name,email,comments,eventdate,eventname,location,distance,units,time,agegrade,age,url'.split(',')
rt_applnresult_dbmapping = dict(zip(rt_applnresult_dbattrs, rt_applnresult_formfields))
rt_applnresult_formmapping = dict(zip(rt_applnresult_formfields, rt_applnresult_dbattrs))

class RacingTeamApplnResultsValidator(Schema):
    name = NotEmpty()
    eventdate = DateConverter(month_style='iso')
    eventname = NotEmpty()
    distance = Number(min=0, max=200)
    units = OneOf(['miles', 'km'])
    time = TimeOptHoursConverter()
    agegrade = Number(min=0, max=100)

class RacingTeamApplnResultsView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        super().beforequery()
        self.queryfilters.append(RacingTeamResult.application != None)

rt_applnresults_view = RacingTeamApplnResultsView(
    roles_accepted=racingteam_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=RacingTeamResult,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Racing Team Application Results',
    endpoint='admin.rt_applnresults',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/rt_applnresults',
    dbmapping=rt_applnresult_dbmapping,
    formmapping=rt_applnresult_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'logtime', 'name': 'logtime', 'label': 'Timestamp',
         'render': { 'eval': '$.fn.dataTable.render.moment("ddd, DD MMM YYYY HH:mm:ss [GMT]", "YYYY-MM-DD HH:mm")' }
         },
        {'data': 'name', 'name': 'name', 'label': 'Name',
         },
        {'data': 'email', 'name': 'email', 'label': 'Email',
         },
        {'data': 'eventdate', 'name': 'eventdate', 'label': 'Event Date',
         'render': { 'eval': '$.fn.dataTable.render.moment("ddd, DD MMM YYYY HH:mm:ss [GMT]", "YYYY-MM-DD")' }
         },
        {'data': 'age', 'name': 'age', 'label': 'Age',
         },
        {'data': 'eventname', 'name': 'eventname', 'label': 'Event Name',
         },
        {'data': 'location', 'name': 'location', 'label': 'Location',
         },
        {'data': 'distance', 'name': 'distance', 'label': 'Dist',
         },
        {'data': 'units', 'name': 'units', 'label': 'Units',
         },
        {'data': 'agegrade', 'name': 'agegrade', 'label': 'Age Grade',
         },
        {'data': 'url', 'name': 'url', 'label': 'Results Link',
         },
      ],
    serverside=True,
    idSrc='rowid',
    # readonly
    buttons=['csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
        'order': [
            ['logtime:name', 'desc'],
            ['eventdate:name', 'desc'],
        ],
    },
)
rt_applnresults_view.register()

##########################################################################################
# rt_applns endpoint
###########################################################################################

rt_appln_dbattrs = 'id,interest_id,logtime,name,gender,dateofbirth,email,type,comments'.split(',')
rt_appln_formfields = 'rowid,interest_id,logtime,name,gender,dateofbirth,email,type,comments'.split(',')
rt_appln_dbmapping = dict(zip(rt_appln_dbattrs, rt_appln_formfields))
rt_appln_formmapping = dict(zip(rt_appln_formfields, rt_appln_dbattrs))
rt_appln_formmapping['logtime'] = lambda dbrow: timestamp.dt2asc(dbrow.logtime)
rt_appln_formmapping['dateofbirth'] = lambda dbrow: isodate.dt2asc(dbrow.dateofbirth)

result_dbattrs = 'eventdate,eventname,location,url,distance,units,time,age,agegrade'.split(',')
db2client = {}
for ndx in [1, 2]:
    result_clientfields = f'race{ndx}_eventdate,race{ndx}_eventname,race{ndx}_location,race{ndx}_resultslink,race{ndx}_distance,race{ndx}_units,' \
        f'race{ndx}_time,race{ndx}_age,race{ndx}_agegrade'.split(',')
    clientmapping = dict(zip(result_clientfields, result_dbattrs))
    clientmapping[f'race{ndx}_eventdate'] = lambda dbrow: isodate.dt2asc(dbrow.eventdate) if dbrow.eventdate else None
    db2client[ndx] = Transform(clientmapping, targetattr=False)

class RacingTeamApplnsView(DbCrudApiInterestsRolePermissions):
    def _result2client(self, result, raceid):
        client = {}
        db2client[raceid].transform(result, client)
        return client

    def nexttablerow(self):
        dbrec = next(self.rows)
        clientrec = self.dte.get_response_data(dbrec)
        results = SortedKeyList(dbrec.rt_results, key=lambda a: a.eventdate)
        results = list(results)
        # may be one or more empty results
        while len(results) < 2:
            results.append(RacingTeamResult())
        for ndx in range(2):
            clientrec.update(self._result2client(results[ndx], ndx+1))
        return clientrec

rt_applns_view = RacingTeamApplnsView(
    roles_accepted=racingteam_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=RacingTeamApplication,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Racing Team Applications',
    endpoint='admin.rt_applns',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/rt_applns',
    dbmapping=rt_appln_dbmapping,
    formmapping=rt_appln_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'logtime', 'name': 'logtime', 'label': 'Timestamp',
         },
        {'data': 'name', 'name': 'name', 'label': 'Name',
         },
        {'data': 'gender', 'name': 'gender', 'label': 'Gen',
         },
        {'data': 'dateofbirth', 'name': 'dateofbirth', 'label': 'DOB',
         },
        {'data': 'email', 'name': 'email', 'label': 'Email',
         },
        {'data': 'type', 'name': 'type', 'label': 'Type',
         },
        {'data': 'comments', 'name': 'comments', 'label': 'Comments',
         'render': {'eval': '$.fn.dataTable.render.ellipsis( 20 )'},
         },
        {'data': 'race1_eventname', 'name': 'race1_eventname', 'label': 'Race 1',
         },
        {'data': 'race1_eventdate', 'name': 'race1_eventdate', 'label': 'R1 Date',
         },
        {'data': 'race1_agegrade', 'name': 'race1_agegrade', 'label': 'R1 AG',
         },
        {'data': 'race2_eventname', 'name': 'race2_eventname', 'label': 'Race 2',
         },
        {'data': 'race2_eventdate', 'name': 'race2_eventdate', 'label': 'R2 Date',
         },
        {'data': 'race2_agegrade', 'name': 'race2_agegrade', 'label': 'R2 AG',
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
rt_applns_view.register()

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

