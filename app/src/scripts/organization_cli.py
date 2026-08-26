"""
organization_cli - cli tasks needed for organization/position access management, see #716
"""

# standard
import csv

# pypi
from flask import g
from flask.cli import with_appcontext
from click import argument, group, option

# homegrown
from scripts import catch_errors, ParameterError
from members.model import db, LocalUser, System, SystemAccessLevel
from members.helpers import localinterest
from members.organization_access import compute_required_access

# needs to be before any commands
@group()
def organization():
    """Perform organization module tasks"""
    pass


def _load_actual_access(interest, csv_path, localinterest_row):
    """
    read the actual-state CSV (email, system_slug, access_level_slug, notes -- see #716
    bootstrapping) and return {localuser_id: {(system_id, accesslevel_id), ...}}

    system_slug/access_level_slug are matched against System.slug/SystemAccessLevel.slug
    (System/SystemAccessLevel views), not the display name -- fails loudly (ParameterError)
    on any row referencing an email/slug that doesn't resolve, rather than silently skipping
    or auto-creating, since this data is hand-authored from a spreadsheet and typo-prone
    """
    actual_by_user = {}
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        missing = {'email', 'system_slug', 'access_level_slug'} - set(reader.fieldnames or [])
        if missing:
            raise ParameterError(f'--actual-csv is missing required column(s): {", ".join(sorted(missing))}')

        for lineno, row in enumerate(reader, start=2):
            email = (row['email'] or '').strip()
            systemslug = (row['system_slug'] or '').strip()
            levelslug = (row['access_level_slug'] or '').strip()
            if not email or not systemslug or not levelslug:
                raise ParameterError(
                    f'--actual-csv line {lineno}: email, system_slug, and access_level_slug are all required')

            user = LocalUser.query.filter_by(interest=localinterest_row, email=email).one_or_none()
            if not user:
                raise ParameterError(f'--actual-csv line {lineno}: no member found for email {email!r}')

            system = System.query.filter_by(interest=localinterest_row, slug=systemslug).one_or_none()
            if not system:
                raise ParameterError(f'--actual-csv line {lineno}: no system found with slug {systemslug!r}')

            level = SystemAccessLevel.query.filter_by(system=system, slug=levelslug).one_or_none()
            if not level:
                raise ParameterError(
                    f'--actual-csv line {lineno}: no access level found with slug {levelslug!r} for system {system.name!r}')

            actual_by_user.setdefault(user.id, set()).add((system.id, level.id))

    return actual_by_user


def _label(system_id, accesslevel_id):
    level = SystemAccessLevel.query.filter_by(id=accesslevel_id).one_or_none()
    return level.label if level else f'system={system_id} accesslevel={accesslevel_id}'


@organization.command('access-report')
@argument('interest')
@option('--actual-csv', 'actual_csv', required=True,
        help='path to CSV (email, system_slug, access_level_slug, notes) of current actual access, exported from the spreadsheet')
@with_appcontext
@catch_errors
def access_report(interest, actual_csv):
    """
    one-time bootstrap reconciliation (see #716): for each member with at least one active
    position, or appearing in --actual-csv, diff required access (computed from Position/
    AccessType data) against actual access (from --actual-csv), and print what's missing
    (required but not in the CSV -- access needs to be granted) and what's extra (in the CSV
    but not required by any active position -- verify or revoke)
    """
    g.interest = interest
    localinterest_row = localinterest()

    actual_by_user = _load_actual_access(interest, actual_csv, localinterest_row)

    required_by_user = {}
    for user in LocalUser.query.filter_by(interest=localinterest_row).all():
        required = compute_required_access(user)
        if required:
            required_by_user[user.id] = required

    all_user_ids = set(required_by_user) | set(actual_by_user)
    if not all_user_ids:
        print('no active positions with required access, and no rows in --actual-csv')
        return

    users_by_id = {u.id: u for u in LocalUser.query.filter(LocalUser.id.in_(all_user_ids)).all()}
    discrepancies = 0
    for userid in sorted(all_user_ids, key=lambda i: users_by_id[i].name):
        required = required_by_user.get(userid, set())
        actual = actual_by_user.get(userid, set())
        missing = required - actual
        extra = actual - required
        if not missing and not extra:
            continue

        discrepancies += 1
        print(users_by_id[userid].name)
        for pair in sorted(missing, key=lambda p: _label(*p)):
            print(f'  MISSING (required, not in CSV): {_label(*pair)}')
        for pair in sorted(extra, key=lambda p: _label(*p)):
            print(f'  EXTRA (in CSV, not required): {_label(*pair)}')

    if not discrepancies:
        print('no discrepancies -- required access matches --actual-csv for every member checked')
    else:
        print(f'\n{discrepancies} member(s) with discrepancies out of {len(all_user_ids)} checked')
