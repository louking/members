"""refactor DiscussionsItem linkage

Revision ID: 66928e802c36
Revises: 2a164fc330d0
Create Date: 2020-08-13 17:10:36.431829

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '66928e802c36'
down_revision = '2a164fc330d0'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('memberstatusreport_discussionitem')
    op.add_column('discussionitem', sa.Column('statusreport_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'discussionitem', 'statusreport', ['statusreport_id'], ['id'])
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'discussionitem', type_='foreignkey')
    op.drop_column('discussionitem', 'statusreport_id')
    op.create_table('memberstatusreport_discussionitem',
    sa.Column('memberstatusreport_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('discussionitem_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['discussionitem_id'], ['discussionitem.id'], name='memberstatusreport_discussionitem_ibfk_1'),
    sa.ForeignKeyConstraint(['memberstatusreport_id'], ['memberstatusreport.id'], name='memberstatusreport_discussionitem_ibfk_2'),
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
