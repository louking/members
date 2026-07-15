"""
community_calendar - filter Discourse events by tag into per-series ICS feeds

Uses the /discourse-post-event/events JSON API (not the ICS feed) so topic tags
are available inline, eliminating the N+1 per-topic API calls the ICS approach
required.  Tags appear in event['post']['topic']['tags'] as a list of strings.
"""

# standard
import logging as _logging
import re
from datetime import date, datetime, time
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

# pypi
from icalendar import Calendar, Event

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
    """Fetch a post's raw content and extract the [event location="..."] value.

    Uses /posts/{id}.json rather than /t/{topic_id}.json because the raw field
    is not reliably present in the topic endpoint response.
    """
    try:
        resp = discourse.posts._(post_id).json.get({})
        raw = resp.get('raw', '')
        m = _EVENT_LOCATION_RE.search(raw)
        return m.group(1) if m else None
    except Exception as exc:
        log.warning("Failed to fetch location for post %s: %s", post_id, exc)
        return None


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
                         log=None) -> bytes:
    """
    Fetch Discourse events via JSON API and return ICS bytes for a set of tags.

    Intended for the web route (on-demand).  No file I/O or disk cache — the
    caller owns any caching layer (e.g. _ics_cache in community_calendar_views).

    base_url   — Discourse site root
    discourse  — _RateLimitedDiscourse instance
    tags       — event is included if it carries any one of these tags (union);
                 None or empty means include all events, unfiltered
    from_date  — inclusive start date filter (default: Jan 1 of current year)
    to_date    — inclusive end date filter (default: open-ended / far future,
                 i.e. all future events)
    log        — logger
    """
    if log is None:
        log = _logging.getLogger(__name__)
    today = date.today()
    from_date = from_date or date(today.year, 1, 1)
    to_date = to_date or date(today.year + 10, 12, 31)
    required_tags = set(tags) if tags else None

    events = _fetch_events(discourse, from_date, to_date, log)

    cal = Calendar()
    cal.add('PRODID', '-//FSRC Calendar//EN')
    cal.add('VERSION', '2.0')

    count = 0
    for event in events:
        if required_tags is not None:
            topic_tags = _tag_names(event.get('post', {}).get('topic', {}).get('tags', []))
            if not (required_tags & topic_tags):
                continue
        post_id = event['post']['id']
        location = _fetch_location(discourse, post_id, log)
        cal.add_component(_build_vevent(event, base_url, location=location))
        count += 1

    log.debug("Built events.ics (%d events, tags=%s)", count, sorted(required_tags) if required_tags else 'all')
    return cal.to_ical()
