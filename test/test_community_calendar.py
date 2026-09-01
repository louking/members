'''
test_community_calendar - test members.community_calendar
=========================================================
'''

# standard
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

# pypi
import pytest

# homegrown
from members.community_calendar import (
    _tag_names, _parse_event_datetime, _fetch_location, fetch_event_locations,
    _build_vevent, _fetch_events, filter_tags_to_bytes,
)
from fakediscourse import FakeDiscourse

log = logging.getLogger('test')


# ----------------------------------------------------------------------
# _tag_names
# ----------------------------------------------------------------------

def test_tag_names_handles_object_tags():
    tags = [{'id': 20, 'name': 'grand-prix', 'slug': 'grand-prix'}, {'id': 21, 'name': 'races'}]
    assert _tag_names(tags) == {'grand-prix', 'races'}


def test_tag_names_handles_string_tags():
    assert _tag_names(['grand-prix', 'races']) == {'grand-prix', 'races'}


def test_tag_names_handles_empty():
    assert _tag_names([]) == set()
    assert _tag_names(None) == set()


# ----------------------------------------------------------------------
# _parse_event_datetime
# ----------------------------------------------------------------------

def test_parse_event_datetime_offset_aware_with_microseconds():
    dt = _parse_event_datetime('2026-03-03T17:30:00.000-05:00', 'America/New_York')
    assert dt == datetime(2026, 3, 3, 17, 30, tzinfo=ZoneInfo('America/New_York'))


def test_parse_event_datetime_offset_aware_without_microseconds():
    dt = _parse_event_datetime('2026-03-03T17:30:00-05:00', 'America/New_York')
    assert dt == datetime(2026, 3, 3, 17, 30, tzinfo=ZoneInfo('America/New_York'))


def test_parse_event_datetime_naive_localized_to_tz_name():
    dt = _parse_event_datetime('2026-02-02T18:00:00', 'America/New_York')
    assert dt == datetime(2026, 2, 2, 18, 0, tzinfo=ZoneInfo('America/New_York'))
    assert dt.tzinfo == ZoneInfo('America/New_York')


def test_parse_event_datetime_defaults_to_utc_when_no_tz_name():
    dt = _parse_event_datetime('2026-02-02T18:00:00', '')
    assert dt.tzinfo == ZoneInfo('UTC')


def test_parse_event_datetime_invalid_raises():
    with pytest.raises(ValueError):
        _parse_event_datetime('not-a-date', 'UTC')


def test_parse_event_datetime_bare_date_returns_plain_date():
    d = _parse_event_datetime('2026-09-26', 'America/New_York')
    assert d == date(2026, 9, 26)
    assert not isinstance(d, datetime)


# ----------------------------------------------------------------------
# _fetch_location / fetch_event_locations
# ----------------------------------------------------------------------

def test_fetch_location_extracts_location_from_raw():
    responses = {'posts.884.json': {'raw': '[event start="x" location="Baker Park, Frederick, MD"][/event]'}}
    discourse = FakeDiscourse(responses)
    assert _fetch_location(discourse, 884, log) == 'Baker Park, Frederick, MD'


def test_fetch_location_returns_none_when_no_location():
    responses = {'posts.884.json': {'raw': '[event start="x"][/event]'}}
    discourse = FakeDiscourse(responses)
    assert _fetch_location(discourse, 884, log) is None


def test_fetch_location_returns_none_on_error():
    def raiser(_params):
        raise RuntimeError('boom')
    discourse = FakeDiscourse({'posts.884.json': raiser})
    assert _fetch_location(discourse, 884, log) is None


def test_fetch_event_locations_empty_post_ids_returns_empty():
    assert fetch_event_locations(FakeDiscourse({}), [], None, log) == {}


def test_fetch_event_locations_fallback_uses_per_post_rest_calls():
    responses = {
        'posts.884.json': {'raw': '[event location="Venue A"][/event]'},
        'posts.973.json': {'raw': '[event][/event]'},
    }
    discourse = FakeDiscourse(responses)
    result = fetch_event_locations(discourse, [884, 973], None, log)
    assert result == {884: 'Venue A'}


# run_query_paged() (community.py) logs via current_app.logger, so anything that
# reaches it needs a pushed app context even though these tests never touch the db

def test_fetch_event_locations_query_id_joins_post_ids_as_comma_string(bareapp):
    calls = []
    responses = {}

    def run(body):
        calls.append(body)
        params = body['params']
        assert params['post_ids'] == '884,973'
        return {
            'columns': ['id', 'raw'],
            'rows': [[884, '[event location="Venue A"][/event]'], [973, '[event][/event]']],
            'result_count': 2,
        }
    responses['admin.plugins.explorer.queries.42.run'] = run
    discourse = FakeDiscourse(responses)

    with bareapp.app_context():
        result = fetch_event_locations(discourse, [884, 973], 42, log)
    assert result == {884: 'Venue A'}
    assert len(calls) == 1


def test_fetch_event_locations_warns_on_missing_ids(bareapp, caplog):
    def run(body):
        return {'columns': ['id', 'raw'], 'rows': [[884, '']], 'result_count': 1}
    discourse = FakeDiscourse({'admin.plugins.explorer.queries.42.run': run})

    with caplog.at_level(logging.WARNING, logger='test'), bareapp.app_context():
        fetch_event_locations(discourse, [884, 973], 42, log)
    assert any('not returned' in r.message for r in caplog.records)


# ----------------------------------------------------------------------
# _build_vevent
# ----------------------------------------------------------------------

def test_build_vevent_builds_expected_fields():
    event = {
        'id': 5,
        'name': 'Grand Prix Race',
        'timezone': 'America/New_York',
        'starts_at': '2026-03-03T17:30:00.000-05:00',
        'ends_at': '2026-03-03T19:30:00.000-05:00',
        'post': {'url': '/t/grand-prix-race/123'},
    }
    vevent = _build_vevent(event, 'https://community.steeplechasers.org', location='Baker Park')
    assert str(vevent['SUMMARY']) == 'Grand Prix Race'
    assert str(vevent['URL']) == 'https://community.steeplechasers.org/t/grand-prix-race/123'
    assert str(vevent['UID']) == 'discourse-event-5@community.steeplechasers.org'
    assert str(vevent['LOCATION']) == 'Baker Park'


def test_build_vevent_falls_back_to_topic_title_when_no_name():
    event = {
        'id': 6,
        'timezone': 'UTC',
        'starts_at': '2026-03-03T17:30:00',
        'ends_at': '2026-03-03T19:30:00',
        'post': {'url': '/t/some-topic/6', 'topic': {'title': 'Some Topic'}},
    }
    vevent = _build_vevent(event, 'https://community.steeplechasers.org')
    assert str(vevent['SUMMARY']) == 'Some Topic'
    assert 'LOCATION' not in vevent


def test_build_vevent_all_day_event_uses_date_values_with_exclusive_end():
    event = {
        'id': 7,
        'name': 'Club Picnic',
        'timezone': 'America/New_York',
        'starts_at': '2026-09-26',
        'ends_at': '2026-09-26',
        'post': {'url': '/t/club-picnic/7'},
    }
    vevent = _build_vevent(event, 'https://community.steeplechasers.org')
    assert vevent['DTSTART'].dt == date(2026, 9, 26)
    # RFC 5545: all-day DTEND is exclusive, so a same-day event ends the next day
    assert vevent['DTEND'].dt == date(2026, 9, 27)


def test_build_vevent_all_day_event_without_ends_at():
    event = {
        'id': 8,
        'name': 'Registration Opens',
        'timezone': 'America/New_York',
        'starts_at': '2026-09-26',
        'post': {'url': '/t/registration-opens/8'},
    }
    vevent = _build_vevent(event, 'https://community.steeplechasers.org')
    assert vevent['DTSTART'].dt == date(2026, 9, 26)
    assert vevent['DTEND'].dt == date(2026, 9, 27)


def test_build_vevent_multi_day_all_day_event_keeps_end_date():
    event = {
        'id': 9,
        'name': 'Race Weekend',
        'timezone': 'America/New_York',
        'starts_at': '2026-09-26',
        'ends_at': '2026-09-28',
        'post': {'url': '/t/race-weekend/9'},
    }
    vevent = _build_vevent(event, 'https://community.steeplechasers.org')
    assert vevent['DTSTART'].dt == date(2026, 9, 26)
    assert vevent['DTEND'].dt == date(2026, 9, 28)


# ----------------------------------------------------------------------
# _fetch_events
# ----------------------------------------------------------------------

def test_fetch_events_returns_events_list():
    responses = {'discourse-post-event.events': {'events': [{'id': 1}, {'id': 2}]}}
    discourse = FakeDiscourse(responses)
    events = _fetch_events(discourse, date(2026, 1, 1), date(2026, 12, 31), log)
    assert [e['id'] for e in events] == [1, 2]


def test_fetch_events_handles_missing_events_key():
    discourse = FakeDiscourse({'discourse-post-event.events': {}})
    assert _fetch_events(discourse, None, None, log) == []


# ----------------------------------------------------------------------
# filter_tags_to_bytes
# ----------------------------------------------------------------------

def _event(id, tags, name='Race'):
    return {
        'id': id,
        'name': name,
        'timezone': 'America/New_York',
        'starts_at': '2026-03-03T17:30:00-05:00',
        'ends_at': '2026-03-03T19:30:00-05:00',
        'post': {'id': id * 100, 'url': f'/t/race-{id}/{id}', 'topic': {'tags': tags}},
    }


def test_filter_tags_to_bytes_filters_by_union_of_tags():
    events = [_event(1, ['grand-prix']), _event(2, ['social']), _event(3, ['grand-prix', 'social'])]
    responses = {
        'discourse-post-event.events': {'events': events},
        'posts.100.json': {'raw': ''},
        'posts.300.json': {'raw': ''},
    }
    discourse = FakeDiscourse(responses)

    ics = filter_tags_to_bytes('https://community.steeplechasers.org', discourse, tags=['grand-prix'], log=log)
    text = ics.decode()
    assert text.count('BEGIN:VEVENT') == 2
    assert 'discourse-event-1@' in text
    assert 'discourse-event-3@' in text
    assert 'discourse-event-2@' not in text


def test_filter_tags_to_bytes_no_tags_includes_all_events():
    events = [_event(1, ['grand-prix']), _event(2, ['social'])]
    responses = {
        'discourse-post-event.events': {'events': events},
        'posts.100.json': {'raw': ''},
        'posts.200.json': {'raw': ''},
    }
    discourse = FakeDiscourse(responses)

    ics = filter_tags_to_bytes('https://community.steeplechasers.org', discourse, tags=None, log=log)
    assert ics.decode().count('BEGIN:VEVENT') == 2


def test_filter_tags_to_bytes_uses_admin_discourse_for_location_query(bareapp):
    events = [_event(1, ['grand-prix'])]
    calls = []

    def run(body):
        calls.append(body)
        return {'columns': ['id', 'raw'], 'rows': [[100, '[event location="Venue"][/event]']], 'result_count': 1}

    public_responses = {'discourse-post-event.events': {'events': events}}
    admin_responses = {'admin.plugins.explorer.queries.7.run': run}
    discourse = FakeDiscourse(public_responses)
    admin_discourse = FakeDiscourse(admin_responses)

    with bareapp.app_context():
        ics = filter_tags_to_bytes('https://community.steeplechasers.org', discourse, tags=['grand-prix'],
                                   location_query_id=7, admin_discourse=admin_discourse, log=log)
    assert len(calls) == 1
    assert b'LOCATION:Venue' in ics
