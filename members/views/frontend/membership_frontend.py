'''
membership_frontend - views handling membership data
===========================================================================
'''

# standard
from datetime import datetime, timedelta
from traceback import format_exc
import time
from os.path import join, getmtime
from platform import system

# pypi
from flask import json, request, jsonify, current_app, g, render_template
from flask.views import MethodView
from loutilities.timeu import epoch2dt, age, asctime
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.user.model import Interest
from loutilities.filters import filtercontainerdiv, filterdiv
from dominate.tags import div, button, input_, span, i

class parameterError(): pass

# homegrown
from ..admin.viewhelpers import localinterest
from ...model import db, LocalInterest
from ...model import Member, TableUpdateTime, MemberDates
from . import bp

ymd = asctime('%Y-%m-%d')
mdy = asctime('%m/%d/%Y')

# https://stackoverflow.com/questions/49674902/datetime-object-without-leading-zero
if system() != 'Windows':
    cachet = asctime('%-m/%-d/%Y %-I:%M %p')
else:
    cachet = asctime('%#m/%#d/%Y %#I:%M %p')

def _getdivision(member):
    '''
    gets division as of Jan 1 

    :param member: Member record
    :rtype: division text
    '''

    # use local time
    today = time.time()-time.timezone
    todaydt = epoch2dt(today)
    jan1 = datetime(todaydt.year, 1, 1)

    memberage = age(jan1, member.dob)

    # this must match grand prix configuration in membership database
    # TODO: add api to query this information from scoretility
    if memberage <= 13:
        div = '13 and under'
    elif memberage <= 29:
        div = '14-29'
    elif memberage <= 39:
        div = '30-39'
    elif memberage <= 49:
        div = '40-49'
    elif memberage <= 59:
        div = '50-59'
    elif memberage <= 69:
        div = '60-69'
    else:
        div = '70 and over'

    return div

##########################################################################################
# front end members endpoint
##########################################################################################

members_dbattrs = 'id,given_name,family_name,gender,hometown,memberdates.end_date,'.split(',')
members_formfields = 'rowId,given_name,family_name,gender,hometown,end_date'.split(',')
members_dbmapping = dict(zip(members_dbattrs, members_formfields))
members_formmapping = dict(zip(members_formfields, members_dbattrs))
members_formmapping['div'] = _getdivision
# see https://datatables.net/manual/data/orthogonal-data#API-interface (must include render option for the field)
members_formmapping['family_name'] = lambda m: {'display': m.family_name, 'sort': m.family_name.lower() }
# need to find correct end_date in list of end_dates, even tho we did a join #587
ondate_f = lambda: ymd.asc2dt(request.args.get('ondate', ymd.dt2asc(datetime.now()))).date()
members_formmapping['end_date'] = lambda m: mdy.dt2asc([md.end_date for md in m.memberdates if md.start_date <= ondate_f() and md.end_date >= ondate_f()][0])

class FrontendMembersView(DbCrudApiInterestsRolePermissions):
    # remove auth_required() decorator
    decorators = []

    def beforequery(self):
        '''
        add update query parameters based on ondate
        '''
        self.queryfilters = []
        super().beforequery()
        ondate = request.args.get('ondate', ymd.dt2asc(datetime.now()))
        ondatedt = ymd.asc2dt(ondate)
        self.queryfilters += [MemberDates.start_date <= ondatedt, MemberDates.end_date >= ondatedt]

    def open(self):
        query = (self.model.query
                 .outerjoin(MemberDates, MemberDates.member_id==Member.id)
                 .filter_by(**self.queryparams)
                 .filter(*self.queryfilters)
                )
        self.rows = iter(query.all())
        
    def permission(self):
        '''
        check for permission on data
        :rtype: boolean
        '''
        # g.interest initialized in <project>.create_app.pull_interest
        # g.interest contains slug, pull in interest db entry. If not found, no permission granted
        self.interest = Interest.query.filter_by(interest=g.interest).one_or_none()
        if not self.interest:
            return False

        return True
    
def frontendmembers_pretablehtml():
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

    return pretablehtml.render()

frontendmembers_view = FrontendMembersView(
    app=bp,
    db = db,
    local_interest_model = LocalInterest,
    pagename='registered members',
    endpoint='frontend.members',
    endpointvalues={'interest': '<interest>'},
    pretablehtml=frontendmembers_pretablehtml,
    model = Member,
    dbmapping = members_dbmapping,
    formmapping = members_formmapping,
    rule='<interest>/members',
    buttons=['csv'],
    dtoptions={
        'order': [[1,'asc']],
        'dom': '<"clear">lBfrtip',
    },
    serverside = False,
    idSrc='rowId',
    templateargs={
        'frontend_page': True, 
        'assets_js': 'frontend_js', 
        'assets_css': 'frontend_css'
    },
    clientcolumns=[
        {'data': 'given_name', 'name': 'given_name', 'label': 'First',
         'type': 'readonly'
         },
        # see https://datatables.net/manual/data/orthogonal-data#API-interface
        {'data': 'family_name', 'name': 'family_name', 'label': 'Last',
        'render': {'_': 'display', 'sort': 'sort'},
         'type': 'readonly'
         },
        {'data': 'div', 'name': 'div', 'label': 'Div (age Jan 1)',
         'type': 'readonly'
         },
        {'data': 'hometown', 'name': 'hometown', 'label': 'Hometown',
         'type': 'readonly',
         },
        {'data': 'end_date', 'name': 'end_date', 'label': 'End Date',
         'type': 'readonly',
         },
    ],
)
frontendmembers_view.register()

class MemberStatsApi(MethodView):
    
    def get(self):
        try:
            # get the club and cache
            memberstatsfile = join(current_app.config['APP_FILE_FOLDER'], g.interest, current_app.config['APP_STATS_FILENAME'])

            # get the summarized statistics, and time file was created
            with open(memberstatsfile, 'r') as stats:
                memberstats_str = stats.read()
            mtime = getmtime(memberstatsfile) + time.localtime().tm_gmtoff
            cachetime = cachet.epoch2asc(mtime)

            # convert json
            memberstats = json.loads(memberstats_str)

            # it's all good
            return jsonify(success=True, data=memberstats, cachetime=cachetime)
        
        except Exception as e:
            # er, not so good
            cause = format_exc()
            current_app.logger.error(format_exc())
            return jsonify(success=False, cause=cause)

bp.add_url_rule('/<interest>/_memberstats',view_func=MemberStatsApi.as_view('_memberstats'),methods=['GET'])

class MembershipStats(MethodView):

    def get(self):
        cachetime = cachet.dt2asc(TableUpdateTime.query.filter_by(interest=localinterest(), tablename='member').one().lastchecked)
        return render_template(
            'membership-stats.jinja2',
            pagename='membership stats',
            frontend_page=True, 
            assets_js='frontendmembers_js', 
            assets_css='frontend_css',
            cachetime=cachetime,
        )

bp.add_url_rule('/<interest>/membershipstats', view_func=MembershipStats.as_view('membershipstats'),methods=['GET'])
 