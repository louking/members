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
from members.community_taxonomy import fetch_all, build_docx

# needs to be before any commands
@group()
def community():
    """Perform community module tasks"""
    pass

@community.command()
@argument('interest')
@argument('raceid')
@argument('communitygroupname')
@option('--skipemail', is_flag=True, help='if set, skip sending email to new community user')
@option('--debug', is_flag=True, help='enable debug logging')
@option('--debugrequests', is_flag=True, help='enable requests debug logging')
@with_appcontext
@catch_errors
def syncrace(interest, raceid, communitygroupname, skipemail, debug, debugrequests):
    """
    Sync community group [communitygroupname] membership from RunSignup race
    [raceid] participants within interest [interest]
    """
    grpmgr = RsuRaceCommunitySyncManager(interest, raceid, communitygroupname, skipemail)
    grpmgr.import_group(debug=debug, debugrequests=debugrequests)


@community.command()
@argument('interest')
@argument('clubid')
@argument('communitygroupname')
@option('--skipemail', is_flag=True, help='if set, skip sending email to new community user')
@option('--debug', is_flag=True, help='enable debug logging')
@option('--debugrequests', is_flag=True, help='enable requests debug logging')
@with_appcontext
@catch_errors
def syncclub(interest, clubid, communitygroupname, skipemail, debug, debugrequests):
    """
    Sync community group [communitygroupname] membership from RunSignup
    membership organization [clubid] members within interest [interest]
    """
    grpmgr = RsuClubCommunitySyncManager(interest, clubid, communitygroupname, skipemail)
    grpmgr.import_group(debug=debug, debugrequests=debugrequests)


@community.command()
@argument('interest')
@argument('tagname')
@argument('communitygroupname')
@option('--skipemail', is_flag=True, help='if set, skip sending email to new community user')
@option('--debug', is_flag=True, help='enable debug logging')
@option('--debugrequests', is_flag=True, help='enable requests debug logging')
@with_appcontext
@catch_errors
def synctag(interest, tagname, communitygroupname, skipemail, debug, debugrequests):
    """
    Sync community group [communitygroupname]  within interest [interest] with users tagged with position
    tag [tagname]
    """
    grpmgr = DbTagCommunitySyncManager(interest, tagname, communitygroupname, skipemail)
    grpmgr.import_group(debug=debug, debugrequests=debugrequests)


@community.command('export-taxonomy')
@argument('interest')
@option('--output', default='discourse-taxonomy.docx', show_default=True,
        help='Output .docx filename')
@option('--json', 'save_json', is_flag=True, help='Also save a raw JSON snapshot alongside the docx')
@with_appcontext
@catch_errors
def export_taxonomy(interest, output, save_json):
    """
    Export Discourse forum taxonomy and configuration for interest [interest] to a .docx file.
    """
    import json as _json

    uinterest = interest.upper()
    base_url = current_app.config[f'DISCOURSE_API_URL_{uinterest}']
    api_key = current_app.config[f'DISCOURSE_API_KEY_{uinterest}']
    api_username = current_app.config[f'DISCOURSE_API_INVITE_USERNAME_{uinterest}']
    category_groups_query_id = current_app.config.get(f'DISCOURSE_API_CATEGORY_GROUPS_QUERY_{uinterest}')

    data = fetch_all(base_url, api_key, api_username,
                     category_groups_query_id=category_groups_query_id)

    if save_json:
        json_path = output.replace('.docx', '.json')
        with open(json_path, 'w') as f:
            _json.dump(data, f, indent=2, default=str)
        print(f'  JSON snapshot saved: {json_path}')

    print('  Building document...', end=' ', flush=True)
    doc = build_docx(data, base_url)
    doc.save(output)
    print('OK')
    print(f'\nSaved: {output}')


