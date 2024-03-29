"""add member, membership, tableupdatetime tables

Revision ID: 3128fd553322
Revises: 53052ccb8a54
Create Date: 2021-10-25 13:12:33.517427

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3128fd553322'
down_revision = '53052ccb8a54'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('member',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('interest_id', sa.Integer(), nullable=True),
    sa.Column('family_name', sa.String(length=128), nullable=True),
    sa.Column('given_name', sa.String(length=128), nullable=True),
    sa.Column('middle_name', sa.Text(), nullable=True),
    sa.Column('gender', sa.String(length=16), nullable=True),
    sa.Column('dob', sa.Date(), nullable=True),
    sa.Column('hometown', sa.Text(), nullable=True),
    sa.Column('email', sa.Text(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('update_time', sa.DateTime(), nullable=True),
    sa.Column('version_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['interest_id'], ['localinterest.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('member_name_gender_dob_idx', 'member', ['family_name', 'given_name', 'gender', 'dob'], unique=False)
    op.create_table('tableupdatetime',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('interest_id', sa.Integer(), nullable=True),
    sa.Column('tablename', sa.Text(), nullable=True),
    sa.Column('lastchecked', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['interest_id'], ['localinterest.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('membership',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('interest_id', sa.Integer(), nullable=True),
    sa.Column('member_id', sa.Integer(), nullable=True),
    sa.Column('svc_member_id', sa.Text(), nullable=True),
    sa.Column('svc_membership_id', sa.String(length=24), nullable=True),
    sa.Column('membershiptype', sa.Text(), nullable=True),
    sa.Column('hometown', sa.Text(), nullable=True),
    sa.Column('email', sa.Text(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('primary', sa.Boolean(), nullable=True),
    sa.Column('last_modified', sa.DateTime(), nullable=True),
    sa.Column('update_time', sa.DateTime(), nullable=True),
    sa.Column('version_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['interest_id'], ['localinterest.id'], ),
    sa.ForeignKeyConstraint(['member_id'], ['member.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('membership_svc_membership_id_idx', 'membership', ['svc_membership_id'], unique=False)
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('membership_svc_membership_id_idx', table_name='membership')
    op.drop_table('membership')
    op.drop_table('tableupdatetime')
    op.drop_index('member_name_gender_dob_idx', table_name='member')
    op.drop_table('member')
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###

