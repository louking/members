'''
racingteam_inforesults_init - command line database initialization - initialize racingteam info raceresults tables
====================================================================================================================
run from 3 levels up, like python -m members.scripts.racingteam_inforesults_init

'''
# standard
from os.path import join, dirname
from csv import DictReader
from argparse import ArgumentParser

# pypi
from flask import g
from charset_normalizer import detect

# homegrown
from members import create_app
from members.settings import Development
from members.model import db
from members.applogging import setlogging

from loutilities.timeu import asctime
from members.model import LocalUser, RacingTeamMember, RacingTeamInfo, RacingTeamResult
from members.views.admin.viewhelpers import localinterest_query_params, localinterest

class parameterError(Exception): pass

tstamp = asctime("%a %b %d %Y %H:%M:%S")
isodate = asctime("%Y-%m-%d")

def main():
    descr = '''
    Update racing team info results records from csv file
    '''
    parser = ArgumentParser(description=descr)
    parser.add_argument('inputfile', help='csv file with input records', default=None)
    args = parser.parse_args()
    
    scriptdir = dirname(__file__)
    # two levels up
    scriptfolder = dirname(dirname(scriptdir))
    configdir = join(scriptfolder, 'config')
    memberconfigfile = "members.cfg"
    memberconfigpath = join(configdir, memberconfigfile)
    userconfigfile = "users.cfg"
    userconfigpath = join(configdir, userconfigfile)

    # create app and get configuration
    # use this order so members.cfg overrrides users.cfg
    configfiles = [userconfigpath, memberconfigpath]
    app = create_app(Development(configfiles), configfiles)

    # set up database
    db.init_app(app)

    # determine input file encoding
    with open(args.inputfile, 'rb') as binaryfile:
        rawdata = binaryfile.read()
    detected = detect(rawdata)

    # need app context, open input file
    with app.app_context(), open(args.inputfile, 'r', encoding=detected['encoding'], newline='', errors='replace') as IN:
        # turn on logging
        setlogging()

        # trick local interest stuff
        g.interest = 'fsrc'

        # initialize database tables from input file
        infile = DictReader(IN)
        for result in infile:
            # first check if racing team member exists
            localuser = LocalUser.query.filter_by(name=result['name'], **localinterest_query_params()).one_or_none()
            member = RacingTeamMember.query.filter_by(localuser=localuser, **localinterest_query_params()).one_or_none() if localuser else None
            if not member: continue
            
            # this pulls timezone information off of result timestamp, formatted like 'Sun Feb 25 2018 14:07:17 GMT-0500 (EST)'
            timestampasc = ' '.join(result['timestamp'].split(' ')[:-2])
            timestamp = tstamp.asc2dt(timestampasc)
            
            # if we already have received an info record for this member at this timestamp, skip it else we'll get duplicates
            inforec = RacingTeamInfo.query.filter_by(member=member, logtime=timestamp).one_or_none()
            if inforec: continue
            
            # if we've gotten here, we need to add info and result records
            inforec = RacingTeamInfo(interest=localinterest(), member=member, logtime=timestamp)
            db.session.add(inforec)
            resultrec = RacingTeamResult(
                interest=localinterest(), 
                info=inforec, 
                eventdate = isodate.asc2dt(result['eventdate']).date(),
                eventname = result['eventname'],
                age = result['age'],
                agegrade = result['agegrade'],
                distance = result['distance'],
                units = result['units'],
                time = result['time'],
                awards = result['awards'],
            )
            db.session.add(resultrec)
            
        db.session.commit()

if __name__ == "__main__":
    main()