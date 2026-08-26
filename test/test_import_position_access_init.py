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
from members.scripts.import_position_access_init import _import_bundles, _import_position_mapping, ParameterError
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
    position = Position(position='Race Director', interest=localinterest)
    db.session.add_all([system, level, position])
    db.session.commit()

    return {'localinterest': localinterest, 'system': system, 'level': level, 'position': position}


def _write_csv(tmp_path, name, rows, fieldnames):
    path = tmp_path / name
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


BUNDLES_FIELDNAMES = ('access_type_slug', 'access_type', 'system_slug', 'access_level_slug', 'description')
POSITIONS_FIELDNAMES = ('position', 'access_type_slug')


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


def test_import_position_mapping_attaches_accesstype_to_position(importsetup, tmp_path):
    bundles_csv = _write_csv(tmp_path, 'bundles.csv', [
        {'access_type_slug': 'rd-bundle', 'access_type': 'RD Bundle', 'system_slug': 'mailchimp',
         'access_level_slug': 'admin', 'description': ''},
    ], fieldnames=BUNDLES_FIELDNAMES)
    accesstypes = _import_bundles(importsetup['localinterest'], bundles_csv)

    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director', 'access_type_slug': 'rd-bundle'},
    ], fieldnames=POSITIONS_FIELDNAMES)
    _import_position_mapping(importsetup['localinterest'], positions_csv, accesstypes)

    assert importsetup['position'].accesstypes == [AccessType.query.filter_by(slug='rd-bundle').one()]


def test_import_position_mapping_errors_on_unknown_position(importsetup, tmp_path):
    bundles_csv = _write_csv(tmp_path, 'bundles.csv', [
        {'access_type_slug': 'rd-bundle', 'access_type': 'RD Bundle', 'system_slug': 'mailchimp',
         'access_level_slug': 'admin', 'description': ''},
    ], fieldnames=BUNDLES_FIELDNAMES)
    accesstypes = _import_bundles(importsetup['localinterest'], bundles_csv)

    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'No Such Position', 'access_type_slug': 'rd-bundle'},
    ], fieldnames=POSITIONS_FIELDNAMES)

    with pytest.raises(ParameterError, match='no position found'):
        _import_position_mapping(importsetup['localinterest'], positions_csv, accesstypes)


def test_import_position_mapping_errors_on_unknown_accesstype(importsetup, tmp_path):
    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director', 'access_type_slug': 'no-such-bundle'},
    ], fieldnames=POSITIONS_FIELDNAMES)

    with pytest.raises(ParameterError, match='no access type found'):
        _import_position_mapping(importsetup['localinterest'], positions_csv, {})


def test_import_position_mapping_does_not_duplicate_existing_pairing(importsetup, tmp_path):
    bundles_csv = _write_csv(tmp_path, 'bundles.csv', [
        {'access_type_slug': 'rd-bundle', 'access_type': 'RD Bundle', 'system_slug': 'mailchimp',
         'access_level_slug': 'admin', 'description': ''},
    ], fieldnames=BUNDLES_FIELDNAMES)
    accesstypes = _import_bundles(importsetup['localinterest'], bundles_csv)

    positions_csv = _write_csv(tmp_path, 'positions.csv', [
        {'position': 'Race Director', 'access_type_slug': 'rd-bundle'},
    ], fieldnames=POSITIONS_FIELDNAMES)
    _import_position_mapping(importsetup['localinterest'], positions_csv, accesstypes)
    _import_position_mapping(importsetup['localinterest'], positions_csv, accesstypes)

    assert len(importsetup['position'].accesstypes) == 1
