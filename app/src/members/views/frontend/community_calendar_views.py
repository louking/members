"""
community_calendar_views - on-demand per-series ICS calendar feeds
"""

# standard
import time
from datetime import date
from io import BytesIO

# pypi
from flask import current_app, g, abort, request, send_file

# homegrown
from . import bp
from members.community import make_discourse_client
from members.community_calendar import get_tag_groups, filter_one_to_bytes

# Compiled ICS bytes cached per (interest, series, from_date, to_date), per worker process.
_ics_cache: dict = {}

ICS_CACHE_TTL = 15 * 60  # rebuild at most once per 15 minutes per series


def _parse_date_params() -> tuple[date | None, date | None]:
    """Parse ?year=YYYY or ?from=YYYY-MM-DD&to=YYYY-MM-DD query params."""
    year_str = request.args.get('year')
    if year_str:
        try:
            year = int(year_str)
            return date(year, 1, 1), date(year, 12, 31)
        except (ValueError, TypeError):
            abort(400)
    from_str = request.args.get('from')
    to_str = request.args.get('to')
    try:
        from_date = date.fromisoformat(from_str) if from_str else None
        to_date = date.fromisoformat(to_str) if to_str else None
    except ValueError:
        abort(400)
    return from_date, to_date


@bp.route('/<interest>/calendars/<series>.ics')
def calendar_feed(series):
    # interest is consumed from URL values by the pull_interest preprocessor -> g.interest
    interest = g.interest
    uinterest = interest.upper()
    filename = f'{series}.ics'

    tag_groups = get_tag_groups(current_app.config.get(f'CALENDAR_TAG_GROUPS_{uinterest}'))
    if filename not in tag_groups:
        abort(404)

    from_date, to_date = _parse_date_params()
    cache_key = (interest, series, from_date, to_date)
    cached = _ics_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < ICS_CACHE_TTL:
        return _ics_response(cached[1], filename)

    base_url = current_app.config[f'DISCOURSE_API_URL_{uinterest}']
    discourse = make_discourse_client(interest)

    ics_bytes = filter_one_to_bytes(
        base_url=base_url,
        discourse=discourse,
        series_filename=filename,
        tag_groups=tag_groups,
        from_date=from_date,
        to_date=to_date,
        log=current_app.logger,
    )
    _ics_cache[cache_key] = (time.time(), ics_bytes)
    return _ics_response(ics_bytes, filename)


def _ics_response(ics_bytes: bytes, filename: str):
    return send_file(
        BytesIO(ics_bytes),
        mimetype='text/calendar',
        as_attachment=True,
        download_name=filename,
    )
