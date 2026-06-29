"""v11 TRGO Planning Module

Adds tables for the annual training planning workflow:
  - planning_years       — squadron planning year record
  - parade_dates         — planned parade night dates within a year
  - holiday_periods      — holiday/stand-down periods
  - anchor_events        — fixed events planned around
  - anchor_prep_rules    — seeded rule set for prep-lesson suggestions
  - anchor_prep_plans    — prep lessons linked to anchor events
  - scheduled_sessions   — parade-night builder grid cells
  - planning_locations   — rooms / outdoor areas for scheduling
  - planning_conflicts   — detected conflicts with override support

Revision ID: f3a1b5c9d7e2
Revises: e6f8a2d4c1b3
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a1b5c9d7e2'
down_revision = 'e6f8a2d4c1b3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'planning_years',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('unit_id', sa.String(36), sa.ForeignKey('squadrons.id'), nullable=True),
        sa.Column('wing_id', sa.String(36), nullable=True),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('active_status', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_planning_years_unit_id', 'planning_years', ['unit_id'])
    op.create_index('ix_planning_years_wing_id', 'planning_years', ['wing_id'])

    op.create_table(
        'parade_dates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('planning_year_id', sa.String(36), sa.ForeignKey('planning_years.id'), nullable=False),
        sa.Column('unit_id', sa.String(36), sa.ForeignKey('squadrons.id'), nullable=True),
        sa.Column('parade_date', sa.String(10), nullable=False),
        sa.Column('parade_type', sa.String(30), nullable=False, server_default='standard'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_parade_dates_planning_year_id', 'parade_dates', ['planning_year_id'])
    op.create_index('ix_parade_dates_unit_id', 'parade_dates', ['unit_id'])

    op.create_table(
        'holiday_periods',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('planning_year_id', sa.String(36), sa.ForeignKey('planning_years.id'), nullable=False),
        sa.Column('jurisdiction', sa.String(40), nullable=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('start_date', sa.String(10), nullable=False),
        sa.Column('end_date', sa.String(10), nullable=False),
        sa.Column('affects_parade', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_holiday_periods_planning_year_id', 'holiday_periods', ['planning_year_id'])

    op.create_table(
        'anchor_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('planning_year_id', sa.String(36), sa.ForeignKey('planning_years.id'), nullable=False),
        sa.Column('owning_level', sa.String(20), nullable=False, server_default='unit'),
        sa.Column('wing_id', sa.String(36), nullable=True),
        sa.Column('unit_id', sa.String(36), sa.ForeignKey('squadrons.id'), nullable=True),
        sa.Column('event_name', sa.String(200), nullable=False),
        sa.Column('event_type', sa.String(40), nullable=False, server_default='other'),
        sa.Column('importance', sa.String(20), nullable=False, server_default='key_event'),
        sa.Column('start_date', sa.String(10), nullable=False),
        sa.Column('end_date', sa.String(10), nullable=True),
        sa.Column('audience_orientation', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('audience_initial', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('audience_junior', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('audience_intermediate', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('audience_senior', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('planning_impact', sa.Text, nullable=True),
        sa.Column('readiness_requirements', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_archived', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_anchor_events_planning_year_id', 'anchor_events', ['planning_year_id'])
    op.create_index('ix_anchor_events_wing_id', 'anchor_events', ['wing_id'])
    op.create_index('ix_anchor_events_unit_id', 'anchor_events', ['unit_id'])

    op.create_table(
        'anchor_prep_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(40), nullable=False),
        sa.Column('subject_area', sa.String(80), nullable=True),
        sa.Column('suggested_curriculum_tags', sa.Text, nullable=True),
        sa.Column('weeks_before_min', sa.Integer, nullable=False, server_default='1'),
        sa.Column('weeks_before_max', sa.Integer, nullable=False, server_default='3'),
        sa.Column('suggested_activity', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_anchor_prep_rules_event_type', 'anchor_prep_rules', ['event_type'])

    op.create_table(
        'anchor_prep_plans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('anchor_event_id', sa.String(36), sa.ForeignKey('anchor_events.id'), nullable=False),
        sa.Column('curriculum_id', sa.String(36), sa.ForeignKey('curriculum_items.id'), nullable=True),
        sa.Column('planned_parade_date_id', sa.String(36), sa.ForeignKey('parade_dates.id'), nullable=True),
        sa.Column('planned_session_number', sa.Integer, nullable=True),
        sa.Column('cadet_group', sa.String(30), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='planned'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_anchor_prep_plans_anchor_event_id', 'anchor_prep_plans', ['anchor_event_id'])

    op.create_table(
        'planning_locations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('unit_id', sa.String(36), sa.ForeignKey('squadrons.id'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('location_type', sa.String(30), nullable=False, server_default='indoor'),
        sa.Column('capacity', sa.Integer, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('active_status', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_planning_locations_unit_id', 'planning_locations', ['unit_id'])

    op.create_table(
        'scheduled_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('parade_date_id', sa.String(36), sa.ForeignKey('parade_dates.id'), nullable=False),
        sa.Column('unit_id', sa.String(36), sa.ForeignKey('squadrons.id'), nullable=False),
        sa.Column('cadet_group', sa.String(30), nullable=False),
        sa.Column('session_number', sa.Integer, nullable=False),
        sa.Column('curriculum_id', sa.String(36), sa.ForeignKey('curriculum_items.id'), nullable=True),
        sa.Column('activity_title', sa.String(200), nullable=True),
        sa.Column('facilitator_id', sa.String(36), sa.ForeignKey('facilitators.id'), nullable=True),
        sa.Column('location_id', sa.String(36), sa.ForeignKey('planning_locations.id'), nullable=True),
        sa.Column('is_combined', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('combined_groups', sa.JSON, nullable=True),
        sa.Column('override_conflict', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('override_reason', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_archived', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_scheduled_sessions_parade_date_id', 'scheduled_sessions', ['parade_date_id'])
    op.create_index('ix_scheduled_sessions_unit_id', 'scheduled_sessions', ['unit_id'])

    op.create_table(
        'planning_conflicts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('planning_year_id', sa.String(36), sa.ForeignKey('planning_years.id'), nullable=True),
        sa.Column('parade_date_id', sa.String(36), sa.ForeignKey('parade_dates.id'), nullable=True),
        sa.Column('scheduled_session_id', sa.String(36), sa.ForeignKey('scheduled_sessions.id'), nullable=True),
        sa.Column('conflict_type', sa.String(60), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False, server_default='warning'),
        sa.Column('message', sa.String(400), nullable=False),
        sa.Column('is_resolved', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('override_reason', sa.Text, nullable=True),
        sa.Column('resolved_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_planning_conflicts_planning_year_id', 'planning_conflicts', ['planning_year_id'])


def downgrade():
    op.drop_table('planning_conflicts')
    op.drop_table('scheduled_sessions')
    op.drop_table('planning_locations')
    op.drop_table('anchor_prep_plans')
    op.drop_table('anchor_prep_rules')
    op.drop_table('anchor_events')
    op.drop_table('holiday_periods')
    op.drop_table('parade_dates')
    op.drop_table('planning_years')
