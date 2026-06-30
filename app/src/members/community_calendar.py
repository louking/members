"""
community_calendar - filter Discourse events.ics by tag into per-series feeds

Discourse's discourse-calendar plugin exposes a single global ICS feed with
no tag/category filtering and no CATEGORIES: field.  This module fetches that
feed, cross-references each event's topic against its Discourse tags via the
rate-limited fluent_discourse client, and either writes one .ics file per
configured tag group (CLI path) or returns bytes for a single series (web path).
"""

# standard
import json
import re
import time
from pathlib import Path

# pypi
import requests
from fasteners import InterProcessLock
from icalendar import Calendar

TOPIC_ID_RE = re.compile(r"/t/[^/]+/(\d+)")

# Fallback tag → output-filename mapping used when CALENDAR_TAG_GROUPS_<interest> is not in config.
DEFAULT_TAG_GROUPS = {
    "grandprix.ics": "grand-prix",
    "equalizer.ics": "equalizer",
    "decathlon.ics": "decathlon",
}


def get_tag_groups(config_value=None) -> dict:
    """Return tag groups dict from config, or DEFAULT_TAG_GROUPS if absent.

    config_value may be a dict (loutilities configparser eval()s values automatically)
    or a string (JSON) for callers that pass a raw value.

    Expected members.cfg format:
        CALENDAR_TAG_GROUPS: {"grandprix.ics": "grandprix", "equalizer.ics": "equalizer", "decathlon.ics": "decathlon"}
    """
    if not config_value:
        return DEFAULT_TAG_GROUPS
    if isinstance(config_value, dict):
        return config_value
    return json.loads(config_value)

REQUEST_TIMEOUT = 15


def load_cache(cache_file: Path) -> dict:
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    return {}


def save_cache(cache: dict, cache_file: Path) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache))


def extract_topic_id(event) -> int | None:
    url = str(event.get("URL", ""))
    match = TOPIC_ID_RE.search(url)
    return int(match.group(1)) if match else None


def get_topic_tags(topic_id: int, cache: dict, discourse,
                   cache_ttl: int, log) -> list[str]:
    """Look up tags for a topic via the rate-limited fluent_discourse client."""
    key = str(topic_id)
    cached = cache.get(key)
    if cached is not None and (time.time() - cached["fetched_at"]) < cache_ttl:
        return cached["tags"]

    try:
        resp = discourse.t._(topic_id).json.get({})
        raw_tags = resp.get("tags", []) or []
        # Discourse may return tag strings or tag objects depending on version/config.
        if raw_tags and isinstance(raw_tags[0], dict):
            log.debug("topic %s tags are objects; extracting 'name' field", topic_id)
            tags = [t["name"] for t in raw_tags if "name" in t]
        else:
            tags = list(raw_tags)
    except Exception as exc:
        log.warning("Failed to look up topic %s: %s", topic_id, exc)
        return cached["tags"] if cached else []

    cache[key] = {"tags": tags, "fetched_at": time.time()}
    return tags


def filter_one_to_bytes(base_url: str, discourse, series_filename: str,
                        tag_cache: dict, tag_groups: dict | None = None,
                        cache_ttl: int = 3600, log=None) -> bytes:
    """
    Fetch the Discourse global events.ics and return ICS bytes for one series.

    Intended for the web route (on-demand).  Uses an in-memory tag_cache dict
    supplied by the caller so topic-tag lookups persist across requests within
    the same process.  No file I/O.

    base_url        — Discourse site root
    discourse       — _RateLimitedDiscourse instance
    series_filename — key in tag_groups, e.g. "grandprix.ics"
    tag_cache       — caller-owned dict (mutated in place) for topic tag caching
    tag_groups      — {filename: tag_slug} mapping; defaults to DEFAULT_TAG_GROUPS
    cache_ttl       — seconds before a cached topic-tags entry is re-fetched
    log             — logger
    """
    import logging
    if log is None:
        log = logging.getLogger(__name__)

    if tag_groups is None:
        tag_groups = DEFAULT_TAG_GROUPS
    required_tag = tag_groups[series_filename]

    log.debug("Fetching master feed for %s", series_filename)
    resp = requests.get(f"{base_url}/discourse-post-event/events.ics", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    master_cal = Calendar.from_ical(resp.content)

    cal = Calendar()
    for key, value in master_cal.items():
        if key != "VEVENT":
            cal.add(key, value)

    for component in master_cal.walk("VEVENT"):
        topic_id = extract_topic_id(component)
        if topic_id is None:
            continue
        if required_tag in set(get_topic_tags(topic_id, tag_cache, discourse, cache_ttl, log)):
            cal.add_component(component)

    log.debug("Built %s (%d events)", series_filename, len(cal.subcomponents))
    return cal.to_ical()


def filter_calendar(base_url: str, discourse, output_dir: Path,
                    cache_file: Path, tag_groups: dict | None = None,
                    cache_ttl: int = 3600, force_refresh: bool = False,
                    log=None) -> None:
    """
    Fetch the Discourse global events.ics, split by tag, write per-series files.

    base_url     — Discourse site root, e.g. "https://community.steeplechasers.org"
    discourse    — _RateLimitedDiscourse instance for topic tag API calls
    output_dir   — directory to write <tag>.ics files into
    cache_file   — JSON file used to cache topic→tags lookups between runs
    tag_groups   — {filename: tag_slug} mapping; defaults to DEFAULT_TAG_GROUPS
    cache_ttl    — seconds before a cached topic-tags entry is re-fetched
    force_refresh — ignore cached topic tags entirely this run
    log          — logger (uses a module-level fallback when None)
    """
    import logging
    if log is None:
        log = logging.getLogger(__name__)

    if tag_groups is None:
        tag_groups = DEFAULT_TAG_GROUPS

    lock = InterProcessLock("/tmp/discourse-calendar-filter.lock")
    lock.acquire()

    master_feed_url = f"{base_url}/discourse-post-event/events.ics"
    cache = {} if force_refresh else load_cache(cache_file)

    log.debug("Fetching master feed: %s", master_feed_url)
    resp = requests.get(master_feed_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    master_cal = Calendar.from_ical(resp.content)

    output_cals = {}
    for filename in tag_groups:
        cal = Calendar()
        for key, value in master_cal.items():
            if key != "VEVENT":
                cal.add(key, value)
        output_cals[filename] = cal

    matched = 0
    unmatched = 0

    for component in master_cal.walk("VEVENT"):
        topic_id = extract_topic_id(component)
        if topic_id is None:
            unmatched += 1
            continue

        topic_tags = set(get_topic_tags(topic_id, cache, discourse, cache_ttl, log))
        if not topic_tags:
            unmatched += 1
            continue

        hit = False
        for filename, required_tag in tag_groups.items():
            if required_tag in topic_tags:
                output_cals[filename].add_component(component)
                hit = True
        if hit:
            matched += 1
        else:
            unmatched += 1

    save_cache(cache, cache_file)

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, cal in output_cals.items():
        out_path = output_dir / filename
        out_path.write_bytes(cal.to_ical())
        log.debug("Wrote %s (%d events)", out_path, len(cal.subcomponents))

    lock.release()
    log.debug(
        "Done. %d events matched a tag group, %d skipped (no topic/tag match).",
        matched, unmatched,
    )
