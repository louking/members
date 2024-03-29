"""add taskcompletion indexes for task,position; task;user

Revision ID: 2f780fa90f7b
Revises: 5e2c1cc0f027
Create Date: 2022-10-21 14:02:23.781819

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f780fa90f7b'
down_revision = '5e2c1cc0f027'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('taskcompletion_taskid_localuserid_idx', 'taskcompletion', ['task_id', 'user_id'], unique=False)
    op.create_index('taskcompletion_taskid_positionid_idx', 'taskcompletion', ['task_id', 'position_id'], unique=False)
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('taskcompletion_taskid_positionid_idx', table_name='taskcompletion')
    
    ### NOTE: second drop gets error; therefore this db migration must be left in place
    #### sqlalchemy.exc.OperationalError: (MySQLdb.OperationalError) (1553, "Cannot drop index 'taskcompletion_taskid_localuserid_idx': needed in a foreign key constraint")
    op.drop_index('taskcompletion_taskid_localuserid_idx', table_name='taskcompletion')
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###

