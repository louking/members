'''
membership_common - admin/frontend common membership view functions
===========================================================================
'''

# standard
from datetime import datetime, timedelta
from json import dumps

# pypi
from loutilities.timeu import asctime
from sortedcollections import SortedDict

# homegrown
from ..model import Member
from .admin.viewhelpers import localinterest
from ..applogging import timenow    # for logpoints

md = asctime('%m-%d')

def analyzemembership(statsfile=None):
    # stats will be unordered dict {year1: {date1:count1, date2:count2...}, year2: {...}, ... }
    stats = {}
    # stats = SortedDict(key=lambda k, v: k)

    members = Member.query.filter_by(interest=localinterest()).all()

    # for each member, add 1 for every date the membership represents
    # only go through today
    today = datetime.now().date()
    for member in members:
        thisdate = member.start_date
        enddate  = member.end_date
        while thisdate <= enddate and thisdate <= today:
            thisyear = thisdate.year
            # skip early registrations
            if thisyear >= 2013:     
                thismd   = md.dt2asc(thisdate)
                stats.setdefault(thisyear, {})
                stats[thisyear].setdefault(thismd, 0)
                stats[thisyear][thismd] += 1
            thisdate += timedelta(1)

    statslist = []
    years = sorted(list(stats.keys()))
    for year in years:
        yearcounts = {'year' : year, 'counts' : [] }
        datecounts = sorted(list(stats[year].keys()))
        for date in datecounts:
            yearcounts['counts'].append( { 'date' : date, 'count' : stats[year][date] } )
        statslist.append( yearcounts )

    if statsfile:
        with open(statsfile, 'w') as statsf:
            statsjson = dumps(statslist, indent=4, sort_keys=True, separators=(',', ': '))
            statsf.write(statsjson)

    return statslist
