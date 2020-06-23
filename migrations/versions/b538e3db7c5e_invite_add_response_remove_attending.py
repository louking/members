"""invite: add response, remove attending

Revision ID: b538e3db7c5e
Revises: c621d93adf94
Create Date: 2020-06-23 14:30:33.032588

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'b538e3db7c5e'
down_revision = 'c621d93adf94'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('invite', sa.Column('response', sa.Enum('response pending', 'attending', 'not attending'), nullable=True))
    op.drop_column('invite', 'attending')
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('invite', sa.Column('attending', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True))
    op.drop_column('invite', 'response')
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###

