"""rt_member table: add is_active

Revision ID: 25357c03de7f
Revises: 2f780fa90f7b
Create Date: 2022-11-18 16:12:51.921208

"""
from alembic import op
import sqlalchemy as sa

from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision = '25357c03de7f'
down_revision = '2f780fa90f7b'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('rt_member', sa.Column('is_active', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###

    # default rt_member.is_active to True
    rt_member = table('rt_member',
                     column('is_active', sa.Boolean()))
    op.execute(
        rt_member.update().\
            values({'is_active':op.inline_literal(True)})
    )

def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('rt_member', 'is_active')
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###

