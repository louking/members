"""
community_calendar - filter Discourse events by tag into per-series ICS feeds

Uses the /discourse-post-event/events JSON API (not the ICS feed) so topic tags
are available inline, eliminating the N+1 per-topic API calls the ICS approach
required.  Tags appear in event['post']['topic']['tags'] as a list of strings.

Event location is a separate N+1 risk: the events API doesn't return it (see
the Discourse API Quirks note in CLAUDE.md), so it has to come from each post's
raw content. fetch_event_locations() avoids per-post REST calls by resolving
all of them in one (paged) Data Explorer query instead.
"""

# standard
import logging as _logging
import re
from datetime import date, datetime, time
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

# pypi
from icalendar import Calendar, Event

# homegrown
from .community import run_query_paged

_EVENT_LOCATION_RE = re.compile(r'\[event\b[^\]]*\blocation="([^"]*)"', re.IGNORECASE)


def _tag_names(tags: list) -> set[str]:
    """Normalise Discourse tag list to a set of name strings.

    The /discourse-post-event/events JSON API returns tags as objects
    ({'id': 20, 'name': 'grand-prix', 'slug': 'grand-prix'}) rather than
    plain strings, so extract 'name' when needed.
    """
    if not tags:
        return set()
    if isinstance(tags[0], dict):
        return {t['name'] for t in tags if 'name' in t}
    return set(tags)


def _parse_event_datetime(dt_str: str, tz_name: str) -> datetime:
    """Parse a Discourse event datetime string to an aware datetime.

    Discourse returns either offset-aware strings ("2026-03-03T17:30:00.000-05:00")
    or naive strings ("2026-02-02T18:00:00") that must be localised using the
    event's timezone field.  Always returns a datetime with the named IANA timezone
    (ZoneInfo) so icalendar serialises TZID=America/New_York rather than UTC-05:00.
    """
    tz = ZoneInfo(tz_name or 'UTC')
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z'):
        try:
            return datetime.strptime(dt_str, fmt).astimezone(tz)
        except ValueError:
            pass
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(dt_str, fmt).replace(tzinfo=tz)
        except ValueError:
            pass
    raise ValueError(f"Cannot parse datetime: {dt_str!r}")


def _fetch_location(discourse, post_id: int, log) -> str | None:
    """Fetch a single post's raw content and extract [event location="..."].

    Uses /posts/{id}.json rather than /t/{topic_id}.json because the raw field
    is not reliably present in the topic endpoint response. One REST call per
    post -- only used as the fetch_event_locations() fallback when no Data
    Explorer query is configured; otherwise this is exactly the N+1 pattern
    fetch_event_locations() exists to avoid.
    """
    try:
        resp = discourse.posts._(post_id).json.get({})
        raw = resp.get('raw', '')
        m = _EVENT_LOCATION_RE.search(raw)
        return m.group(1) if m else None
    except Exception as exc:
        log.warning("Failed to fetch location for post %s: %s", post_id, exc)
        return None


def fetch_event_locations(discourse, post_ids: list[int], query_id: str | None, log) -> dict[int, str]:
    """Resolve [event location="..."] for a set of post ids.

    query_id -- id of a Discourse Data Explorer query returning (id, raw) for
    posts.id IN :post_ids (an int_list param), paged via page_num/page_size
    like the other Data Explorer queries in this codebase. When configured,
    this replaces what would otherwise be one /posts/{id}.json REST call per
    event with a single query (possibly a handful of pages for a very large
    post_ids list). Falls back to the old per-post REST calls when query_id
    is absent -- same optional-config/fallback tradeoff as the category-groups
    Data Explorer query in community_taxonomy.py.
    """
    if not post_ids:
        return {}
    if not query_id:
        locations = {}
        for post_id in post_ids:
            location = _fetch_location(discourse, post_id, log)
            if location is not None:
                locations[post_id] = location
        return locations
    # int_list must be sent as a comma-separated string, not a JSON array -- a
    # native array's first element is silently dropped (see CLAUDE.md's Data
    # Explorer int_list quirk note for how this was diagnosed)
    columns, rows = run_query_paged(discourse, query_id, params={'post_ids': ','.join(str(pid) for pid in post_ids)})
    locations = {}
    returned_ids = set()
    for row in rows:
        record = dict(zip(columns, row))
        returned_ids.add(record['id'])
        m = _EVENT_LOCATION_RE.search(record.get('raw') or '')
        if m:
            locations[record['id']] = m.group(1)
    missing_ids = set(post_ids) - returned_ids
    if missing_ids:
        # diagnostic for the 62-vs-63-rows discrepancy: which post id(s) the
        # query didn't return a row for at all, vs. one it returned but with
        # no [event location="..."] in its raw content (a normal, silent case
        # handled below by the len(locations) < len(returned_ids) comparison)
        log.warning(
            "fetch_event_locations(): %d post id(s) requested but not returned by "
            "Data Explorer query %s: %s",
            len(missing_ids), query_id, sorted(missing_ids),
        )
    log.debug(
        "fetch_event_locations(): resolved %d/%d post locations via Data Explorer query %s "
        "(%d/%d posts returned, %d had no location in raw content)",
        len(locations), len(post_ids), query_id,
        len(returned_ids), len(post_ids), len(returned_ids) - len(locations),
    )
    return locations


def _build_vevent(event: dict, base_url: str, location: str | None = None) -> Event:
    """Build an icalendar Event from one /discourse-post-event/events entry."""
    cal_event = Event()
    tz_name = event.get('timezone') or 'UTC'
    summary = event.get('name') or event['post']['topic']['title']
    cal_event.add('SUMMARY', summary)
    cal_event.add('DTSTART', _parse_event_datetime(event['starts_at'], tz_name))
    cal_event.add('DTEND', _parse_event_datetime(event['ends_at'], tz_name))
    cal_event.add('URL', base_url.rstrip('/') + event['post']['url'])
    cal_event.add('UID', f"discourse-event-{event['id']}@{urlparse(base_url).netloc}")
    if location:
        cal_event.add('LOCATION', location)
    return cal_event


def _fetch_events(discourse, from_date: date | None, to_date: date | None, log) -> list[dict]:
    """Call /discourse-post-event/events for the given date window.

    Defaults to current year + next year when no range is specified.
    The API returns all events within the window in a single response; no
    server-side pagination metadata is exposed by this endpoint.
    """
    today = date.today()
    after_dt = datetime.combine(from_date or date(today.year, 1, 1), time(0, 0, 0))
    before_dt = datetime.combine(to_date or date(today.year + 1, 12, 31), time(23, 59, 59))
    params = {
        'after': after_dt.isoformat(),
        'before': before_dt.isoformat(),
        'include_ongoing': 'true',
    }
    log.info("Fetching events: after=%s before=%s", params['after'], params['before'])
    resp = discourse._('discourse-post-event').events.get(params)
    events = resp.get('events', [])
    log.info("Got %d events from API", len(events))
    if events:
        sample_tags = _tag_names(events[0].get('post', {}).get('topic', {}).get('tags', []))
        log.debug("First event: id=%s tags=%s", events[0].get('id'), sample_tags)
    return events


def filter_tags_to_bytes(base_url: str, discourse, tags: list[str] | None = None,
                         from_date: date | None = None,
                         to_date: date | None = None,
                         location_query_id: str | None = None,
                         admin_discourse=None,
                         log=None) -> bytes:
    """
    Fetch Discourse events via JSON API and return ICS bytes for a set of tags.

    Intended for the web route (on-demand).  No file I/O or disk cache — the
    caller owns any caching layer (e.g. _ics_cache in community_calendar_views).

    base_url          — Discourse site root
    discourse         — _RateLimitedDiscourse instance; typically authenticated
                         as a low-privilege, "public"-equivalent account for
                         reading events, not the admin account
    tags              — event is included if it carries any one of these tags
                         (union); None or empty means include all events, unfiltered
    from_date         — inclusive start date filter (default: Jan 1 of current year)
    to_date           — inclusive end date filter (default: open-ended / far
                         future, i.e. all future events)
    location_query_id — Data Explorer query id for fetch_event_locations(); None
                         falls back to one REST call per matched event
    admin_discourse    — admin-privileged _RateLimitedDiscourse instance, required
                         when location_query_id is set: /admin/plugins/explorer/...
                         is an admin-only endpoint, so it can't be run through
                         discourse above if that's a deliberately low-privilege
                         client (as it is for the calendar route). Ignored when
                         location_query_id is None, since the REST fallback works
                         fine with any authenticated account.
    log               — logger
    """
    if log is None:
        log = _logging.getLogger(__name__)
    today = date.today()
    from_date = from_date or date(today.year, 1, 1)
    to_date = to_date or date(today.year + 10, 12, 31)
    required_tags = set(tags) if tags else None

    events = _fetch_events(discourse, from_date, to_date, log)

    if required_tags is not None:
        matched_events = []
        for event in events:
            topic_tags = _tag_names(event.get('post', {}).get('topic', {}).get('tags', []))
            if required_tags & topic_tags:
                matched_events.append(event)
    else:
        matched_events = events

    # dict.fromkeys dedupes while preserving order -- recurring discourse-calendar
    # events can produce multiple event entries (one per occurrence) that all
    # point at the same underlying post, so this list can have fewer distinct
    # ids than there are matched_events
    post_ids = list(dict.fromkeys(event['post']['id'] for event in matched_events))
    location_discourse = admin_discourse if location_query_id and admin_discourse else discourse
    locations = fetch_event_locations(location_discourse, post_ids, location_query_id, log)

    cal = Calendar()
    cal.add('PRODID', '-//FSRC Calendar//EN')
    cal.add('VERSION', '2.0')

    count = 0
    for event in matched_events:
        location = locations.get(event['post']['id'])
        cal.add_component(_build_vevent(event, base_url, location=location))
        count += 1

    log.debug("Built events.ics (%d events, tags=%s)", count, sorted(required_tags) if required_tags else 'all')
    return cal.to_ical()
