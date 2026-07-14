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
from members.community_events import import_events as _import_events

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
@option('--year', default=None, type=int,
        help='Restrict to a single calendar year (e.g. 2026)')
@option('--from-date', default=None,
        help='Start date filter YYYY-MM-DD (default: Jan 1 of current year)')
@option('--to-date', default=None,
        help='End date filter YYYY-MM-DD (default: Dec 31 of next year)')
@option('--debug', is_flag=True, help='Enable debug logging')
@with_appcontext
@catch_errors
def filter_calendar_cmd(interest, output_dir, year, from_date, to_date, debug):
    """
    Fetch Discourse events and write per-series .ics files for interest [interest].

    Uses the /discourse-post-event/events JSON API so topic tags are available
    inline without per-topic lookups.  Writes one .ics file per configured tag
    group into OUTPUT_DIR.
    """
    from datetime import date
    from pathlib import Path

    if debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    if year:
        from_date_obj = date(year, 1, 1)
        to_date_obj = date(year, 12, 31)
    else:
        from_date_obj = date.fromisoformat(from_date) if from_date else None
        to_date_obj = date.fromisoformat(to_date) if to_date else None

    uinterest = interest.upper()
    base_url = current_app.config[f'DISCOURSE_API_URL_{uinterest}']
    discourse = make_discourse_client(interest)

    filter_calendar(
        base_url=base_url,
        discourse=discourse,
        output_dir=Path(output_dir),
        tag_groups=get_tag_groups(current_app.config.get(f'CALENDAR_TAG_GROUPS_{uinterest}')),
        from_date=from_date_obj,
        to_date=to_date_obj,
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


@community.command('import-events')
@argument('interest')
@option('--csv-file', default='fsrc_events_2026.csv', show_default=True,
        help='CSV from export_fsrc_events.py')
@option('--category-id', required=True, type=int,
        help='Discourse category ID to post events into')
@option('--state-file', default='fsrc_import_state.json', show_default=True,
        help='JSON file tracking imported event IDs for idempotency')
@option('--post-as', default=None,
        help='Discourse username to author topics as (overrides DISCOURSE_API_INVITE_USERNAME)')
@option('--dry-run', is_flag=True, help='Print what would be posted without posting')
@option('--debug', is_flag=True, help='Enable debug logging')
@with_appcontext
@catch_errors
def import_events(interest, csv_file, category_id, state_file, post_as, dry_run, debug):
    """
    Create Discourse topics for events in CSV_FILE within interest [interest].
    Idempotent: skips events already recorded in STATE_FILE. Re-run safely after
    fixing tags or editing the CSV.
    """
    if debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    uinterest = interest.upper()
    base_url = current_app.config[f'DISCOURSE_API_URL_{uinterest}']
    username = post_as or current_app.config.get(f'DISCOURSE_API_EVENT_USERNAME_{uinterest}')
    discourse = make_discourse_client(interest, username=username)

    _import_events(
        interest=interest,
        csv_file=csv_file,
        category_id=category_id,
        state_file=state_file,
        discourse=discourse,
        base_url=base_url,
        dry_run=dry_run,
        log=current_app.logger,
    )

