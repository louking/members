#!/usr/bin/env python3
"""
Export 2026 events from steeplechasers.org (The Events Calendar Pro REST API)
into a CSV suitable for review and later import as Discourse topics.

Usage:
    python3 export_fsrc_events.py

Output:
    fsrc_events_2026.csv  (in the current directory)

Notes:
- Uses the public, unauthenticated REST endpoint, so no WP credentials needed
  (this only reads published events, same as what a site visitor sees).
- Filters by start_date/end_date to the 2026 calendar year and paginates
  through all results.
- Category -> tag mapping is a simple lowercase/hyphenate slugify of each
  category name. Edit `CATEGORY_TAG_OVERRIDES` below once you've decided on
  your real tag scheme, then re-run.
"""

import csv
import re
import sys
import time
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlencode

import requests

BASE_URL = "https://steeplechasers.org/wp-json/tribe/events/v1/events"
YEAR_START = "2026-01-01 00:00:00"
YEAR_END = "2026-12-31 23:59:59"
PER_PAGE = 50
OUTPUT_FILE = "fsrc_events_2026.csv"

# Key = WordPress category slug (category['slug'] in the API response).
# Value = Discourse tag slug to use instead of the WP slug.
# Categories not listed use the WP slug directly as the Discourse tag.
CATEGORY_TAG_OVERRIDES = {
    "cat-racing-team": "racing-team",      # WP prefixes Racing Team slug with "cat-"
    "lowkey": "lowkey-race",
    "fsrc-volunteers-needed": "volunteers-needed",
    
    # remove these categories
    "race": "",
    "steeps-race": "",
    
}


def slugify(name: str) -> str:
    """Fallback slug for categories that are missing a slug field."""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def category_to_tag(cat: dict) -> str:
    wp_slug = cat.get("slug") or slugify(cat.get("name", ""))
    return CATEGORY_TAG_OVERRIDES.get(wp_slug, wp_slug)


def _strip_tribe_widgets(html_text: str) -> str:
    """Remove WordPress tribe-events widget <div> blocks from event HTML.

    Strips any <div> whose class list contains a class starting with 'tribe-',
    including all nested content. Leaves <p> and other non-widget tags intact.
    """
    class _Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.depth = 0  # >0 while inside a tribe- div being skipped

        def handle_starttag(self, tag, attrs):
            if self.depth > 0:
                if tag == 'div':
                    self.depth += 1
                return
            if tag == 'div':
                cls = dict(attrs).get('class', '') or ''
                if any(c.startswith('tribe-') for c in cls.split()):
                    self.depth = 1
                    return
            attr_str = ''.join(
                f' {k}="{v}"' if v is not None else f' {k}'
                for k, v in attrs
            )
            self.parts.append(f'<{tag}{attr_str}>')

        def handle_endtag(self, tag):
            if self.depth > 0:
                if tag == 'div':
                    self.depth -= 1
                return
            self.parts.append(f'</{tag}>')

        def handle_data(self, data):
            if self.depth == 0:
                self.parts.append(data)

    parser = _Parser()
    parser.feed(html_text)
    return ''.join(parser.parts)


def collapse_ws(text: str) -> str:
    """Collapse all whitespace runs (including newlines) to a single space.

    HTML renders multiple whitespace chars identically, so this is display-neutral
    and keeps each CSV row on a single line.
    """
    return re.sub(r"\s+", " ", text).strip() if text else ""


def format_venue(venue_data: dict) -> str:
    if not venue_data:
        return ""
    name = unescape(venue_data.get("venue", "") or "")
    city = venue_data.get("city", "") or ""
    state = venue_data.get("state", "") or ""
    return ", ".join(p for p in [name, city, state] if p)



def fetch_all_events():
    events = []
    page = 1
    while True:
        params = {
            "start_date": YEAR_START,
            "end_date": YEAR_END,
            "per_page": PER_PAGE,
            "page": page,
        }
        url = f"{BASE_URL}?{urlencode(params)}"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 404:
            # TEC REST API returns 404 once you page past the last page
            break
        resp.raise_for_status()
        data = resp.json()

        batch = data.get("events", [])
        events.extend(batch)

        total_pages = data.get("total_pages", 1)
        print(f"Fetched page {page}/{total_pages} ({len(batch)} events)", file=sys.stderr)

        if page >= total_pages or not batch:
            break
        page += 1
        time.sleep(0.3)  # be polite to the server

    return events


def main():
    events = fetch_all_events()
    print(f"Total events fetched: {len(events)}", file=sys.stderr)

    rows = []
    for ev in events:
        cat_dicts = ev.get("categories", []) or []
        tags = sorted(t for c in cat_dicts if c.get("slug") or c.get("name") for t in [category_to_tag(c)] if t)
        cat_names = [c.get("name", "") for c in cat_dicts if c.get("name")]

        venue = format_venue(ev.get("venue") or {})
        image_url = (ev.get("image") or {}).get("url") or ""

        rows.append({
            "id": ev.get("id"),
            "title": unescape(ev.get("title", "")),
            "start_date": ev.get("start_date", ""),
            "end_date": ev.get("end_date", ""),
            "all_day": ev.get("all_day", False),
            "url": ev.get("url", ""),
            "website": ev.get("website", "") or "",
            "venue": venue,
            "image_url": image_url,
            "categories_raw": "; ".join(cat_names),
            "tags": "; ".join(tags),
            "description": collapse_ws(_strip_tribe_widgets(ev.get("description", ""))),
        })

    rows.sort(key=lambda r: r["start_date"])

    fieldnames = [
        "id", "title", "start_date", "end_date", "all_day",
        "url", "website", "venue", "image_url", "categories_raw", "tags", "description",
    ]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} events to {OUTPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
