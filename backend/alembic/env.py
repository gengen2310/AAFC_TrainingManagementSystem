"""Alembic environment. Uses the app's metadata and DATABASE_URL.

For the SQLite demo, tables are also created at startup; in production run
`alembic upgrade head` before launching the app (see DEPLOYMENT.md).
"""
import os, sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from alembic.operations import ops

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import normalize_database_url, settings  # noqa: E402
from app.database import Base            # noqa: E402
from app import models                   # noqa: F401,E402

config = context.config
database_url = normalize_database_url(settings.DATABASE_URL)
config.set_main_option("sqlalchemy.url", database_url)
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

# The current migration chain intentionally preserves several compatibility
# objects while the ORM has moved to the replacement models.  Alembic's
# autogenerate compares the live, migrated schema with current metadata, so
# these exact differences otherwise appear as upgrade operations on every
# clean database.  Keep this allowlist narrow: each entry is a known
# compatibility or dialect representation difference, not a blanket
# comparison disable.
_COMPATIBILITY_TABLES = {"_parade_dates_deprecated"}
_COMPATIBILITY_INDEXES = {
    "ix_parade_dates_parade_night_id",
    "ix_parade_dates_planning_year_id",
    "ix_parade_dates_unit_id",
    "ix_activities_owning_level_archived",
    "ix_activities_squadron_archived_date",
    "ix_activities_wing_archived_date",
    "ix_pnts_night_period",
    "uq_parade_night_sqn_date_active",
    "ix_timing_blocks_template_id",
    "ix_planning_notices_parade_date_id",
    "ix_scpa_custom_phase",
    "ix_scpa_session",
    "ix_planning_notices_parade_night_id",
}
_MODEL_INDEXES_WITHOUT_FORWARD_MIGRATION = {
    "ix_anchor_events_is_archived",
    "ix_curriculum_elements_is_archived",
    "ix_curriculum_phases_is_archived",
    "ix_parade_night_timing_overrides_is_archived",
    "ix_parade_night_timing_overrides_timing_template_id",
    "ix_parade_nights_planning_year_id",
    "ix_session_custom_phase_audiences_custom_phase_id",
    "ix_session_custom_phase_audiences_session_id",
    "ix_timing_blocks_timing_template_id",
    "ix_wing_hq_events_is_archived",
}
_COMPATIBILITY_CONSTRAINTS = {
    "uq_session_audience_session_class",
    "uq_session_audience_pair",
}
_LEGACY_NULLABILITY_COLUMNS = {
    ("activity_local_hides", "created_at"),
    ("activity_local_hides", "updated_at"),
    ("activity_local_overrides", "created_at"),
    ("activity_local_overrides", "updated_at"),
    ("activity_type_tags", "created_at"),
    ("activity_type_tags", "updated_at"),
    ("anchor_events", "created_at"),
    ("anchor_events", "updated_at"),
    ("anchor_prep_plans", "created_at"),
    ("anchor_prep_plans", "updated_at"),
    ("anchor_prep_rules", "created_at"),
    ("anchor_prep_rules", "updated_at"),
    ("cadet_member_import_batches", "created_at"),
    ("cadet_member_import_batches", "updated_at"),
    ("cadet_session_outcomes", "created_at"),
    ("cadet_session_outcomes", "updated_at"),
    ("cea_activities", "source_type"),
    ("cea_activities", "classification_status"),
    ("cea_activities", "created_at"),
    ("cea_activities", "updated_at"),
    ("cea_import_batches", "row_count"),
    ("cea_import_batches", "created_count"),
    ("cea_import_batches", "updated_count"),
    ("cea_import_batches", "duplicate_count"),
    ("cea_import_batches", "skipped_count"),
    ("cea_import_batches", "error_count"),
    ("cea_import_batches", "created_at"),
    ("cea_import_batches", "updated_at"),
    ("curriculum_elements", "created_at"),
    ("curriculum_elements", "updated_at"),
    ("curriculum_items", "part_number"),
    ("curriculum_phases", "created_at"),
    ("curriculum_phases", "updated_at"),
    ("facilitator_type_tags", "created_at"),
    ("facilitator_type_tags", "updated_at"),
    ("faq_entries", "created_at"),
    ("faq_entries", "updated_at"),
    ("holiday_periods", "created_at"),
    ("holiday_periods", "updated_at"),
    ("planning_conflicts", "created_at"),
    ("planning_conflicts", "updated_at"),
    ("planning_facilitator_leave", "created_at"),
    ("planning_facilitator_leave", "updated_at"),
    ("planning_notices", "created_at"),
    ("planning_notices", "updated_at"),
    ("planning_years", "created_at"),
    ("planning_years", "updated_at"),
    ("recovery_tokens", "created_at"),
    ("recovery_tokens", "updated_at"),
    ("session_status_reason_tags", "created_at"),
    ("session_status_reason_tags", "updated_at"),
    ("squadron_event_status", "created_at"),
    ("squadron_event_status", "updated_at"),
    ("subject_area_tags", "created_at"),
    ("subject_area_tags", "updated_at"),
    ("training_area_capability_tags", "created_at"),
    ("training_area_capability_tags", "updated_at"),
    ("wing_event_curriculum_links", "created_at"),
    ("wing_event_curriculum_links", "updated_at"),
    ("wing_hq_events", "created_at"),
    ("wing_hq_events", "updated_at"),
}
_LEGACY_FOREIGN_KEYS = {
    ("activity_type_tags", "national_id", "national_entities"),
    ("anchor_prep_plans", "planned_parade_night_id", "_parade_dates_deprecated"),
    ("anchor_prep_plans", "planned_parade_night_id", "parade_nights"),
    ("cadet_session_outcomes", "cadet_id", "cadets"),
    ("cadet_session_outcomes", "session_id", "sessions"),
    ("facilitator_type_tags", "national_id", "national_entities"),
    ("facilitator_type_tags", "squadron_id", "squadrons"),
    ("planning_conflicts", "parade_night_id", "parade_nights"),
    ("planning_conflicts", "parade_night_id", "_parade_dates_deprecated"),
    ("planning_conflicts", "parade_night_id", "parade_dates"),
    ("planning_conflicts", "scheduled_session_id", "scheduled_sessions"),
    ("planning_notices", "parade_night_id", "parade_nights"),
    ("planning_notices", "parade_night_id", "_parade_dates_deprecated"),
    ("planning_notices", "parade_night_id", "parade_dates"),
    ("session_status_reason_tags", "national_id", "national_entities"),
    ("session_status_reason_tags", "squadron_id", "squadrons"),
    ("subject_area_tags", "national_id", "national_entities"),
    ("subject_area_tags", "squadron_id", "squadrons"),
    ("training_area_capability_tags", "national_id", "national_entities"),
    ("users", "recovery_email_updated_by", "users"),
}


def include_object(object_, name, type_, reflected, compare_to):
    """Exclude only documented legacy/dialect objects from autogenerate."""
    table_name = getattr(getattr(object_, "table", None), "name", None)
    if type_ == "table" and name in _COMPATIBILITY_TABLES:
        return False
    if type_ == "index" and name in (_COMPATIBILITY_INDEXES | _MODEL_INDEXES_WITHOUT_FORWARD_MIGRATION):
        return False
    if type_ in {"unique_constraint", "primary_key_constraint"} and name in _COMPATIBILITY_CONSTRAINTS:
        return False
    if type_ == "foreign_key_constraint":
        elements = list(getattr(object_, "elements", ()) or ())
        constrained = [element.parent.name for element in elements]
        referred = elements[0].target_fullname.rsplit(".", 1)[0] if elements else None
        if constrained and (table_name, constrained[0], referred) in _LEGACY_FOREIGN_KEYS:
            return False
    return True


def _strip_known_nullability_ops(container) -> None:
    """Remove only known nullable-only drift from an autogenerate op tree.

    The old include_object filter hid the *entire column*, which also hid a
    missing column or future type/default changes. Keeping the column in the
    comparison and deleting only modify_nullable preserves all other drift.
    """
    kept = []
    for operation in container.ops:
        if isinstance(operation, ops.ModifyTableOps):
            _strip_known_nullability_ops(operation)
            if operation.ops:
                kept.append(operation)
            continue
        if isinstance(operation, ops.AlterColumnOp):
            key = (operation.table_name, operation.column_name)
            if key in _LEGACY_NULLABILITY_COLUMNS and operation.modify_nullable is not None:
                operation.modify_nullable = None
                if operation.has_changes():
                    kept.append(operation)
                continue
        kept.append(operation)
    container.ops[:] = kept


def process_revision_directives(context_, revision, directives):
    """Autogenerate hook: suppress only allow-listed nullability alterations."""
    if not directives:
        return
    script = directives[0]
    for upgrade_ops in script.upgrade_ops_list:
        _strip_known_nullability_ops(upgrade_ops)
    for downgrade_ops in script.downgrade_ops_list:
        _strip_known_nullability_ops(downgrade_ops)


def compare_type(context_, inspected_column, metadata_column, inspected_type, metadata_type):
    # facilitators.subject_areas is JSON in metadata but TEXT in the historical
    # SQLite/PostgreSQL representation; the application serializer handles both.
    if inspected_column.table.name == "facilitators" and inspected_column.name == "subject_areas":
        return False
    return None


def run_migrations_offline():
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True,
                      include_object=include_object, compare_type=compare_type,
                      process_revision_directives=process_revision_directives)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    cfg = config.get_section(config.config_ini_section)
    cfg["sqlalchemy.url"] = database_url
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          include_object=include_object, compare_type=compare_type,
                          process_revision_directives=process_revision_directives)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
