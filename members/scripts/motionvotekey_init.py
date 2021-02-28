'''
motionvotekey_init - command line database initialization - initialize motionvotekey in motionvote
===================================================================================================
run from 3 levels up, like python -m members.scripts.motionvotekey_init

'''
# standard
from os.path import join, dirname
from uuid import uuid4

# pypi
from flask import url_for

# homegrown
from members import create_app
from members.settings import Development
from members.model import db
from members.applogging import setlogging
from members.model import MotionVote

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

        # assumes MeetingType table was created manually, with Board Meeting as a meeting type
        motionvotes = MotionVote.query.filter_by().all()
        for motionvote in motionvotes:
            if not motionvote.motionvotekey:
                motionvote.motionvotekey = uuid4().hex

        db.session.commit()

if __name__ == "__main__":
    main()