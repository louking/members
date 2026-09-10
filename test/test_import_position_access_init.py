'''
test_import_position_access_init - test members.scripts.import_position_access_init
=========================================================
'''

# standard
import csv

# pypi
import pytest
from flask import g

# homegrown
from members.scripts.import_position_access_init import (
    _import_bundles, _import_position_mapping, ParameterError,
)
from members.model import db, LocalInterest, Position, System, SystemAccessLevel, AccessType
from loutilities.user.model import Interest


@pytest.fixture
def importsetup(bare_dbapp):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()
    g.interest = 'fsrc'

    system = System(name='MailChimp', slug='mailchimp', interest=localinterest)
    level = SystemAccessLevel(system=system, name='Admin', slug='admin', interest=localinterest)
    # a second system with an access level of the same slug, to prove the system_slug: prefix
    # on a direct_access_level_slugs token actually disambiguates
    system2 = System(name='RunSignUp', slug='runsignup', interest=localinterest)
    level2 = SystemAccessLevel(system=system2, name='Admin', slug='admin', interest=localinterest)
    position = Position(position='Race Director', interest=localinterest)
    db.session.add_all([system, level, system2, level2, position])
    db.session.commit()

    return {'localinterest': localinterest, 'system': system, 'level': level,
            'system2': system2, 'level2': level2, 'position': position}


def _write_csv(tmp_path, name, rows, fieldnames):
    path = tmp_path / name
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


BUNDLES_FIELDNAMES = ('access_type_slug', 'access_type', 'system_slug', 'access_level_slug', 'description')
POSITIONS_FIELDNAMES = ('position', 'access_type_slugs', 'direct_access_level_slugs')


def test_import_bundles_creates_accesstype_with_members(importsetup, tmp_path):
    csv_path = _write_csv(tmp_path, 'bundles.csv', [
        {'access_type_slug': 'rd-bundle', 'access_type': 'RD Bundle', 'system_slug': 'mailchimp',
         'access_level_slug': 'admin', 'description': 'race director access'},
    ], fieldnames=BUNDLES_FIELDNAMES)

    accesstypes = _import_bundles(importsetup['localinterest'], csv_path)

    assert set(accesstypes) == {'rd-bundle'}
    accesstype = AccessType.query.filter_by(slug='rd-bundle').one()
    assert accesstype.name == 'RD Bundle'
    assert accesstype.description == 'race director access'
    assert accesstype.access == [importsetup['level']]


def test_import_bundles_errors_on_unknown_system(importsetup, tmp_path):
    csv_path = _write_csv(tmp_path, 'bundles.csv', [
        {'access_type_slug': 'rd-bundle', 'access_type': 'RD Bundle', 'system_slug': 'nosuchsystem',
         'access_level_slug': 'admin', 'description': ''},
    ], fieldnames=BUNDLES_FIELDNAMES)

    with pytest.raises(ParameterError, match='no system found'):
        _import_bundles(importsetup['localinterest'], csv_path)


def _bundle_csv(tmp_path):
    return _write_csv(tmp_path, 'bundles.csv', [
        {'access_type_slug': 'rd-bundle', 'access_type': 'RD Bundle', 'system_slug': 'mailchimp',
         'access_level_slug': 'admin', 'description': ''},
    ], fieldnames=BUNDLES_FIELDNAMES)


def test_import_position_mapping_attaches_multiple_access_types_and_direct_access(importsetup, tmp_path):
    # two bundles so the comma-separated access_type_slugs cell has two entries
    accesstypes = _import_bundles(importsetup['localinterest'], _write_csv(tmp_path, 'bundles.csv', [
        {'access_type_slug': 'rd-bundle', 'access_type': 'RD Bundle', 'system_slug': 'mailchimp',
         'access_level_slug': 'admin', 'description': ''},
        {'access_type_slug': 'officer-bundle', 'access_type': 'Officer Bundle', 'system_slug': 'mailchimp',
         'access_level_slug': 'admin', 'description': ''},
    ], fieldnames=BUNDLES_FIELDNAMES))

    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director',
         'access_type_slugs': 'rd-bundle, officer-bundle',
         'direct_access_level_slugs': 'mailchimp:admin, runsignup:admin'},
    ], fieldnames=POSITIONS_FIELDNAMES)
    _import_position_mapping(importsetup['localinterest'], positions_csv, accesstypes)

    position = importsetup['position']
    assert {at.slug for at in position.accesstypes} == {'rd-bundle', 'officer-bundle'}
    # the runsignup:admin token must resolve to system2's level, not system1's (same slug)
    assert set(position.direct_access) == {importsetup['level'], importsetup['level2']}


def test_import_position_mapping_allows_empty_lists(importsetup, tmp_path):
    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director', 'access_type_slugs': '', 'direct_access_level_slugs': ''},
    ], fieldnames=POSITIONS_FIELDNAMES)
    _import_position_mapping(importsetup['localinterest'], positions_csv, {})

    assert importsetup['position'].accesstypes == []
    assert importsetup['position'].direct_access == []


def test_import_position_mapping_errors_on_unknown_position(importsetup, tmp_path):
    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'No Such Position', 'access_type_slugs': '', 'direct_access_level_slugs': ''},
    ], fieldnames=POSITIONS_FIELDNAMES)

    with pytest.raises(ParameterError, match='no position found'):
        _import_position_mapping(importsetup['localinterest'], positions_csv, {})


def test_import_position_mapping_errors_on_unknown_accesstype(importsetup, tmp_path):
    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director', 'access_type_slugs': 'no-such-bundle', 'direct_access_level_slugs': ''},
    ], fieldnames=POSITIONS_FIELDNAMES)

    with pytest.raises(ParameterError, match='no access type found'):
        _import_position_mapping(importsetup['localinterest'], positions_csv, {})


def test_import_position_mapping_errors_on_direct_access_token_without_system_prefix(importsetup, tmp_path):
    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director', 'access_type_slugs': '', 'direct_access_level_slugs': 'admin'},
    ], fieldnames=POSITIONS_FIELDNAMES)

    with pytest.raises(ParameterError, match='system_slug:access_level_slug'):
        _import_position_mapping(importsetup['localinterest'], positions_csv, {})


def test_import_position_mapping_errors_on_unknown_direct_access_system(importsetup, tmp_path):
    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director', 'access_type_slugs': '', 'direct_access_level_slugs': 'nosuchsystem:admin'},
    ], fieldnames=POSITIONS_FIELDNAMES)

    with pytest.raises(ParameterError, match='no system found'):
        _import_position_mapping(importsetup['localinterest'], positions_csv, {})


def test_import_position_mapping_errors_on_unknown_direct_access_level(importsetup, tmp_path):
    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director', 'access_type_slugs': '', 'direct_access_level_slugs': 'mailchimp:nosuchlevel'},
    ], fieldnames=POSITIONS_FIELDNAMES)

    with pytest.raises(ParameterError, match='no access level found'):
        _import_position_mapping(importsetup['localinterest'], positions_csv, {})


def test_import_position_mapping_errors_on_missing_csv_column(importsetup, tmp_path):
    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director'},
    ], fieldnames=('position',))

    with pytest.raises(ParameterError, match='missing required column'):
        _import_position_mapping(importsetup['localinterest'], positions_csv, {})


def test_import_position_mapping_does_not_duplicate_existing_pairings(importsetup, tmp_path):
    accesstypes = _import_bundles(importsetup['localinterest'], _bundle_csv(tmp_path))

    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director', 'access_type_slugs': 'rd-bundle',
         'direct_access_level_slugs': 'mailchimp:admin'},
    ], fieldnames=POSITIONS_FIELDNAMES)
    _import_position_mapping(importsetup['localinterest'], positions_csv, accesstypes)
    _import_position_mapping(importsetup['localinterest'], positions_csv, accesstypes)

    assert len(importsetup['position'].accesstypes) == 1
    assert len(importsetup['position'].direct_access) == 1
