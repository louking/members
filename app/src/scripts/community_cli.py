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
from members.community import RsuRaceCommunitySyncManager, RsuClubCommunitySyncManager, DbTagCommunitySyncManager, make_discourse_client
from members.community_taxonomy import fetch_all, build_docx
from members.community_calendar import filter_calendar, get_tag_groups

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


@community.command('filter-calendar')
@argument('interest')
@option('--output-dir', default='/var/www/calendars', show_default=True,
        help='Directory to write per-series .ics files into')
@option('--cache-file',
        default='/var/lib/discourse-calendar-filter/topic_tags_cache.json',
        show_default=True,
        help='JSON file used to cache topic→tags lookups between runs')
@option('--cache-ttl', default=3600, show_default=True,
        help='Seconds before a cached topic-tags entry is re-fetched')
@option('--force-refresh', is_flag=True,
        help='Ignore cached topic tags and re-fetch all topics this run')
@option('--debug', is_flag=True, help='Enable debug logging')
@with_appcontext
@catch_errors
def filter_calendar_cmd(interest, output_dir, cache_file, cache_ttl, force_refresh, debug):
    """
    Split the Discourse events.ics feed into per-series .ics files for interest [interest].

    Fetches the global events feed from the Discourse instance configured for [interest],
    looks up each event's Discourse tags, and writes one .ics file per tag group
    (grandprix.ics, equalizer.ics, decathlon.ics) into OUTPUT_DIR.
    """
    from pathlib import Path

    if debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    uinterest = interest.upper()
    base_url = current_app.config[f'DISCOURSE_API_URL_{uinterest}']
    discourse = make_discourse_client(interest)

    filter_calendar(
        base_url=base_url,
        discourse=discourse,
        output_dir=Path(output_dir),
        cache_file=Path(cache_file),
        tag_groups=get_tag_groups(current_app.config.get(f'CALENDAR_TAG_GROUPS_{uinterest}')),
        cache_ttl=cache_ttl,
        force_refresh=force_refresh,
        log=current_app.logger,
    )


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


