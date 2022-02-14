'''
racingteam_appln_init - command line database initialization - initialize racingteam application tables
====================================================================================================================
run from 3 levels up, like python -m members.scripts.racingteam_appln_init

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
from members.model import RacingTeamVolunteer, db
from members.applogging import setlogging

from loutilities.timeu import asctime, age
from members.model import RacingTeamApplication, RacingTeamResult
from members.views.admin.viewhelpers import localinterest_query_params, localinterest

class parameterError(Exception): pass

tstamp = asctime("%a %b %d %Y %H:%M:%S")
isodate = asctime("%Y-%m-%d")

def main():
    descr = '''
    Update racing team info volunteer records from csv file
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

    # translate type from old format to new
    applntype = {
        'Returning Racing Team Member': 'renewal',
        'New Racing Team Member': 'new',
    }
    
    # need app context, open input file
    with app.app_context(), open(args.inputfile, 'r', encoding=detected['encoding'], newline='', errors='replace') as IN:
        # turn on logging
        setlogging()

        # trick local interest stuff
        g.interest = 'fsrc'

        # initialize database tables from input file
        infile = DictReader(IN)
        for row in infile:
            # this pulls timezone information off of record timestamp, formatted like 'Sun Feb 25 2018 14:07:17 GMT-0500 (EST)'
            timestampasc = ' '.join(row['time'].split(' ')[:-2])
            timestamp = tstamp.asc2dt(timestampasc)
            
            # if we already have received an application for this name at this timestamp, skip it else we'll get duplicates
            applnrec = RacingTeamApplication.query.filter_by(name=row['name'], logtime=timestamp, **localinterest_query_params()).one_or_none()
            if applnrec: continue
            
            # at least one record doesn't have a date of birth       
            if not row['dob']:
                app.logger.warning(f"racingteam_appln_init: skipping {row['name']} {row['race1-name']} {row[f'race1-date']}")
                continue
            
            # if we've gotten here, we need to add application and result records     
            dob = isodate.asc2dt(row['dob']).date()
            applnrec = RacingTeamApplication(
                interest=localinterest(), 
                logtime=timestamp, 
                name=row['name'], 
                type=applntype[row['applntype']],
                comments=row['comments'],
                dateofbirth=dob,
                email=row['email'],
                gender=row['gender'].upper()[0],
            )
            db.session.add(applnrec)
            for race in ['race1', 'race2']:
                # originally, new members were only asked for one race
                # detect this condition and skip this result -- this should only happen for race2
                if not row[f'{race}-date']: continue
                
                # handle case where age grade was not calculated properly
                # this was due to deficiency in the original script, so these should be early entries
                # it's not worth adding the complexity to fix this data at this point
                try:
                    agegrade = float(row[f'{race}-agegrade']),
                    agegrade = row[f'{race}-agegrade']
                except ValueError:
                    agegrade = None
                
                # calculate age
                racedate = isodate.asc2dt(row[f'{race}-date']).date()
                thisage = age(racedate, dob)
                
                # add result
                resultrec = RacingTeamResult(
                    interest=localinterest(), 
                    application=applnrec, 
                    eventdate = racedate,
                    eventname = row[f'{race}-name'],
                    age = thisage,
                    agegrade = agegrade,
                    distance = row[f'{race}-distance'],
                    units = row[f'{race}-units'],
                    location = row[f'{race}-location'],
                    url = row[f'{race}-resultslink'],
                    time = row[f'{race}-time'],
                )
                db.session.add(resultrec)
            
        db.session.commit()

if __name__ == "__main__":
    main()