"""meetingtype: add buttonoptions

Revision ID: 27411264ffcb
Revises: cc5a2d509450
Create Date: 2021-02-27 12:54:14.737428

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '27411264ffcb'
down_revision = 'cc5a2d509450'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('meetingtype', sa.Column('buttonoptions', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('meetingtype', 'buttonoptions')
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
