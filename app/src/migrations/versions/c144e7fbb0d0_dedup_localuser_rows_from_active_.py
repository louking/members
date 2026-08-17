"""dedup localuser rows from active-filter bug (loutilities#103)

Revision ID: c144e7fbb0d0
Revises: 44975ae71024
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c144e7fbb0d0'
down_revision = '44975ae71024'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()


# ManageLocalTables._updateuser_byinterest() (loutilities/user/model.py) used to seed
# its "which rows already exist" lookup from active=True rows only. Once a localuser
# row's active flag went False, the next update_local_tables() call couldn't find it,
# so it inserted a duplicate row instead of updating the existing one -- one new
# duplicate per call, forever, for every inactive user. Fixed in loutilities#103
# (loutilities==3.13.0.dev2). This migration cleans up the rows that bug already
# created.
#
# For each (user_id, interest_id) group with more than one row, keep exactly one row
# and delete the rest:
#   - prefer a row referenced by another table's FK (user_taskgroup, user_position,
#     user_position_dates, taskcompletion, meeting, invite, actionitem, motion,
#     motionvote, rt_member, localuser_tag -- every FK to localuser.id in this schema)
#   - else prefer the active row
#   - else keep the lowest id (oldest row)
#
# A group is left untouched (no deletes at all) if more than one row in it is
# FK-referenced or more than one is active -- that's a genuine ambiguity the automated
# pass can't safely resolve; review those manually. Confirmed against a full dev-data
# snapshot (2026-08-17): every duplicate group had at most one referenced and at most
# one active row, so nothing was left ambiguous there, but this repo's data may differ.
_DEDUP_LOCALUSER_SQL = """
WITH referenced_localuser_ids AS (
    SELECT DISTINCT id FROM (
        SELECT user_id      AS id FROM user_taskgroup      WHERE user_id      IS NOT NULL
        UNION ALL SELECT user_id      FROM user_position         WHERE user_id      IS NOT NULL
        UNION ALL SELECT user_id      FROM user_position_dates   WHERE user_id      IS NOT NULL
        UNION ALL SELECT user_id      FROM taskcompletion        WHERE user_id      IS NOT NULL
        UNION ALL SELECT organizer_id FROM meeting               WHERE organizer_id IS NOT NULL
        UNION ALL SELECT user_id      FROM invite                WHERE user_id      IS NOT NULL
        UNION ALL SELECT assignee_id  FROM actionitem            WHERE assignee_id  IS NOT NULL
        UNION ALL SELECT mover_id     FROM motion                WHERE mover_id     IS NOT NULL
        UNION ALL SELECT seconder_id  FROM motion                WHERE seconder_id  IS NOT NULL
        UNION ALL SELECT user_id      FROM motionvote            WHERE user_id      IS NOT NULL
        UNION ALL SELECT localuser_id FROM rt_member             WHERE localuser_id IS NOT NULL
        UNION ALL SELECT localuser_id FROM localuser_tag         WHERE localuser_id IS NOT NULL
    ) refs
),
ranked AS (
    SELECT l.id,
           ROW_NUMBER() OVER (
               PARTITION BY l.user_id, l.interest_id
               ORDER BY (l.id IN (SELECT id FROM referenced_localuser_ids)) DESC,
                        l.active DESC,
                        l.id ASC
           ) AS rn,
           COUNT(*) OVER (PARTITION BY l.user_id, l.interest_id) AS grp_count,
           SUM(l.id IN (SELECT id FROM referenced_localuser_ids))
               OVER (PARTITION BY l.user_id, l.interest_id) AS grp_referenced_count,
           SUM(l.active) OVER (PARTITION BY l.user_id, l.interest_id) AS grp_active_count
    FROM localuser l
    WHERE l.user_id IS NOT NULL AND l.interest_id IS NOT NULL
)
DELETE FROM localuser WHERE id IN (
    SELECT id FROM (
        SELECT id FROM ranked
        WHERE grp_count > 1 AND rn > 1 AND grp_referenced_count <= 1 AND grp_active_count <= 1
    ) AS to_delete
)
"""


def upgrade_():
    op.get_bind().execute(sa.text(_DEDUP_LOCALUSER_SQL))


def downgrade_():
    # data cleanup only -- deleted duplicate rows can't be reconstructed
    pass


def upgrade_users():
    pass


def downgrade_users():
    pass
