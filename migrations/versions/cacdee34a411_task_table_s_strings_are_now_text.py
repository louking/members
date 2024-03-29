"""task: table's strings are now text

Revision ID: cacdee34a411
Revises: 20c21e6832e2
Create Date: 2022-02-09 16:23:19.636297

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'cacdee34a411'
down_revision = '20c21e6832e2'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('task', 'description',
               existing_type=mysql.VARCHAR(length=512),
               type_=sa.Text(),
               existing_nullable=True)
    op.alter_column('task', 'task',
               existing_type=mysql.VARCHAR(length=64),
               type_=sa.Text(),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('task', 'task',
               existing_type=sa.Text(),
               type_=mysql.VARCHAR(length=64),
               existing_nullable=True)
    op.alter_column('task', 'description',
               existing_type=sa.Text(),
               type_=mysql.VARCHAR(length=512),
               existing_nullable=True)
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###

