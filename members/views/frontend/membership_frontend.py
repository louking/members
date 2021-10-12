'''
membership_frontend - views handling membership data
===========================================================================
'''

# standard
from collections import OrderedDict
from datetime import datetime, timedelta
from traceback import format_exc
import time
from os.path import getmtime
from csv import DictWriter

# pypi
from flask import json, request, jsonify, current_app
from flask.views import MethodView
from loutilities.timeu import epoch2dt, age, asctime
from loutilities.transform import Transform
from loutilities.csvwt import wlist
from loutilities.tables import CrudApi
from loutilities.filters import filtercontainerdiv, filterdiv
from running.runsignup import RunSignUp
from dominate.tags import div, button, input, span, i

# homegrown
from ..admin.viewhelpers import localinterest
from . import bp

ymd = asctime('%Y-%m-%d')
mdy = asctime('%m/%d/%Y')
cachet = asctime('%-m/%-d/%Y %-I:%M %p')

def _getdivision(member):
    '''
    gets division as of Jan 1 from RunSignUp record

    :param member: RunSignUp record
    :rtype: division text
    '''

    # use local time
    today = time.time()-time.timezone
    todaydt = epoch2dt(today)
    jan1 = datetime(todaydt.year, 1, 1)

    memberage = age(jan1, ymd.asc2dt(member['user']['dob']))

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

class FrontendMembersView(CrudApi):
    def open(self):
        linterest = localinterest()
        club_id = linterest.service_id
    
        # we only handle runsignup now
        if linterest.club_service == 'runsignup' and club_id:
            # note ondate, defaults to today
            ondate = request.args.get('ondate', ymd.dt2asc(datetime.now()))

            # pull in members
            rsu = RunSignUp(key=current_app.config['RSU_KEY'], secret=current_app.config['RSU_SECRET'])
            with rsu:
                members = rsu.members(club_id, current_members_only='F')
            members.sort(key=lambda m: f"{m['user']['last_name']} {m['user']['first_name']} {m['user']['dob']} {m['membership_start']}")

            mapping = {
                'rowId':        lambda m: f"{m['user']['user_id']} {m['membership_start']}",
                'first':        lambda m: m['user']['first_name'], 
                'last':         lambda m: m['user']['last_name'], 
                'div':          _getdivision, 
                'hometown':     lambda m: '{}, {}'.format(m['user']['address']['city'], m['user']['address']['state']), 
                'start':        lambda m: mdy.dt2asc(ymd.asc2dt(m['membership_start'])), 
                'expiration':   lambda m: mdy.dt2asc(ymd.asc2dt(m['membership_end'])), 
                'isostart':     'membership_start',
                'isoend':       'membership_end',
            }
            xform = Transform(mapping, sourceattr=False, targetattr=False)

            # translate rows and set up iterable; note members list is sorted by member last_name, first_name, dob, membership_start
            rowslist = []
            lastmember = ''
            for member in members:
                # if new member, create a new row
                if lastmember != member['user']['last_name'] + ' ' +  member['user']['first_name'] + ' ' + member['user']['dob']:
                    lastmember = member['user']['last_name'] + ' ' +  member['user']['first_name'] + ' ' + member['user']['dob']
                    outrow = {}
                    xform.transform(member, outrow)
                    rowslist.append(outrow)

                # if same as last member and the membership is continuous, update expiration date, else create a new row
                else:
                    lastend = mdy.asc2dt(rowslist[-1]['expiration'])
                    thisstart = ymd.asc2dt(member['membership_start'])

                    # if same as last member and the membership is contiguous, update expiration date
                    if thisstart == lastend + timedelta(1):
                        rowslist[-1]['expiration'] = mdy.dt2asc(ymd.asc2dt(member['membership_end']))
                        rowslist[-1]['isoend'] = member['membership_end']

                    # if noncontiguous membership, create a new row
                    else:
                        outrow = {}
                        xform.transform(member, outrow)
                        rowslist.append(outrow)
            
            # filter based on ondate
            filteredrows = [r for r in rowslist if r['isostart'] <= ondate and r['isoend'] >= ondate]

            # self.rows needs to be iterable for nexttablerow()
            self.rows = iter(filteredrows)

        # if there's no service to pull the data from, there's no data
        else:
            self.rows = iter([])

    def nexttablerow(self):
        row = next(self.rows)
        return row

    def close(self):
        pass

    def permission(self):
        return True

# fsrcmembers_pretablehtml = p('The current list of registered members follows. Note if you recently renewed before your current expiration, \
#     the expiration date shown below may not be correct. We will try to look into this when we can, but in the meantime if you want to make \
#     sure your renewal went through, you can check with membership@steeplechasers.org or technology@steeplechasers.org.')
def frontendmembers_pretablehtml():
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

    return pretablehtml.render()

frontendmembersview = FrontendMembersView(
    app=bp,
    pagename='registered members',
    endpoint='frontend.members',
    endpointvalues={'interest': '<interest>'},
    pretablehtml=frontendmembers_pretablehtml,
    rule='<interest>/members',
    buttons=['csv'],
    dtoptions={
        'order': [[1,'asc']],
        'dom': '<"clear">lBfrtip',
    },
    idSrc='rowId',
    templateargs={'frontend_page': True},
    clientcolumns=[
        # {'data': '',  # needs to be '' else get exception converting options from meetings render_template
        #  # TypeError: '<' not supported between instances of 'str' and 'NoneType'
        #  'name': 'view-control',
        #  'className': 'view-control shrink-to-fit',
        #  'orderable': False,
        #  'defaultContent': '',
        #  'label': '',
        #  'type': 'hidden',  # only affects editor modal
        #  'title': 'View',
        #  'render': {'eval': 'render_icon("fas fa-eye")'},
        #  },
        {'data': 'first', 'name': 'first', 'label': 'First',
         'type': 'readonly'
         },
        {'data': 'last', 'name': 'last', 'label': 'Last',
         'type': 'readonly'
         },
        {'data': 'div', 'name': 'div', 'label': 'Div (age Jan 1)',
         'type': 'readonly'
         },
        {'data': 'hometown', 'name': 'hometown', 'label': 'Hometown',
         'type': 'readonly',
         },
        {'data': 'start', 'name': 'start', 'label': 'Start Date',
         'type': 'readonly',
         },
        {'data': 'expiration', 'name': 'expiration', 'label': 'Expiration Date',
         'type': 'readonly',
         },
    ],
)
frontendmembersview.register()

class AjaxMemberStats(MethodView):
    
    def get(self):
        try:
            # get the club and cache
            memberstatsfile = bp.config['RSU_STATSFILE']

            # get the summarized statistics, and time file was created
            with open(memberstatsfile, 'rb') as stats:
                memberstats_str = stats.read()
            mtime = getmtime(memberstatsfile) - time.timezone;
            cachetime = cachet.epoch2asc(mtime)

            # convert json
            memberstats = json.loads(memberstats_str)

            # it's all good
            return jsonify(success=True, data=memberstats, cachetime=cachetime)
        
        except Exception as e:
            # er, not so good
            cause = format_exc()
            bp.logger.error(format_exc())
            return jsonify(success=False, cause=cause)

bp.add_url_rule('/_memberstats',view_func=AjaxMemberStats.as_view('_memberstats'),methods=['GET'])