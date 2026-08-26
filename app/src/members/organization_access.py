"""
organization_access — track which systems/access-levels a user's currently held
positions require, and maintain a checklist of grant/revoke actions an admin
needs to take when that changes (see #716).

A position's required access is the union of its direct_access and everything
pulled in by its accesstypes (Position.accesstypes/direct_access, model.py).
sync_access_notices() is called from both places a UserPosition row can be
created/end-dated/deleted -- PositionWizardApi.post() and PositionDateView's
editor hooks (organization_admin.py). Each caller is responsible for capturing
a user's required-access snapshot with compute_required_access() *before*
making any UserPosition changes, then calling sync_access_notices() with that
snapshot once the changes are staged (added/deleted/flushed, not necessarily
committed) -- helpers.positions_active() already accounts for in-session
pending adds/deletes, so no extra flush choreography is needed beyond what the
callers already do for their own purposes.
"""

from datetime import date, datetime, timezone

from .model import db, PositionAccessNotice
from .model import POSITIONACCESSNOTICE_ACTION_GRANT, POSITIONACCESSNOTICE_ACTION_REVOKE
from .helpers import positions_active


def compute_required_access(user, thisdate=None):
    '''
    the set of (system_id, accesslevel_id) pairs required by user's currently
    active positions as of thisdate (default today), from the union of each
    position's direct_access and its accesstypes' access

    :param user: LocalUser instance
    :param thisdate: date to check (datetime.date), default today
    :rtype: set of (system_id, accesslevel_id) tuples
    '''
    thisdate = thisdate or date.today()
    required = set()
    for position in positions_active(user, thisdate):
        for level in position.direct_access:
            required.add((level.system_id, level.id))
        for accesstype in position.accesstypes:
            for level in accesstype.access:
                required.add((level.system_id, level.id))
    return required


def _upsert_notice(interest, user, system_id, accesslevel_id, action, opposite_action,
                    reason_position, effective_date, now):
    # an unresolved notice for the opposite action is now moot -- e.g. access was
    # revoked and re-granted (or vice versa) before anyone acted on the first notice
    opposite = PositionAccessNotice.query.filter_by(
        interest=interest, user=user, system_id=system_id, accesslevel_id=accesslevel_id,
        action=opposite_action, resolved_at=None,
    ).one_or_none()
    if opposite:
        db.session.delete(opposite)

    # don't duplicate an already-unresolved notice for the same change
    existing = PositionAccessNotice.query.filter_by(
        interest=interest, user=user, system_id=system_id, accesslevel_id=accesslevel_id,
        action=action, resolved_at=None,
    ).one_or_none()
    if existing:
        return

    db.session.add(PositionAccessNotice(
        interest=interest, user=user, system_id=system_id, accesslevel_id=accesslevel_id,
        action=action, reason_position=reason_position, effective_date=effective_date, detected_at=now,
    ))


def sync_access_notices(interest, user, before_access, reason_position=None, effective_date=None):
    '''
    diff before_access (captured by the caller via compute_required_access()
    *before* making any UserPosition changes for this user) against the
    user's required access as of now, and create/clear PositionAccessNotice
    checklist rows for anything that changed.

    A (system, accesslevel) required by another still-held position never
    generates a notice, since it's in both the before and after sets -- this
    is what avoids reminding an admin to revoke access that's still justified
    by a different position (see #716).

    :param interest: LocalInterest instance
    :param user: LocalUser instance
    :param before_access: set of (system_id, accesslevel_id) from compute_required_access(),
        captured before this user's UserPosition rows were changed
    :param reason_position: Position instance that triggered this change, if known (informational only)
    :param effective_date: date the change takes effect, default today
    '''
    after_access = compute_required_access(user)
    if after_access == before_access:
        return

    effective_date = effective_date or date.today()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for system_id, accesslevel_id in after_access - before_access:
        _upsert_notice(interest, user, system_id, accesslevel_id,
                        POSITIONACCESSNOTICE_ACTION_GRANT, POSITIONACCESSNOTICE_ACTION_REVOKE,
                        reason_position, effective_date, now)

    for system_id, accesslevel_id in before_access - after_access:
        _upsert_notice(interest, user, system_id, accesslevel_id,
                        POSITIONACCESSNOTICE_ACTION_REVOKE, POSITIONACCESSNOTICE_ACTION_GRANT,
                        reason_position, effective_date, now)
