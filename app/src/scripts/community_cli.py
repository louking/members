"""
community_cli - cli tasks needed for community management (discourse integration)
"""

# standard

# pypi
from flask import g, current_app
from flask.cli import with_appcontext
from click import argument, group, option

# homegrown
from scripts import catch_errors, ParameterError
from members.community import RsuRaceCommunitySyncManager, RsuClubCommunitySyncManager, DbTagCommunitySyncManager

# needs to be before any commands
@group()
def community():
    """Perform community module tasks"""
    pass

@community.command()
@argument('interest')
@argument('raceid')
@argument('communitygroupname')
@option('--debug', is_flag=True, help='enable debug logging')
@option('--debugrequests', is_flag=True, help='enable requests debug logging')
@with_appcontext
@catch_errors
def syncrace(interest, raceid, communitygroupname, debug, debugrequests):
    """
    Sync community group [communitygroupname] membership from RunSignup race
    [raceid] participants within interest [interest]
    """
    grpmgr = RsuRaceCommunitySyncManager(interest, raceid, communitygroupname)
    grpmgr.import_group(debug=debug, debugrequests=debugrequests)


@community.command()
@argument('interest')
@argument('clubid')
@argument('communitygroupname')
@option('--debug', is_flag=True, help='enable debug logging')
@option('--debugrequests', is_flag=True, help='enable requests debug logging')
@with_appcontext
@catch_errors
def syncclub(interest, clubid, communitygroupname, debug, debugrequests):
    """
    Sync community group [communitygroupname] membership from RunSignup
    membership organization [clubid] members within interest [interest]
    """
    grpmgr = RsuClubCommunitySyncManager(interest, clubid, communitygroupname)
    grpmgr.import_group(debug=debug, debugrequests=debugrequests)


@community.command()
@argument('interest')
@argument('tagname')
@argument('communitygroupname')
@option('--debug', is_flag=True, help='enable debug logging')
@option('--debugrequests', is_flag=True, help='enable requests debug logging')
@with_appcontext
@catch_errors
def synctag(interest, tagname, communitygroupname, debug, debugrequests):
    """
    Sync community group [communitygroupname]  within interest [interest] with users tagged with position
    tag [tagname]
    """
    grpmgr = DbTagCommunitySyncManager(interest, tagname, communitygroupname)
    grpmgr.import_group(debug=debug, debugrequests=debugrequests)


