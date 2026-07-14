"""
community_events — import WordPress events into Discourse as tagged topics

Each CSV row (from export_fsrc_events.py) becomes a Discourse topic in the
configured category, tagged from the 'tags' column, and with a discourse-calendar
[event] block so the topic appears in the global events.ics feed.
"""

import csv
import json
import logging
from pathlib import Path


def _parse_dt(s: str) -> str:
    """Convert '2026-01-15 10:00:00' to '2026-01-15T10:00:00' for [event] BBCode."""
    return s.strip().replace(' ', 'T')


def _build_topic_body(row: dict) -> str:
    """Build the Discourse topic body (Markdown + [event] BBCode) for one event row."""
    start_raw = row.get('start_date', '').strip()
    end_raw = row.get('end_date', '').strip()
    all_day = row.get('all_day', '').lower() in ('true', '1', 'yes')

    website = row.get('website', '').strip()
    venue = row.get('venue', '').strip()

    extra = ''
    if website:
        extra += f' url="{website}"'
    if venue:
        extra += f' location="{venue}"'

    if all_day:
        start_val = start_raw[:10] if start_raw else ''
        end_val = end_raw[:10] if end_raw else start_val
        event_line = (
            f'[event start="{start_val}" end="{end_val}"'
            f' all_day="true" status="public" timezone="America/New_York"{extra}]\n[/event]'
        )
    else:
        start_val = _parse_dt(start_raw) if start_raw else ''
        end_val = _parse_dt(end_raw) if end_raw else start_val
        event_line = (
            f'[event start="{start_val}" end="{end_val}"'
            f' status="public" timezone="America/New_York"{extra}]\n[/event]'
        )

    parts = [event_line]

    if row.get('image_url'):
        parts.append(f"\n![]({row['image_url']})")

    if row.get('description'):
        parts.append(f"\n{row['description']}")

    return "\n".join(parts)


def _fetch_known_tags(discourse) -> set[str]:
    """Return the set of tag slugs that already exist in Discourse."""
    resp = discourse.tags.json.get({})
    return {t['name'] for t in resp.get('tags', []) if t.get('name')}


def import_events(interest: str, csv_file: str, category_id: int,
                  state_file: str, discourse, base_url: str,
                  dry_run: bool = False, log=None) -> None:
    """
    Read csv_file and create one Discourse topic per row.

    Idempotent: state_file is a JSON map of WordPress event ID → created topic info.
    Rows whose IDs are already in state_file are skipped, so re-runs are safe.

    Pre-flight: fetches all existing Discourse tags and aborts if any tag in the
    CSV is unknown, preventing accidental tag creation by the admin API key.

    interest      — interest name (used only for logging)
    csv_file      — path to CSV from export_fsrc_events.py
    category_id   — Discourse category ID to post into
    state_file    — JSON file tracking {wp_id: {topic_id, url, title}}
    discourse     — _RateLimitedDiscourse instance from make_discourse_client()
    base_url      — Discourse site root, e.g. "https://community.steeplechasers.org"
    dry_run       — print what would be posted without actually posting
    log           — logger; defaults to module logger
    """
    if log is None:
        log = logging.getLogger(__name__)

    state_path = Path(state_file)
    state: dict = json.loads(state_path.read_text()) if state_path.exists() else {}

    with open(csv_file, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    # Pre-flight: collect every tag the CSV wants to use, check against Discourse.
    log.info('Fetching existing Discourse tags for pre-flight check...')
    known_tags = _fetch_known_tags(discourse)
    csv_tags: set[str] = set()
    for row in rows:
        csv_tags.update(t.strip() for t in row.get('tags', '').split(';') if t.strip())
    unknown = csv_tags - known_tags
    if unknown:
        print('ERROR: the following tags in the CSV do not exist in Discourse:')
        for tag in sorted(unknown):
            print(f'  {tag}')
        print('Create them in Discourse first (or add overrides in CATEGORY_TAG_OVERRIDES), then re-run.')
        return

    created = skipped = errors = 0

    for row in rows:
        wp_id = str(row.get('id', '')).strip()
        title = row.get('title', '').strip()
        if not wp_id or not title:
            log.warning('Skipping row with missing id or title: %r', row)
            continue

        if wp_id in state:
            log.debug('Skipping already-imported event %s: %s', wp_id, title)
            skipped += 1
            continue

        tags = [t.strip() for t in row.get('tags', '').split(';') if t.strip()]
        raw = _build_topic_body(row)

        if dry_run:
            print(f'  [DRY RUN] {title}')
            print(f'            tags={tags}  category={category_id}')
            print(f'            body[:80]: {raw[:80]!r}')
            created += 1
            continue

        try:
            result = discourse.posts.post({
                'title': title,
                'raw': raw,
                'category': category_id,
                'tags': tags,
            })
            topic_id = result.get('topic_id')
            topic_slug = result.get('topic_slug', '')
            topic_url = f'{base_url}/t/{topic_slug}/{topic_id}'
            state[wp_id] = {'topic_id': topic_id, 'url': topic_url, 'title': title}
            state_path.write_text(json.dumps(state, indent=2))
            log.info('Created: %s → %s', title, topic_url)
            created += 1
        except Exception as exc:
            log.error("Error posting '%s': %s", title, exc)
            errors += 1

    print(f'\nDone. Created: {created}, Skipped: {skipped}, Errors: {errors}')
