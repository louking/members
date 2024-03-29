"""member: add svc_member_id

Revision ID: 8ee7d707ada1
Revises: 3128fd553322
Create Date: 2021-10-27 14:48:46.950377

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ee7d707ada1'
down_revision = '3128fd553322'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('member', sa.Column('svc_member_id', sa.String(length=24), nullable=True))
    op.create_index('member_member_id', 'member', ['svc_member_id'], unique=False)
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('member_member_id', table_name='member')
    op.drop_column('member', 'svc_member_id')
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###

