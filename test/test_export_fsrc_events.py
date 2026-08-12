'''
test_export_fsrc_events - test scripts.export_fsrc_events
=========================================================
'''

# homegrown
from scripts.export_fsrc_events import (
    slugify, category_to_tag, _strip_tribe_widgets, collapse_ws, format_venue,
)


# ----------------------------------------------------------------------
# slugify / category_to_tag
# ----------------------------------------------------------------------

def test_slugify_lowercases_and_hyphenates():
    assert slugify('Grand Prix Race') == 'grand-prix-race'


def test_slugify_strips_leading_trailing_hyphens():
    assert slugify('  !Race Day!  ') == 'race-day'


def test_category_to_tag_uses_slug_when_present():
    assert category_to_tag({'slug': 'lowkey', 'name': 'Low Key'}) == 'lowkey-race'


def test_category_to_tag_falls_back_to_slugified_name():
    assert category_to_tag({'name': 'Some New Category'}) == 'some-new-category'


def test_category_to_tag_removed_category_returns_empty_string():
    assert category_to_tag({'slug': 'race'}) == ''


def test_category_to_tag_unmapped_slug_passes_through():
    assert category_to_tag({'slug': 'grand-prix'}) == 'grand-prix'


# ----------------------------------------------------------------------
# _strip_tribe_widgets
# ----------------------------------------------------------------------

def test_strip_tribe_widgets_removes_tribe_div_and_contents():
    html = '<p>Race info</p><div class="tribe-events-widget">junk<span>more junk</span></div><p>after</p>'
    result = _strip_tribe_widgets(html)
    assert 'junk' not in result
    assert 'more junk' not in result
    assert '<p>Race info</p>' in result
    assert '<p>after</p>' in result


def test_strip_tribe_widgets_leaves_non_tribe_divs_intact():
    html = '<div class="normal">keep me</div>'
    assert 'keep me' in _strip_tribe_widgets(html)


def test_strip_tribe_widgets_handles_nested_tribe_divs():
    html = '<div class="tribe-outer">outer<div class="tribe-inner">inner</div>tail</div><p>safe</p>'
    result = _strip_tribe_widgets(html)
    assert 'outer' not in result
    assert 'inner' not in result
    assert 'tail' not in result
    assert '<p>safe</p>' in result


# ----------------------------------------------------------------------
# collapse_ws
# ----------------------------------------------------------------------

def test_collapse_ws_collapses_multiple_whitespace_runs():
    assert collapse_ws('line one\n\n  line   two') == 'line one line two'


def test_collapse_ws_strips_leading_trailing_whitespace():
    assert collapse_ws('  padded  ') == 'padded'


def test_collapse_ws_empty_string_returns_empty():
    assert collapse_ws('') == ''
    assert collapse_ws(None) == ''


# ----------------------------------------------------------------------
# format_venue
# ----------------------------------------------------------------------

def test_format_venue_joins_name_city_state():
    venue = {'venue': 'Baker Park', 'city': 'Frederick', 'state': 'MD'}
    assert format_venue(venue) == 'Baker Park, Frederick, MD'


def test_format_venue_omits_missing_fields():
    venue = {'venue': 'Baker Park', 'city': '', 'state': None}
    assert format_venue(venue) == 'Baker Park'


def test_format_venue_unwraps_list_shaped_venue():
    venue = [{'venue': 'Baker Park', 'city': 'Frederick', 'state': 'MD'}]
    assert format_venue(venue) == 'Baker Park, Frederick, MD'


def test_format_venue_empty_list_returns_empty_string():
    assert format_venue([]) == ''


def test_format_venue_none_returns_empty_string():
    assert format_venue(None) == ''


def test_format_venue_unescapes_html_entities_in_name():
    venue = {'venue': 'Tuscarora H.S. &amp; Track', 'city': '', 'state': ''}
    assert format_venue(venue) == 'Tuscarora H.S. & Track'
