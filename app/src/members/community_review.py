"""
community_review — notify category moderator groups about pending Discourse review-queue items

Discourse's per-category posting-review settings only surface an on-site badge to
non-staff category moderators; they never email or PM them. This module polls the
Admin API review queue for a set of categories and sends a Discourse PM to each
category's configured moderator group(s) once items have been pending longer than
a threshold, then re-notifies (escalates) any still-pending items at a longer
interval. All datetimes here are UTC; DB columns store naive UTC values.
"""

import logging
import re
from datetime import datetime, timedelta, timezone

from fasteners import InterProcessLock
from flask import g

from .community import COMMUNITY_LOCKFILE
from .community_taxonomy import fetch_categories, fetch_groups
from .model import db, DiscourseReviewNotice, localinterest_query_params


def _resolve_category(categories: list[dict], slug: str) -> dict | None:
    """Find a category dict (top-level or subcategory) by slug."""
    for c in categories:
        if c.get('slug') == slug:
            return c
    return None


def fetch_category_moderator_groups(discourse, category_id: int, group_id_to_name: dict) -> list[str]:
    """Return the moderator group name(s) configured for a category.

    Discourse exposes this per-category, as group ids, via GET /c/{id}/show.json's
    topic_posting_review_group_ids and reply_posting_review_group_ids (not on the
    GET /categories.json list response, which doesn't include these fields). A
    category can have more than one group configured — the two lists are set
    independently (new topics vs. replies) — so both are unioned since either
    implies that group reviews items pending in this category. [] if none configured.
    """
    detail = discourse.c._(str(category_id)).show.json.get({})
    category = detail.get('category', {})
    group_ids = set(category.get('topic_posting_review_group_ids') or [])
    group_ids.update(category.get('reply_posting_review_group_ids') or [])
    return sorted(group_id_to_name[gid] for gid in group_ids if gid in group_id_to_name)


def fetch_pending_reviewables(discourse, category_id: int, per_page: int = 50, log=None) -> list[dict]:
    """Fetch pending reviewables for category_id from GET /review.json.

    A single, generously-sized request rather than looping over a 'page' param:
    /review.json's pagination shape isn't documented, and an earlier version of
    this that looped speculatively on "empty page means done" never actually
    terminated against the live instance — Discourse kept returning the same
    non-empty page regardless of 'page', burning the rate limit. A single
    category's review queue on a small club forum should never come close to
    per_page anyway; warns (doesn't raise) if a response looks truncated.

    Each returned item gets a '_submitted_by' key (username, or None if
    unknown) resolved from the response's sibling 'users' list via
    target_created_by_id, for use in a human-readable notice.
    """
    if log is None:
        log = logging.getLogger(__name__)
    resp = discourse.review.json.get({'status': 'pending', 'category_id': category_id, 'per_page': per_page})
    items = resp.get('reviewables', [])
    users_by_id = {u['id']: u for u in resp.get('users', [])}
    for item in items:
        submitter = users_by_id.get(item.get('target_created_by_id'))
        item['_submitted_by'] = submitter['username'] if submitter else None
    if len(items) >= per_page:
        log.warning('fetch_pending_reviewables(): category %s returned %d items (>= per_page=%d); '
                     'results may be truncated', category_id, len(items), per_page)
    return items


def send_group_pm(discourse, group_names: list[str], subject: str, body: str) -> dict:
    """Send a Discourse PM to one or more groups. Kept as its own function so
    email/webhook delivery can be swapped in later without touching orchestration.
    """
    return discourse.posts.post({
        'archetype': 'private_message',
        'target_recipients': ','.join(group_names),
        'title': subject,
        'raw': body,
    })


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def _format_local(dt: datetime) -> str:
    """Format a UTC datetime in the container's local timezone (the TZ env var,
    e.g. America/New_York, set in docker-compose for the app/crond services) rather
    than raw UTC/Zulu, which isn't meaningful to a human reading the PM.
    """
    return dt.astimezone().strftime('%Y-%m-%d %I:%M %p %Z')


def _humanize_reviewable_type(reviewable_type: str) -> str:
    """'ReviewableQueuedPost' -> 'Queued Post', 'Chat::ReviewableMessage' -> 'Message'."""
    name = reviewable_type.rsplit('::', 1)[-1].removeprefix('Reviewable')
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', name) or reviewable_type


def _reviewable_label(item: dict) -> str:
    """Best-effort human-readable label for a reviewable, for use in the notice PM.

    A bare reviewable id means nothing to a moderator reading the PM, so this
    prefers the actual post/topic title (fancy_title, falling back to
    payload.title) and who submitted it ('_submitted_by', set by
    fetch_pending_reviewables from the response's target_created_by_id). Falls
    back to a humanized reviewable type (e.g. "Flagged Post") for reviewable
    types that aren't a post/topic and so have no title (e.g. a new-user review).
    """
    title = item.get('fancy_title') or (item.get('payload') or {}).get('title')
    label = title or _humanize_reviewable_type(item.get('type', 'item'))
    submitter = item.get('_submitted_by')
    return f'{label} (submitted by {submitter})' if submitter else label


def _build_notice_body(base_url: str, category_name: str, items: list[dict], escalated: bool) -> str:
    heading = 'Still pending — escalation' if escalated else 'New pending review items'
    lines = [f'{heading} in **{category_name}**:', '']
    for item in items:
        when = _format_local(_parse_dt(item['created_at']))
        lines.append(f"- [{_reviewable_label(item)}]({base_url}/review/{item['id']}) — pending since {when}")
    return '\n'.join(lines)


def check_pending_reviews(interest: str, discourse, category_slugs: list[str], base_url: str,
                           pending_hours: float = 2.0, escalation_hours: float = 24.0,
                           notify_fn=send_group_pm, dry_run: bool = False, log=None) -> dict:
    """
    Poll the Discourse review queue for category_slugs, notifying each category's
    moderator group(s) about items pending longer than pending_hours, and re-notifying
    (escalating) any still pending after escalation_hours since the last notice.

    State is tracked in the DiscourseReviewNotice table, scoped by interest, so
    re-runs don't re-notify on every pass for the same item.

    interest        — interest name (used to scope DB state)
    discourse        — _RateLimitedDiscourse instance from make_discourse_client()
    category_slugs   — Discourse category slugs to poll
    base_url         — Discourse site root, e.g. "https://community.steeplechasers.org"
    pending_hours    — minimum age before a first notice is sent
    escalation_hours — how long after the last notice to re-notify if still pending
    notify_fn        — callable(discourse, group_names, subject, body); default sends a Discourse PM
    dry_run          — compute what would be sent/tracked without sending or writing state
    log              — logger; defaults to module logger

    :rtype: dict of counts: checked, notified, escalated, resolved, errors
    """
    if log is None:
        log = logging.getLogger(__name__)

    # interprocess lock so an overlapping community command can't share Discourse's
    # real rate limit with this one (each process has its own in-memory
    # _RateLimiter, with no cross-process coordination) — same lockfile as
    # CommunitySyncManager.start_import() in community.py, deliberately, since
    # it's the same underlying Discourse-side rate limit being protected
    # regardless of which community command is running
    with InterProcessLock(COMMUNITY_LOCKFILE):
        g.interest = interest
        localinterest = localinterest_query_params()['interest']

        counts = {'checked': 0, 'notified': 0, 'escalated': 0, 'resolved': 0, 'errors': 0}
        now = datetime.now(timezone.utc)
        pending_delta = timedelta(hours=pending_hours)
        escalation_delta = timedelta(hours=escalation_hours)

        categories = fetch_categories(discourse)
        group_id_to_name = {grp['id']: grp['name'] for grp in fetch_groups(discourse)}

        for slug in category_slugs:
            category = _resolve_category(categories, slug)
            if not category:
                log.warning('check_pending_reviews(): category slug %r not found', slug)
                counts['errors'] += 1
                continue

            category_id = category['id']
            group_names = fetch_category_moderator_groups(discourse, category_id, group_id_to_name)
            if not group_names:
                log.warning('check_pending_reviews(): category %r (id=%s) has no moderator group configured', slug, category_id)
                counts['errors'] += 1
                continue

            try:
                reviewables = fetch_pending_reviewables(discourse, category_id, log=log)
            except Exception as exc:
                log.error('check_pending_reviews(): error fetching reviewables for category %r: %s', slug, exc)
                counts['errors'] += 1
                continue

            counts['checked'] += len(reviewables)
            pending_ids = {item['id'] for item in reviewables}

            existing = {
                row.reviewable_id: row for row in
                DiscourseReviewNotice.query.filter_by(interest=localinterest, category_id=category_id).all()
            }

            to_notify = []
            to_escalate = []
            for item in reviewables:
                age = now - _parse_dt(item['created_at'])
                if age < pending_delta:
                    continue
                row = existing.get(item['id'])
                if row is None:
                    to_notify.append(item)
                elif now - row.last_notified_at.replace(tzinfo=timezone.utc) >= escalation_delta:
                    to_escalate.append((item, row))

            if to_notify or to_escalate:
                body_items = to_notify + [item for item, _ in to_escalate]
                subject = f"Pending review items in {category['name']}"
                body = _build_notice_body(base_url, category['name'], body_items, escalated=not to_notify)
                log.info('check_pending_reviews(): category %r: notifying %s (%d new, %d escalated)',
                          slug, group_names, len(to_notify), len(to_escalate))
                if dry_run:
                    print(f"  [DRY RUN] would notify {group_names}: {len(to_notify)} new, {len(to_escalate)} escalated")
                else:
                    try:
                        notify_fn(discourse, group_names, subject, body)
                    except Exception as exc:
                        log.error('check_pending_reviews(): error sending notification for category %r: %s', slug, exc)
                        counts['errors'] += 1
                        continue

                    stored_now = now.replace(tzinfo=None)
                    for item in to_notify:
                        db.session.add(DiscourseReviewNotice(
                            interest=localinterest, category_id=category_id, reviewable_id=item['id'],
                            first_notified_at=stored_now, last_notified_at=stored_now,
                        ))
                    for item, row in to_escalate:
                        row.last_notified_at = stored_now

                counts['notified'] += len(to_notify)
                counts['escalated'] += len(to_escalate)

            # clean up items that are no longer pending (approved/rejected elsewhere)
            for reviewable_id, row in existing.items():
                if reviewable_id not in pending_ids:
                    log.info('check_pending_reviews(): review #%s in category %r resolved', reviewable_id, slug)
                    if not dry_run:
                        db.session.delete(row)
                    counts['resolved'] += 1

        if not dry_run:
            db.session.commit()

        return counts
