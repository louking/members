"""agendaheading table

Revision ID: cbac9afeaa40
Revises: 128c7e32169e
Create Date: 2020-08-29 16:10:33.670629

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cbac9afeaa40'
down_revision = '128c7e32169e'
branch_labels = None
depends_on = None


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('agendaheading',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('interest_id', sa.Integer(), nullable=True),
    sa.Column('heading', sa.Text(), nullable=True),
    sa.Column('version_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['interest_id'], ['localinterest.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('agendaitem', sa.Column('agendaheading_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'agendaitem', 'agendaheading', ['agendaheading_id'], ['id'])
    op.add_column('position', sa.Column('agendaheading_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'position', 'agendaheading', ['agendaheading_id'], ['id'])
    # ### end Alembic commands ###


def downgrade_():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'position', type_='foreignkey')
    op.drop_column('position', 'agendaheading_id')
    op.drop_constraint(None, 'agendaitem', type_='foreignkey')
    op.drop_column('agendaitem', 'agendaheading_id')
    op.drop_table('agendaheading')
    # ### end Alembic commands ###


def upgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade_users():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###

