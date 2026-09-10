'''
import_position_access_init - one-time bootstrap import of AccessType bundles and
per-position access type / direct access mapping (see #716)
================================================================================================
run from 3 levels up, like:
    python -m members.scripts.import_position_access_init <interest> <bundles.csv> <positions.csv>

bundles.csv columns: access_type_slug, access_type, system_slug, access_level_slug, description
    one row per (access_type_slug, system_slug, access_level_slug) triple; repeat the
    access_type_slug across rows to build up its member set. access_type_slug is the lookup/
    creation key (an existing AccessType.slug is reused, matching #716's additive-only
    contract; a new slug creates a new AccessType named from the access_type column).
    system_slug/access_level_slug are matched against System.slug/SystemAccessLevel.slug --
    create those by hand via the admin UI first. access_type/description only need to be
    present on one row per access_type_slug (ignored on repeats).

positions.csv columns: position, access_type_slugs, direct_access_level_slugs
    one row per position. access_type_slugs is a comma-separated list of AccessType slugs;
    direct_access_level_slugs is a comma-separated list of system_slug:access_level_slug
    tokens (the system_slug prefix is required because SystemAccessLevel.slug is only unique
    within its system). Either list may be empty. Whitespace around a slug or token is
    trimmed; empty entries (e.g. a trailing comma) are ignored. Additive: an access type or
    level already attached to the position is left alone.

Throwaway, operator-run script -- not a supported ongoing command, delete once the
bootstrap import has run. Fails loudly (raises) on any unrecognized name rather than
silently skipping, since this data is hand-authored and typo-prone.
'''
# standard
import csv
import sys
from os.path import join, dirname

# homegrown
from members import create_app
from members.settings import Development
from members.model import db
from members.applogging import setlogging
from members.model import LocalInterest, Position, System, SystemAccessLevel, AccessType
from loutilities.user.model import Interest

class ParameterError(Exception): pass

def _slug_list(cell):
    '''comma-separated cell -> list of trimmed non-empty entries'''
    return [entry.strip() for entry in (cell or '').split(',') if entry.strip()]

def _import_bundles(localinterest, bundles_csv):
    accesstypes_by_slug = {}
    with open(bundles_csv, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        missing = {'access_type_slug', 'access_type', 'system_slug', 'access_level_slug'} - set(reader.fieldnames or [])
        if missing:
            raise ParameterError(f'{bundles_csv} is missing required column(s): {", ".join(sorted(missing))}')

        for lineno, row in enumerate(reader, start=2):
            accesstypeslug = (row['access_type_slug'] or '').strip()
            accesstypename = (row['access_type'] or '').strip()
            systemslug = (row['system_slug'] or '').strip()
            levelslug = (row['access_level_slug'] or '').strip()
            description = (row.get('description') or '').strip()
            if not accesstypeslug or not accesstypename or not systemslug or not levelslug:
                raise ParameterError(
                    f'{bundles_csv} line {lineno}: access_type_slug, access_type, system_slug, and '
                    'access_level_slug are all required')

            system = System.query.filter_by(interest=localinterest, slug=systemslug).one_or_none()
            if not system:
                raise ParameterError(f'{bundles_csv} line {lineno}: no system found with slug {systemslug!r}')

            level = SystemAccessLevel.query.filter_by(system=system, slug=levelslug).one_or_none()
            if not level:
                raise ParameterError(
                    f'{bundles_csv} line {lineno}: no access level found with slug {levelslug!r} for system {system.name!r}')

            accesstype = accesstypes_by_slug.get(accesstypeslug)
            if not accesstype:
                accesstype = AccessType.query.filter_by(interest=localinterest, slug=accesstypeslug).one_or_none()
                if not accesstype:
                    accesstype = AccessType(interest=localinterest, slug=accesstypeslug, name=accesstypename)
                    db.session.add(accesstype)
                accesstypes_by_slug[accesstypeslug] = accesstype

            if description and not accesstype.description:
                accesstype.description = description
            if level not in accesstype.access:
                accesstype.access.append(level)

    db.session.flush()
    print(f'imported {len(accesstypes_by_slug)} access type(s) from {bundles_csv}')
    return accesstypes_by_slug


def _import_position_mapping(localinterest, positions_csv, accesstypes_by_slug):
    accesstypes_mapped = 0
    direct_access_mapped = 0
    with open(positions_csv, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        missing = {'position', 'access_type_slugs', 'direct_access_level_slugs'} - set(reader.fieldnames or [])
        if missing:
            raise ParameterError(f'{positions_csv} is missing required column(s): {", ".join(sorted(missing))}')

        for lineno, row in enumerate(reader, start=2):
            positionname = (row['position'] or '').strip()
            if not positionname:
                raise ParameterError(f'{positions_csv} line {lineno}: position is required')

            position = Position.query.filter_by(interest=localinterest, position=positionname).one_or_none()
            if not position:
                raise ParameterError(f'{positions_csv} line {lineno}: no position found named {positionname!r}')

            for accesstypeslug in _slug_list(row['access_type_slugs']):
                accesstype = accesstypes_by_slug.get(accesstypeslug) or \
                    AccessType.query.filter_by(interest=localinterest, slug=accesstypeslug).one_or_none()
                if not accesstype:
                    raise ParameterError(
                        f'{positions_csv} line {lineno}: no access type found with slug {accesstypeslug!r}')
                if accesstype not in position.accesstypes:
                    position.accesstypes.append(accesstype)
                    accesstypes_mapped += 1

            for token in _slug_list(row['direct_access_level_slugs']):
                if token.count(':') != 1:
                    raise ParameterError(
                        f'{positions_csv} line {lineno}: direct access entry {token!r} must be '
                        'system_slug:access_level_slug')
                systemslug, levelslug = (part.strip() for part in token.split(':'))
                if not systemslug or not levelslug:
                    raise ParameterError(
                        f'{positions_csv} line {lineno}: direct access entry {token!r} must be '
                        'system_slug:access_level_slug')

                system = System.query.filter_by(interest=localinterest, slug=systemslug).one_or_none()
                if not system:
                    raise ParameterError(
                        f'{positions_csv} line {lineno}: no system found with slug {systemslug!r}')

                level = SystemAccessLevel.query.filter_by(system=system, slug=levelslug).one_or_none()
                if not level:
                    raise ParameterError(
                        f'{positions_csv} line {lineno}: no access level found with slug {levelslug!r} '
                        f'for system {system.name!r}')
                if level not in position.direct_access:
                    position.direct_access.append(level)
                    direct_access_mapped += 1

    print(f'mapped {accesstypes_mapped} position/access-type and {direct_access_mapped} '
          f'position/direct-access pairing(s) from {positions_csv}')


def main():
    if len(sys.argv) != 4:
        print('usage: python -m members.scripts.import_position_access_init '
              '<interest> <bundles.csv> <positions.csv>')
        sys.exit(1)
    interest, bundles_csv, positions_csv = sys.argv[1:4]

    scriptdir = dirname(__file__)
    # two levels up
    scriptfolder = dirname(dirname(scriptdir))
    configdir = join(scriptfolder, 'config')
    memberconfigpath = join(configdir, 'members.cfg')
    userconfigpath = join(configdir, 'users.cfg')

    # use this order so members.cfg overrrides users.cfg
    configfiles = [userconfigpath, memberconfigpath]
    app = create_app(Development(configfiles), configfiles)
    db.init_app(app)

    with app.app_context():
        setlogging()

        interest_row = Interest.query.filter_by(interest=interest).one()
        localinterest = LocalInterest.query.filter_by(interest_id=interest_row.id).one()

        accesstypes_by_slug = _import_bundles(localinterest, bundles_csv)
        _import_position_mapping(localinterest, positions_csv, accesstypes_by_slug)

        db.session.commit()

if __name__ == "__main__":
    main()
