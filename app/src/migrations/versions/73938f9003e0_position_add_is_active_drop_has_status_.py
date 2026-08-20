"""Position add is_active, drop has_status_report (#588)

Revision ID: 73938f9003e0
Revises: ca9c1b72e781
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision = '73938f9003e0'
down_revision = 'ca9c1b72e781'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()


def upgrade_():
    op.add_column('position', sa.Column('is_active', sa.Boolean(), nullable=True))

    # default position.is_active to True for existing rows
    position = table('position',
                     column('is_active', sa.Boolean()))
    op.execute(
        position.update().\
            values({'is_active':op.inline_literal(True)})
    )

    op.drop_column('position', 'has_status_report')


def downgrade_():
    op.add_column('position', sa.Column('has_status_report', sa.Boolean(), nullable=True))

    position = table('position',
                     column('has_status_report', sa.Boolean()))
    op.execute(
        position.update().\
            values({'has_status_report':op.inline_literal(True)})
    )

    op.drop_column('position', 'is_active')


def upgrade_users():
    pass


def downgrade_users():
    pass
