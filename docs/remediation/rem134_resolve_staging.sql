-- REM-134 planning-year resolution — STAGING
-- Verified against staging 2026-08-23; alembic revision 0ae75ee5aed6, 1 duplicate group.
--
-- The group is 703 SQN year 2064: six rows, every one named
-- "2064 Session-Class Test Year <timestamp>", all created within 60 seconds on
-- 2026-08-09. Test debris from an automated run, on a synthetic environment.
--
-- MORE THAN ONE row carries data, so planning_year_resolution_sql.py would not
-- resolve this automatically and asked for a decision. What follows is a
-- judgement, not a derivation:
--
--   KEEP    856c3d14   13 parade dates, 5 training classes   <- the substantive row
--   ARCHIVE 7783e831   no dependents
--   ARCHIVE 6a196045   no dependents
--   ARCHIVE 22a6790e   no dependents
--   ARCHIVE 46bff487   no dependents
--   ARCHIVE 629ea352   1 holiday period   <- NOT empty; archiving hides that holiday
--
-- 629ea352 is the only real call here. It holds a single holiday period created
-- by the same test run. On synthetic staging data that is acceptable. The same
-- reasoning does NOT transfer to production — see rem134_resolve_production.sql,
-- where every archived row is genuinely empty.
--
-- Nothing is deleted. Archiving is reversible; the statement to undo it is at the
-- bottom of this file.

BEGIN;

UPDATE planning_years SET active_status = false, updated_at = now()
WHERE id IN (
    '7783e831-2a8b-4855-b3cf-e52521eb7ff0',
    '6a196045-e82f-4ac9-93dd-6a871234d3cb',
    '22a6790e-3767-42c1-b8b7-c3cbc79d0ac6',
    '46bff487-3649-4e45-96bb-8382ff2107b1',
    '629ea352-8f2a-42d4-9e52-107b3c80cad8'
);
-- expect: UPDATE 5

-- Verify BEFORE committing. All three must hold.
SELECT count(*) AS duplicate_groups_must_be_zero FROM (
  SELECT unit_id, year FROM planning_years
  WHERE unit_id IS NOT NULL AND active_status
  GROUP BY unit_id, year HAVING count(*) > 1) x;

SELECT count(*) AS rows_2064_must_be_six FROM planning_years WHERE year = 2064;

SELECT active_status AS kept_row_must_be_true FROM planning_years
WHERE id = '856c3d14-7dca-4dd9-ad1b-18a9a987c52d';

COMMIT;   -- or ROLLBACK; if any check failed


-- ── Reversal ────────────────────────────────────────────────────────────────
-- UPDATE planning_years SET active_status = true WHERE id IN (
--     '7783e831-2a8b-4855-b3cf-e52521eb7ff0',
--     '6a196045-e82f-4ac9-93dd-6a871234d3cb',
--     '22a6790e-3767-42c1-b8b7-c3cbc79d0ac6',
--     '46bff487-3649-4e45-96bb-8382ff2107b1',
--     '629ea352-8f2a-42d4-9e52-107b3c80cad8');


-- ── After this runs ─────────────────────────────────────────────────────────
-- Staging is then clear to migrate (0ae75ee5aed6 -> d1e4f8a03b27, 4 migrations).
-- Migrate via a deploy rather than by running alembic against the database on
-- its own: 821e2a4bc3e6 rewrites timing_blocks.block_type values, and the
-- currently deployed staging backend predates that taxonomy. Migrating without
-- shipping the matching code would leave staging's running app reading values it
-- does not understand.
