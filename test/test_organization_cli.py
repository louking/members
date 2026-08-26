'''
test_organization_cli - test scripts.organization_cli
=========================================================
'''

# standard
import csv

# pypi
import pytest
from flask import g

# homegrown
from scripts import ParameterError
from scripts.organization_cli import access_report as _access_report_command
from members.model import db, LocalInterest, LocalUser, Position, System, SystemAccessLevel
from loutilities.user.model import Interest

# access_report is wrapped by @with_appcontext (needs a live click context, which these
# tests don't have) and @catch_errors (turns ParameterError into sys.exit(1), which would
# defeat the pytest.raises(ParameterError, ...) tests below) -- both preserve __wrapped__,
# so call the raw function directly under the bare_dbapp fixture's own app context instead
access_report = _access_report_command.callback.__wrapped__.__wrapped__


@pytest.fixture
def clisetup(bare_dbapp):
    interest_row = Interest(interest='fsrc', description='FSRC')
    localinterest = LocalInterest(interest_id=None)
    db.session.add_all([interest_row, localinterest])
    db.session.commit()
    localinterest.interest_id = interest_row.id
    db.session.commit()
    g.interest = 'fsrc'

    member = LocalUser(name='Jane Doe', email='jane@example.com', active=True, interest=localinterest)
    system = System(name='MailChimp', slug='mailchimp', interest=localinterest)
    level = SystemAccessLevel(system=system, name='Admin', slug='admin', interest=localinterest)
    position = Position(position='Race Director', interest=localinterest, direct_access=[level])
    db.session.add_all([member, system, level, position])
    db.session.commit()

    return {
        'localinterest': localinterest, 'member': member, 'system': system, 'level': level,
        'position': position,
    }


def _write_csv(tmp_path, rows, fieldnames=('email', 'system_slug', 'access_level_slug', 'notes')):
    path = tmp_path / 'actual.csv'
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


def _hold(member, position, localinterest):
    from datetime import date
    from members.model import UserPosition
    up = UserPosition(user=member, position=position, interest=localinterest,
                       startdate=date(2026, 1, 1), finishdate=None)
    db.session.add(up)
    db.session.commit()


def test_access_report_no_discrepancy(clisetup, tmp_path, capsys):
    _hold(clisetup['member'], clisetup['position'], clisetup['localinterest'])
    csv_path = _write_csv(tmp_path, [
        {'email': 'jane@example.com', 'system_slug': 'mailchimp', 'access_level_slug': 'admin', 'notes': ''},
    ])

    access_report('fsrc', csv_path)

    out = capsys.readouterr().out
    assert 'no discrepancies' in out


def test_access_report_flags_missing_access(clisetup, tmp_path, capsys):
    _hold(clisetup['member'], clisetup['position'], clisetup['localinterest'])
    csv_path = _write_csv(tmp_path, [])

    access_report('fsrc', csv_path)

    out = capsys.readouterr().out
    assert 'Jane Doe' in out
    assert 'MISSING' in out
    assert 'MailChimp: Admin' in out


def test_access_report_flags_extra_access(clisetup, tmp_path, capsys):
    # member has no active position, but CSV shows they have access anyway
    csv_path = _write_csv(tmp_path, [
        {'email': 'jane@example.com', 'system_slug': 'mailchimp', 'access_level_slug': 'admin', 'notes': ''},
    ])

    access_report('fsrc', csv_path)

    out = capsys.readouterr().out
    assert 'Jane Doe' in out
    assert 'EXTRA' in out
    assert 'MailChimp: Admin' in out


def test_access_report_errors_on_unknown_email(clisetup, tmp_path):
    csv_path = _write_csv(tmp_path, [
        {'email': 'nobody@example.com', 'system_slug': 'mailchimp', 'access_level_slug': 'admin', 'notes': ''},
    ])

    with pytest.raises(ParameterError, match='no member found'):
        access_report('fsrc', csv_path)


def test_access_report_errors_on_unknown_system(clisetup, tmp_path):
    csv_path = _write_csv(tmp_path, [
        {'email': 'jane@example.com', 'system_slug': 'nosuchsystem', 'access_level_slug': 'admin', 'notes': ''},
    ])

    with pytest.raises(ParameterError, match='no system found'):
        access_report('fsrc', csv_path)


def test_access_report_errors_on_unknown_access_level(clisetup, tmp_path):
    csv_path = _write_csv(tmp_path, [
        {'email': 'jane@example.com', 'system_slug': 'mailchimp', 'access_level_slug': 'nosuchlevel', 'notes': ''},
    ])

    with pytest.raises(ParameterError, match='no access level found'):
        access_report('fsrc', csv_path)


def test_access_report_errors_on_missing_csv_column(clisetup, tmp_path):
    csv_path = _write_csv(tmp_path, [{'email': 'jane@example.com'}], fieldnames=('email',))

    with pytest.raises(ParameterError, match='missing required column'):
        access_report('fsrc', csv_path)
