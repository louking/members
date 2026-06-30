"""
community_calendar_views - on-demand per-series ICS calendar feeds
"""

# standard
import time
from io import BytesIO

# pypi
from flask import current_app, g, abort, send_file

# homegrown
from . import bp
from members.community import make_discourse_client
from members.community_calendar import get_tag_groups, filter_one_to_bytes

# In-memory caches, per worker process.
# _tag_cache: topic_id_str -> {"tags": [...], "fetched_at": float}
# _ics_cache: (interest, series) -> (fetched_at, ics_bytes)
_tag_cache: dict = {}
_ics_cache: dict = {}

ICS_CACHE_TTL = 15 * 60  # rebuild at most once per 15 minutes per series


@bp.route('/<interest>/calendars/<series>.ics')
def calendar_feed(series):
    # interest is consumed from URL values by the pull_interest preprocessor -> g.interest
    interest = g.interest
    uinterest = interest.upper()
    filename = f'{series}.ics'

    tag_groups = get_tag_groups(current_app.config.get(f'CALENDAR_TAG_GROUPS_{uinterest}'))
    if filename not in tag_groups:
        abort(404)

    cache_key = (interest, series)
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
        tag_cache=_tag_cache,
        cache_ttl=3600,
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
