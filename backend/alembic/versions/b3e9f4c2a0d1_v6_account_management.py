"""v6 account management — flights table, users.flight_id, users.last_login_at

Revision ID: b3e9f4c2a0d1
Revises: 175e1c6e12f7
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'b3e9f4c2a0d1'
down_revision = '175e1c6e12f7'
branch_labels = None
depends_on = None


def upgrade():
    # ── New table: flights ─────────────────────────────────────────────────
    op.create_table(
        'flights',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('squadron_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('active_status', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('updated_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['squadron_id'], ['squadrons.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_flights_squadron_id', 'flights', ['squadron_id'])
    op.create_index('ix_flights_is_archived', 'flights', ['is_archived'])

    # ── New columns: users ─────────────────────────────────────────────────
    # flight_id: nullable FK — squadron-scoped users only; does not change permissions
    op.add_column('users', sa.Column('flight_id', sa.String(length=36), nullable=True))
    op.create_foreign_key('fk_users_flight_id', 'users', 'flights', ['flight_id'], ['id'])
    op.create_index('ix_users_flight_id', 'users', ['flight_id'])

    # last_login_at: set by auth/login; never exposes codes
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'last_login_at')
    op.drop_index('ix_users_flight_id', table_name='users')
    op.drop_constraint('fk_users_flight_id', 'users', type_='foreignkey')
    op.drop_column('users', 'flight_id')
    op.drop_index('ix_flights_is_archived', table_name='flights')
    op.drop_index('ix_flights_squadron_id', table_name='flights')
    op.drop_table('flights')
