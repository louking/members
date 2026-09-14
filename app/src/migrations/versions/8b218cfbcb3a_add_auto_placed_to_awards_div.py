"""add auto_placed to awards_div (#723)

Revision ID: 8b218cfbcb3a
Revises: 214b0daddc9d
Create Date: 2026-09-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b218cfbcb3a'
down_revision = '214b0daddc9d'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()


def upgrade_():
    op.add_column('awards_div', sa.Column('auto_placed', sa.Boolean(), nullable=True))


def downgrade_():
    op.drop_column('awards_div', 'auto_placed')


def upgrade_users():
    pass


def downgrade_users():
    pass
