"""
community_calendar_views - on-demand ICS calendar feed, filterable by tag

Single endpoint /<interest>/calendars/events.ics — no tags= returns all events
in the date window; tags=<tag>[,<tag>...] returns the union of events carrying
any of the listed tags.
"""

# standard
import time
from datetime import date
from io import BytesIO

# pypi
from flask import current_app, g, abort, request, send_file

# homegrown
from . import bp
from members.community import make_discourse_client
from members.community_calendar import filter_tags_to_bytes

# Compiled ICS bytes cached per (interest, tags, from_date, to_date), per worker process.
_ics_cache: dict = {}

ICS_CACHE_TTL = 15 * 60  # rebuild at most once per 15 minutes per (interest, tags, from, to)


def _parse_tags_param() -> list[str] | None:
    """Parse ?tags=tag1,tag2 into a list, or None if omitted (meaning: all events)."""
    tags_str = request.args.get('tags')
    if not tags_str:
        return None
    tags = [t.strip() for t in tags_str.split(',') if t.strip()]
    return tags or None


def _parse_date_params() -> tuple[date | None, date | None]:
    """Parse ?year=YYYY or ?from=YYYY-MM-DD&to=YYYY-MM-DD query params.

    from also accepts the literal 'today'. When to is omitted, the caller
    (filter_tags_to_bytes) defaults to an open-ended future window.
    """
    year_str = request.args.get('year')
    if year_str:
        try:
            year = int(year_str)
            return date(year, 1, 1), date(year, 12, 31)
        except (ValueError, TypeError):
            abort(400)
    from_str = request.args.get('from')
    to_str = request.args.get('to')
    try:
        if from_str == 'today':
            from_date = date.today()
        else:
            from_date = date.fromisoformat(from_str) if from_str else None
        to_date = date.fromisoformat(to_str) if to_str else None
    except ValueError:
        abort(400)
    return from_date, to_date


@bp.route('/<interest>/calendars/events.ics')
def calendar_feed():
    # interest is consumed from URL values by the pull_interest preprocessor -> g.interest
    interest = g.interest
    uinterest = interest.upper()

    tags = _parse_tags_param()
    from_date, to_date = _parse_date_params()

    cache_key = (interest, tuple(sorted(tags)) if tags else None, from_date, to_date)
    cached = _ics_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < ICS_CACHE_TTL:
        return _ics_response(cached[1])

    base_url = current_app.config[f'DISCOURSE_API_URL_{uinterest}']
    username = current_app.config.get(f'DISCOURSE_API_CALENDAR_USERNAME_{uinterest}')
    location_query_id = current_app.config.get(f'DISCOURSE_API_EVENT_LOCATIONS_QUERY_{uinterest}')
    discourse = make_discourse_client(interest, username=username)
    # the Data Explorer "run query" endpoint is admin-only, so it can't go through
    # the calendar's deliberately low-privilege `discourse` client above -- build
    # a separate admin-privileged one (default INVITE_USERNAME, same API key)
    # only when there's actually a query configured to run through it.
    admin_discourse = make_discourse_client(interest) if location_query_id else None

    ics_bytes = filter_tags_to_bytes(
        base_url=base_url,
        discourse=discourse,
        tags=tags,
        from_date=from_date,
        to_date=to_date,
        location_query_id=location_query_id,
        admin_discourse=admin_discourse,
        log=current_app.logger,
    )
    _ics_cache[cache_key] = (time.time(), ics_bytes)
    return _ics_response(ics_bytes)


def _ics_response(ics_bytes: bytes):
    return send_file(
        BytesIO(ics_bytes),
        mimetype='text/calendar',
        as_attachment=True,
        download_name='events.ics',
    )
