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
from members.community import RsuRaceCommunitySyncManager

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


# TODO: this is just to test the interface -- this should be deleted
from fluent_discourse import Discourse, DiscourseError
@community.command()
@argument('interest')
@argument('email')
@with_appcontext
@catch_errors
def getinvite(interest, email):
    """
    Get a discourse invite link for a local interest group

    :param interest: local interest group short name
    :param email: email address to send invite to, or auto to just get the link
    """
    upper_interest = interest.upper()
    
    # set up discourse client
    discourse = Discourse(
        base_url=current_app.config[f'DISCOURSE_API_URL_{upper_interest}'],
        username=current_app.config[f'DISCOURSE_API_USERNAME_{upper_interest}'],
        api_key=current_app.config[f'DISCOURSE_API_KEY_{upper_interest}'],
        raise_for_rate_limit=True,
    )

    try:
        invite = discourse.invites.retrieve.json.get({
            'email': email,
        })
    except DiscourseError as e:
        raise ParameterError(f'ERROR: could not retrieve invite: {e}')

    print(f'Invite had been sent to {email} for interest {interest}: {invite}')

# TODO: this is just to test the interface -- this should be deleted
@community.command()
@argument('interest')
@argument('username')
@with_appcontext
@catch_errors
def getuseremails(interest, username):
    """
    Get a discourse invite link for a local interest group

    :param interest: local interest group short name
    :param username: username to get emails for
    """
    upper_interest = interest.upper()
    
    # set up discourse client
    discourse = Discourse(
        base_url=current_app.config[f'DISCOURSE_API_URL_{upper_interest}'],
        username=current_app.config[f'DISCOURSE_API_USERNAME_{upper_interest}'],
        api_key=current_app.config[f'DISCOURSE_API_KEY_{upper_interest}'],
        raise_for_rate_limit=True,
    )

    try:
        emails = discourse.u[username].emails.json.get({
        })
    except DiscourseError as e:
        raise ParameterError(f'ERROR: could not retrieve invite: {e}')

    print(f'Emails for user {username} in interest {interest}: {emails}')