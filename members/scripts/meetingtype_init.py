'''
meetingtype_init - command line database initialization - initialize meetingtype in meetings
================================================================================================
run from 3 levels up, like python -m members.scripts.meetingtype_init

'''
# standard
from os.path import join, dirname

# pypi
from flask import url_for

# homegrown
from members import create_app
from members.settings import Development
from members.model import db
from members.applogging import setlogging
from members.model import LocalInterest, Meeting, MeetingType
from loutilities.user.model import Interest

class parameterError(Exception): pass

def main():
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

    # set up scoped session
    with app.app_context():
        # turn on logging
        setlogging()

        fsrcinterest = Interest.query.filter_by(interest='fsrc').one()
        localfsrcinterest = LocalInterest.query.filter_by(interest_id=fsrcinterest.id).one()

        # assumes MeetingType table was created manually, with Board Meeting as a meeting type
        boardmeeting = MeetingType.query.filter_by(meetingtype='Board Meeting', interest=localfsrcinterest).one()
        meetings = Meeting.query.filter_by(interest=localfsrcinterest).all()
        for meeting in meetings:
            meeting.meetingtype = boardmeeting

        db.session.commit()

if __name__ == "__main__":
    main()