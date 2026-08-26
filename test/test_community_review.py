'''
test_community_review - test members.community_review
=========================================================
'''

# standard
import logging
from datetime import datetime, timedelta, timezone

# pypi
import pytest
from flask import g

# homegrown
from members import community_review
from members.community_review import (
    _resolve_category, fetch_category_moderator_groups, fetch_pending_reviewables,
    send_group_pm, _parse_dt, _format_local, _humanize_reviewable_type, _reviewable_label,
    _build_notice_body, check_pending_reviews,
)
from members.model import db, LocalInterest, DiscourseReviewNotice
from loutilities.user.model import Interest
from fakediscourse import FakeDiscourse

log = logging.getLogger('test')


# ----------------------------------------------------------------------
# _resolve_category
# ----------------------------------------------------------------------

def test_resolve_category_finds_matching_slug():
    categories = [{'id': 1, 'slug': 'general'}, {'id': 2, 'slug': 'public-calendar-events'}]
    assert _resolve_category(categories, 'public-calendar-events')['id'] == 2


def test_resolve_category_returns_none_when_not_found():
    assert _resolve_category([{'slug': 'general'}], 'missing') is None


# ----------------------------------------------------------------------
# fetch_category_moderator_groups
# ----------------------------------------------------------------------

def test_fetch_category_moderator_groups_reads_moderating_group_ids():
    detail = {'category': {'moderating_group_ids': [1, 2],
                            # exemption-list fields; must NOT be read as moderator groups
                            'topic_posting_review_group_ids': [1, 3], 'reply_posting_review_group_ids': [3]}}
    discourse = FakeDiscourse({'c.10.show.json': detail})
    groups_by_id = {1: {'name': 'club-mods'}, 2: {'name': 'cal-mods'}, 3: {'name': 'preapproved-posters'}}
    assert fetch_category_moderator_groups(discourse, 10, groups_by_id) == ['cal-mods', 'club-mods']


def test_fetch_category_moderator_groups_empty_when_none_configured():
    discourse = FakeDiscourse({'c.10.show.json': {'category': {}}})
    assert fetch_category_moderator_groups(discourse, 10, {}) == []


def test_fetch_category_moderator_groups_excludes_unmessageable_group(caplog):
    # a group with "Who can message this group" = Nobody (messageable_level 0) can't
    # receive a PM at all, and including it alongside messageable groups would fail
    # the whole notice — so it's excluded here rather than left to fail at send time
    detail = {'category': {'moderating_group_ids': [1, 2]}}
    discourse = FakeDiscourse({'c.10.show.json': detail})
    groups_by_id = {1: {'name': 'club-mods', 'messageable_level': 3}, 2: {'name': 'preapproved-posters', 'messageable_level': 0}}
    with caplog.at_level(logging.WARNING):
        result = fetch_category_moderator_groups(discourse, 10, groups_by_id)
    assert result == ['club-mods']
    assert 'preapproved-posters' in caplog.text


# ----------------------------------------------------------------------
# fetch_pending_reviewables
# ----------------------------------------------------------------------

def test_fetch_pending_reviewables_resolves_submitter_username():
    resp = {
        'reviewables': [{'id': 1, 'target_created_by_id': 5}],
        'users': [{'id': 5, 'username': 'joe.runner'}],
    }
    discourse = FakeDiscourse({'review.json': resp})
    items = fetch_pending_reviewables(discourse, 10, log=log)
    assert items[0]['_submitted_by'] == 'joe.runner'


def test_fetch_pending_reviewables_submitter_none_when_unknown():
    resp = {'reviewables': [{'id': 1, 'target_created_by_id': 99}], 'users': []}
    discourse = FakeDiscourse({'review.json': resp})
    items = fetch_pending_reviewables(discourse, 10, log=log)
    assert items[0]['_submitted_by'] is None


def test_fetch_pending_reviewables_warns_when_response_looks_truncated(caplog):
    resp = {'reviewables': [{'id': i} for i in range(3)], 'users': []}
    discourse = FakeDiscourse({'review.json': resp})
    with caplog.at_level(logging.WARNING, logger='test'):
        fetch_pending_reviewables(discourse, 10, per_page=3, log=log)
    assert any('truncated' in r.message for r in caplog.records)


# ----------------------------------------------------------------------
# send_group_pm
# ----------------------------------------------------------------------

def test_send_group_pm_posts_private_message():
    captured = {}

    def post(body):
        captured.update(body)
        return {'ok': True}
    discourse = FakeDiscourse({'posts': post})

    send_group_pm(discourse, ['club-mods', 'cal-mods'], 'Subject', 'Body text')

    assert captured['archetype'] == 'private_message'
    assert captured['target_recipients'] == 'club-mods,cal-mods'
    assert captured['title'] == 'Subject'
    assert captured['raw'] == 'Body text'


# ----------------------------------------------------------------------
# _parse_dt / _format_local
# ----------------------------------------------------------------------

def test_parse_dt_handles_zulu_suffix():
    dt = _parse_dt('2026-07-19T16:31:39.483Z')
    assert dt == datetime(2026, 7, 19, 16, 31, 39, 483000, tzinfo=timezone.utc)


def test_format_local_matches_expected_shape():
    dt = datetime(2026, 7, 19, 16, 31, 39, tzinfo=timezone.utc)
    result = _format_local(dt)
    assert result == dt.astimezone().strftime('%Y-%m-%d %I:%M %p %Z')


# ----------------------------------------------------------------------
# _humanize_reviewable_type
# ----------------------------------------------------------------------

def test_humanize_reviewable_type_strips_reviewable_prefix():
    assert _humanize_reviewable_type('ReviewableQueuedPost') == 'Queued Post'


def test_humanize_reviewable_type_strips_namespace():
    assert _humanize_reviewable_type('Chat::ReviewableMessage') == 'Message'


# ----------------------------------------------------------------------
# _reviewable_label
# ----------------------------------------------------------------------

def test_reviewable_label_prefers_fancy_title_with_submitter():
    item = {'fancy_title': 'Grand Prix Race', '_submitted_by': 'joe.runner'}
    assert _reviewable_label(item) == 'Grand Prix Race (submitted by joe.runner)'


def test_reviewable_label_falls_back_to_payload_title():
    item = {'payload': {'title': 'Payload Title'}, '_submitted_by': None}
    assert _reviewable_label(item) == 'Payload Title'


def test_reviewable_label_falls_back_to_humanized_type():
    item = {'type': 'ReviewableFlaggedPost', '_submitted_by': None}
    assert _reviewable_label(item) == 'Flagged Post'


# ----------------------------------------------------------------------
# _build_notice_body
# ----------------------------------------------------------------------

def test_build_notice_body_new_items_heading():
    items = [{'id': 1, 'fancy_title': 'A Post', '_submitted_by': None, 'created_at': '2026-07-19T16:31:39.483Z'}]
    body = _build_notice_body('https://community.example.com', 'General', items, escalated=False)
    assert body.startswith('New pending review items in **General**:')
    assert '[A Post](https://community.example.com/review/1)' in body


def test_build_notice_body_escalated_heading():
    items = [{'id': 1, 'fancy_title': 'A Post', '_submitted_by': None, 'created_at': '2026-07-19T16:31:39.483Z'}]
    body = _build_notice_body('https://community.example.com', 'General', items, escalated=True)
    assert body.startswith('Still pending — escalation in **General**:')


# ----------------------------------------------------------------------
# check_pending_reviews (full orchestration)
# ----------------------------------------------------------------------

@pytest.fixture
def reviewsetup(bare_dbapp, monkeypatch, tmp_path):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()

    monkeypatch.setattr(community_review, 'COMMUNITY_LOCKFILE', str(tmp_path / 'lock'))
    return localinterest


def _iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')


def test_check_pending_reviews_notifies_escalates_and_resolves(reviewsetup):
    localinterest = reviewsetup
    now = datetime.now(timezone.utc)

    # pre-existing tracked item (id=3) escalates; id=4 is tracked but no longer pending (resolved)
    db.session.add(DiscourseReviewNotice(
        interest=localinterest, category_id=10, reviewable_id=3,
        first_notified_at=(now - timedelta(hours=40)).replace(tzinfo=None),
        last_notified_at=(now - timedelta(hours=30)).replace(tzinfo=None),
    ))
    db.session.add(DiscourseReviewNotice(
        interest=localinterest, category_id=10, reviewable_id=4,
        first_notified_at=(now - timedelta(hours=40)).replace(tzinfo=None),
        last_notified_at=(now - timedelta(hours=30)).replace(tzinfo=None),
    ))
    db.session.commit()

    reviewables = [
        {'id': 1, 'fancy_title': 'New item (old enough)', '_submitted_by': None,
         'created_at': _iso(now - timedelta(hours=3)), 'target_created_by_id': None},
        {'id': 2, 'fancy_title': 'Too new', '_submitted_by': None,
         'created_at': _iso(now - timedelta(minutes=10)), 'target_created_by_id': None},
        {'id': 3, 'fancy_title': 'Escalating item', '_submitted_by': None,
         'created_at': _iso(now - timedelta(hours=40)), 'target_created_by_id': None},
    ]

    responses = {
        'categories.json': {'category_list': {'categories': [
            {'id': 10, 'slug': 'public-calendar-events', 'name': 'Public Calendar Events'},
        ]}},
        'groups.json': lambda params: {'groups': [{'id': 1, 'name': 'club-mods'}, {'id': 2, 'name': 'cal-mods'}]}
                                       if params['page'] == 0 else {'groups': []},
        'c.10.show.json': {'category': {'moderating_group_ids': [1, 2]}},
        'review.json': {'reviewables': reviewables, 'users': []},
    }
    discourse = FakeDiscourse(responses)

    notified = []

    def fake_notify(discourse, group_names, subject, body):
        notified.append((group_names, subject, body))

    counts = check_pending_reviews('fsrc', discourse, ['public-calendar-events'],
                                   'https://community.example.com',
                                   pending_hours=2.0, escalation_hours=24.0,
                                   notify_fn=fake_notify, log=log)

    assert counts == {'checked': 3, 'notified': 1, 'escalated': 1, 'resolved': 1, 'errors': 0}
    assert len(notified) == 1
    group_names, subject, body = notified[0]
    assert group_names == ['cal-mods', 'club-mods']
    assert 'New item (old enough)' in body
    assert 'Escalating item' in body
    assert 'Too new' not in body

    rows = {r.reviewable_id: r for r in DiscourseReviewNotice.query.all()}
    assert set(rows.keys()) == {1, 3}
    assert rows[3].last_notified_at > (now - timedelta(hours=1)).replace(tzinfo=None)


def test_check_pending_reviews_dry_run_makes_no_changes(reviewsetup):
    localinterest = reviewsetup
    now = datetime.now(timezone.utc)

    reviewables = [{'id': 1, 'fancy_title': 'New item', '_submitted_by': None,
                    'created_at': _iso(now - timedelta(hours=3)), 'target_created_by_id': None}]
    responses = {
        'categories.json': {'category_list': {'categories': [
            {'id': 10, 'slug': 'public-calendar-events', 'name': 'Public Calendar Events'},
        ]}},
        'groups.json': lambda params: {'groups': [{'id': 1, 'name': 'club-mods'}]} if params['page'] == 0 else {'groups': []},
        'c.10.show.json': {'category': {'moderating_group_ids': [1]}},
        'review.json': {'reviewables': reviewables, 'users': []},
    }
    discourse = FakeDiscourse(responses)

    def fail_notify(*args, **kwargs):
        raise AssertionError('notify_fn should not be called in dry_run')

    counts = check_pending_reviews('fsrc', discourse, ['public-calendar-events'],
                                   'https://community.example.com',
                                   notify_fn=fail_notify, dry_run=True, log=log)

    assert counts['notified'] == 1
    assert DiscourseReviewNotice.query.count() == 0


def test_check_pending_reviews_unknown_category_slug_counts_as_error(reviewsetup):
    responses = {
        'categories.json': {'category_list': {'categories': []}},
        'groups.json': lambda params: {'groups': []},
    }
    discourse = FakeDiscourse(responses)

    counts = check_pending_reviews('fsrc', discourse, ['missing-category'],
                                   'https://community.example.com', log=log)

    assert counts['errors'] == 1
    assert counts['checked'] == 0
