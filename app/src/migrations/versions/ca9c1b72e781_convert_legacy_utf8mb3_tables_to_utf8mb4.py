"""convert legacy utf8mb3 tables to utf8mb4 (#714)

Revision ID: ca9c1b72e781
Revises: c144e7fbb0d0
Create Date: 2026-08-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ca9c1b72e781'
down_revision = 'c144e7fbb0d0'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()


# Every table in this schema created before the MySQL 8.0 upgrade was left on the
# old 3-byte utf8mb3 charset (MySQL's historical "utf8"), even though the database's
# own default has been utf8mb4 since then -- new tables (awards_*, discoursereviewnotice)
# picked up utf8mb4 automatically because CREATE TABLE follows the schema default at
# creation time, but existing tables don't retroactively follow a later default change.
# utf8mb3 can't store 4-byte characters (emoji, some CJK extension-B characters), so
# free-text fields fail with "Incorrect string value: '\xF0\x9F\x8F\x83...'" (#714)
# whenever a user pastes one in -- statusreport.statusreport was the one hit, but
# every other utf8mb3 table's text columns have the same latent problem.
#
# Convert every remaining utf8mb3 table to utf8mb4/utf8mb4_0900_ai_ci -- the collation
# already in use by the tables created since the MySQL 8.0 upgrade -- rather than
# hardcoding a table list, so this also covers any utf8mb3 table this pass missed.
def upgrade_():
    bind = op.get_bind()
    tables = bind.execute(sa.text(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_COLLATION LIKE 'utf8mb3%'"
    )).scalars().all()
    for table in tables:
        bind.execute(sa.text(
            f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
        ))


def downgrade_():
    # charset widening only -- no data loss, not worth reversing
    pass


def upgrade_users():
    pass


def downgrade_users():
    pass
