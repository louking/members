"""add slug to system, systemaccesslevel, and accesstype, for use in the bootstrap CSVs (#716)

Revision ID: 214b0daddc9d
Revises: 326ce70b31d1
Create Date: 2026-08-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '214b0daddc9d'
down_revision = '326ce70b31d1'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()


def upgrade_():
    op.add_column('system', sa.Column('slug', sa.String(length=128), nullable=True))
    op.add_column('systemaccesslevel', sa.Column('slug', sa.String(length=128), nullable=True))
    op.add_column('accesstype', sa.Column('slug', sa.String(length=128), nullable=True))


def downgrade_():
    op.drop_column('accesstype', 'slug')
    op.drop_column('systemaccesslevel', 'slug')
    op.drop_column('system', 'slug')


def upgrade_users():
    pass


def downgrade_users():
    pass
