'''
test_community_events - test members.community_events
=========================================================
'''

# standard
import json
import logging

# pypi
import pytest

# homegrown
from members.community_events import _parse_dt, _build_topic_body, _fetch_known_tags, import_events
from fakediscourse import FakeDiscourse

log = logging.getLogger('test')


# ----------------------------------------------------------------------
# _parse_dt
# ----------------------------------------------------------------------

def test_parse_dt_replaces_space_with_t():
    assert _parse_dt('2026-01-15 10:00:00') == '2026-01-15T10:00:00'


def test_parse_dt_strips_whitespace():
    assert _parse_dt('  2026-01-15 10:00:00  ') == '2026-01-15T10:00:00'


# ----------------------------------------------------------------------
# _build_topic_body
# ----------------------------------------------------------------------

def test_build_topic_body_timed_event():
    row = {'start_date': '2026-01-15 10:00:00', 'end_date': '2026-01-15 11:30:00'}
    body = _build_topic_body(row)
    assert 'start="2026-01-15T10:00:00"' in body
    assert 'end="2026-01-15T11:30:00"' in body
    assert 'all_day' not in body
    assert 'status="public" timezone="America/New_York"' in body


def test_build_topic_body_all_day_event_uses_date_only():
    row = {'start_date': '2026-01-15 00:00:00', 'end_date': '2026-01-16 00:00:00', 'all_day': 'true'}
    body = _build_topic_body(row)
    assert 'start="2026-01-15"' in body
    assert 'end="2026-01-16"' in body
    assert 'all_day="true"' in body


def test_build_topic_body_all_day_defaults_end_to_start_when_missing():
    row = {'start_date': '2026-01-15 00:00:00', 'all_day': 'true'}
    body = _build_topic_body(row)
    assert 'start="2026-01-15"' in body
    assert 'end="2026-01-15"' in body


def test_build_topic_body_includes_url_and_location_when_present():
    row = {'start_date': '2026-01-15 10:00:00', 'end_date': '2026-01-15 11:00:00',
           'website': 'https://example.com/race', 'venue': 'Baker Park, Frederick, MD'}
    body = _build_topic_body(row)
    assert 'url="https://example.com/race"' in body
    assert 'location="Baker Park, Frederick, MD"' in body


def test_build_topic_body_appends_image_and_description():
    row = {'start_date': '2026-01-15 10:00:00', 'end_date': '2026-01-15 11:00:00',
           'image_url': 'https://example.com/img.png', 'description': 'Come run!'}
    body = _build_topic_body(row)
    assert '![](https://example.com/img.png)' in body
    assert 'Come run!' in body


# ----------------------------------------------------------------------
# _fetch_known_tags
# ----------------------------------------------------------------------

def test_fetch_known_tags_extracts_names():
    discourse = FakeDiscourse({'tags.json': {'tags': [{'name': 'grand-prix'}, {'name': 'social'}]}})
    assert _fetch_known_tags(discourse) == {'grand-prix', 'social'}


def test_fetch_known_tags_skips_entries_without_name():
    discourse = FakeDiscourse({'tags.json': {'tags': [{'name': 'grand-prix'}, {}]}})
    assert _fetch_known_tags(discourse) == {'grand-prix'}


# ----------------------------------------------------------------------
# import_events
# ----------------------------------------------------------------------

@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / 'events.csv'
    path.write_text(
        'id,title,start_date,end_date,tags\n'
        '1,Grand Prix Race,2026-01-15 10:00:00,2026-01-15 11:00:00,grand-prix\n'
        '2,Social Run,2026-02-01 09:00:00,2026-02-01 10:00:00,social\n',
        encoding='utf-8',
    )
    return str(path)


@pytest.fixture
def state_file(tmp_path):
    return str(tmp_path / 'state.json')


def test_import_events_creates_topic_per_row_and_writes_state(csv_file, state_file):
    created = []

    def post(body):
        created.append(body)
        return {'topic_id': len(created), 'topic_slug': f'topic-{len(created)}'}

    discourse = FakeDiscourse({
        'tags.json': {'tags': [{'name': 'grand-prix'}, {'name': 'social'}]},
        'posts': post,
    })

    import_events('fsrc', csv_file, 5, state_file, discourse, 'https://community.example.com', log=log)

    assert len(created) == 2
    assert created[0]['category'] == 5
    assert created[0]['tags'] == ['grand-prix']

    state = json.loads(open(state_file).read())
    assert set(state.keys()) == {'1', '2'}
    assert state['1']['url'] == 'https://community.example.com/t/topic-1/1'


def test_import_events_skips_rows_already_in_state(csv_file, state_file):
    with open(state_file, 'w') as f:
        json.dump({'1': {'topic_id': 99, 'url': 'existing', 'title': 'Grand Prix Race'}}, f)

    created = []

    def post(body):
        created.append(body)
        return {'topic_id': 2, 'topic_slug': 'topic-2'}

    discourse = FakeDiscourse({
        'tags.json': {'tags': [{'name': 'grand-prix'}, {'name': 'social'}]},
        'posts': post,
    })

    import_events('fsrc', csv_file, 5, state_file, discourse, 'https://community.example.com', log=log)

    assert len(created) == 1
    assert created[0]['title'] == 'Social Run'


def test_import_events_aborts_on_unknown_tag(csv_file, state_file, capsys):
    discourse = FakeDiscourse({'tags.json': {'tags': [{'name': 'social'}]}})

    import_events('fsrc', csv_file, 5, state_file, discourse, 'https://community.example.com', log=log)

    captured = capsys.readouterr()
    assert 'grand-prix' in captured.out
    assert not __import__('os').path.exists(state_file)


def test_import_events_dry_run_does_not_post_or_write_state(csv_file, state_file):
    def post(body):
        raise AssertionError('should not post in dry run')

    discourse = FakeDiscourse({
        'tags.json': {'tags': [{'name': 'grand-prix'}, {'name': 'social'}]},
        'posts': post,
    })

    import_events('fsrc', csv_file, 5, state_file, discourse, 'https://community.example.com',
                  dry_run=True, log=log)

    import os
    assert not os.path.exists(state_file)
