"""Meetings Module: automatic status report generation

Revision ID: 59cb1cd31420
Revises: 6c091e0fbcbe
Create Date: 2020-11-11 07:12:01.911002

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '59cb1cd31420'
down_revision = '6c091e0fbcbe'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('discussionitem', sa.Column('update_time', sa.DateTime(), nullable=True))
    op.add_column('meeting', sa.Column('last_status_gen', sa.DateTime(), nullable=True))
    op.alter_column('meeting', 'time',
               existing_type=mysql.VARCHAR(length=8),
               type_=sa.Text(),
               existing_nullable=True)
    op.add_column('statusreport', sa.Column('update_time', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###

    # default discussionitem.update_time and statusreport.update_time to now()
    from datetime import datetime
    from sqlalchemy.sql import table, column
    discussionitem = table('discussionitem',
                     column('update_time', sa.DateTime()))
    statusreport = table('statusreport',
                     column('update_time', sa.DateTime()))
    now = datetime.now()
    op.execute(
        discussionitem.update().\
            values({'update_time':now})
    )
    op.execute(
        statusreport.update().\
            values({'update_time':now})
    )


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('statusreport', 'update_time')
    op.alter_column('meeting', 'time',
               existing_type=sa.Text(),
               type_=mysql.VARCHAR(length=8),
               existing_nullable=True)
    op.drop_column('meeting', 'last_status_gen')
    op.drop_column('discussionitem', 'update_time')
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
