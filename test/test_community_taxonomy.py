'''
test_community_taxonomy - test members.community_taxonomy
=========================================================
'''

# homegrown
from members.community_taxonomy import (
    fetch_categories, fetch_category_groups, fetch_tags, fetch_tag_groups, fetch_groups,
    fetch_site_settings, fetch_user_fields, fetch_badges, fetch_themes, fetch_watched_words,
    fetch_nav_items, fetch_site_title,
    _permission_label, _visibility_label, _access_level_label,
    build_docx,
)
from fakediscourse import FakeDiscourse


# ----------------------------------------------------------------------
# fetch_categories
# ----------------------------------------------------------------------

def test_fetch_categories_flattens_subcategories_with_parent_name():
    data = {
        'category_list': {
            'categories': [
                {'id': 1, 'name': 'General', 'subcategory_list': [{'id': 2, 'name': 'Announcements'}]},
                {'id': 3, 'name': 'Racing'},
            ]
        }
    }
    discourse = FakeDiscourse({'categories.json': data})
    result = fetch_categories(discourse)
    assert [c['id'] for c in result] == [1, 2, 3]
    assert result[1]['_parent_name'] == 'General'
    assert '_parent_name' not in result[2]


# ----------------------------------------------------------------------
# fetch_category_groups
# ----------------------------------------------------------------------

def test_fetch_category_groups_zips_columns_and_rows():
    resp = {'columns': ['category_id', 'group_name', 'permission_type'],
            'rows': [[10, 'club-mods', 1], [10, 'cal-mods', 2]]}
    discourse = FakeDiscourse({'admin.plugins.explorer.queries.7.run': resp})
    result = fetch_category_groups(discourse, 7)
    assert result == [
        {'category_id': 10, 'group_name': 'club-mods', 'permission_type': 1},
        {'category_id': 10, 'group_name': 'cal-mods', 'permission_type': 2},
    ]


# ----------------------------------------------------------------------
# simple single-call fetchers
# ----------------------------------------------------------------------

def test_fetch_tags_returns_tags_list():
    discourse = FakeDiscourse({'tags.json': {'tags': [{'name': 'a'}]}})
    assert fetch_tags(discourse) == [{'name': 'a'}]


def test_fetch_tag_groups_returns_list():
    discourse = FakeDiscourse({'tag_groups.json': {'tag_groups': [{'name': 'g1'}]}})
    assert fetch_tag_groups(discourse) == [{'name': 'g1'}]


def test_fetch_site_settings_converts_list_to_dict():
    discourse = FakeDiscourse({'admin.site_settings.json': {'site_settings': [
        {'setting': 'title', 'value': 'FSRC', 'humanized_name': 'Title'},
    ]}})
    assert fetch_site_settings(discourse) == {'title': {'value': 'FSRC', 'label': 'Title'}}


def test_fetch_user_fields_returns_list():
    discourse = FakeDiscourse({'admin.user_fields.json': {'user_fields': [{'name': 'shirt size'}]}})
    assert fetch_user_fields(discourse) == [{'name': 'shirt size'}]


def test_fetch_badges_returns_list():
    discourse = FakeDiscourse({'admin.badges.json': {'badges': [{'name': 'Basic'}]}})
    assert fetch_badges(discourse) == [{'name': 'Basic'}]


def test_fetch_themes_returns_list():
    discourse = FakeDiscourse({'admin.themes.json': {'themes': [{'name': 'Default'}]}})
    assert fetch_themes(discourse) == [{'name': 'Default'}]


def test_fetch_watched_words_returns_raw_response():
    discourse = FakeDiscourse({'admin.watched_words.json': {'words': []}})
    assert fetch_watched_words(discourse) == {'words': []}


def test_fetch_nav_items_returns_list():
    discourse = FakeDiscourse({'navigation_menu_items.json': {'navigation_menu_items': [{'name': 'FAQ'}]}})
    assert fetch_nav_items(discourse) == [{'name': 'FAQ'}]


def test_fetch_nav_items_returns_empty_on_error():
    def raiser(_params):
        raise RuntimeError('not available')
    discourse = FakeDiscourse({'navigation_menu_items.json': raiser})
    assert fetch_nav_items(discourse) == []


def test_fetch_site_title_returns_title():
    discourse = FakeDiscourse({'about.json': {'about': {'title': 'FSRC Community'}}})
    assert fetch_site_title(discourse) == 'FSRC Community'


def test_fetch_site_title_returns_empty_on_error():
    def raiser(_params):
        raise RuntimeError('boom')
    discourse = FakeDiscourse({'about.json': raiser})
    assert fetch_site_title(discourse) == ''


# ----------------------------------------------------------------------
# fetch_groups pagination
# ----------------------------------------------------------------------

def test_fetch_groups_paginates_until_short_page():
    page0 = [{'name': f'group{i}'} for i in range(20)]
    page1 = [{'name': 'group20'}]

    def get(params):
        return {'groups': page0 if params['page'] == 0 else page1}
    discourse = FakeDiscourse({'groups.json': get})

    result = fetch_groups(discourse)
    assert len(result) == 21


def test_fetch_groups_stops_on_empty_page():
    discourse = FakeDiscourse({'groups.json': lambda params: {'groups': []}})
    assert fetch_groups(discourse) == []


# ----------------------------------------------------------------------
# label helpers
# ----------------------------------------------------------------------

def test_permission_label_known_values():
    assert _permission_label(1) == 'Full'
    assert _permission_label(2) == 'Create Post'
    assert _permission_label(3) == 'Read Only'


def test_permission_label_unknown_value_falls_back_to_str():
    assert _permission_label(99) == '99'


def test_visibility_label_known_values():
    assert _visibility_label(0) == 'Public'
    assert _visibility_label(4) == 'Owners'


def test_access_level_label_known_values():
    assert _access_level_label(0) == 'Nobody'
    assert _access_level_label(99) == 'Everyone'


def test_access_level_label_unknown_falls_back_to_str():
    assert _access_level_label(42) == '42'


# ----------------------------------------------------------------------
# build_docx (smoke test -- doesn't crash, produces expected section headings)
# ----------------------------------------------------------------------

def test_build_docx_smoke():
    data = {
        'title': 'FSRC Community',
        'groups': [{'id': 1, 'name': 'club-mods', 'user_count': 3}],
        'categories': [{'id': 1, 'name': 'General', 'read_restricted': False}],
        'tags': [{'name': 'grand-prix'}],
        'tag_groups': [],
        'site_settings': {'title': {'value': 'FSRC', 'label': 'Title'}},
        'user_fields': [],
        'badges': [],
        'themes': [],
        'watched_words': [],
        'nav_items': [],
    }
    doc = build_docx(data, 'https://community.steeplechasers.org')
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith('Heading')]
    assert 'Groups' in headings
    assert 'Categories' in headings
    assert 'Tags' in headings
