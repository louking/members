"""meetingtype: renew options, meeting tags

Revision ID: 600d376397c5
Revises: 7a96f84c8433
Create Date: 2021-03-26 07:10:48.023786

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '600d376397c5'
down_revision = '7a96f84c8433'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('meetingtypeinvite_tag',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meetingtype_id', sa.Integer(), nullable=True),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['meetingtype_id'], ['meetingtype.id'], ),
    sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('meetingtypestatusreport_tag',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meetingtype_id', sa.Integer(), nullable=True),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['meetingtype_id'], ['meetingtype.id'], ),
    sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('meetingtypevote_tag',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meetingtype_id', sa.Integer(), nullable=True),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['meetingtype_id'], ['meetingtype.id'], ),
    sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('meetingtype', sa.Column('renewoptions', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('meetingtype', 'renewoptions')
    op.drop_table('meetingtypevote_tag')
    op.drop_table('meetingtypestatusreport_tag')
    op.drop_table('meetingtypeinvite_tag')
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
