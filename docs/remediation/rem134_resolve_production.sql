-- ============================================================================
-- SUPERSEDED 2026-08-28 — DO NOT RUN. Kept for the record only.
--
-- This runbook was written on 2026-08-23 and never executed. The work it
-- describes was done instead on 2026-08-28, directly and interactively, on the
-- user's instruction squadron by squadron (see REM-156). Production no longer
-- matches the state this script expects.
--
-- Running it now would FAIL its own verification block. Check 4 asserts that
-- ec1a2a05 is still active; it was archived on 2026-08-28. It would also try to
-- archive rows that are already archived, which is harmless, and would NOT
-- archive 704's 2027 row or rename anything, which is the part that mattered.
--
-- What actually happened, and why it differs:
--
--   703  archived 57b5c229 (empty)                         — as planned here
--   721  archived 6ea1640f (empty)                         — as planned here
--   704  KEPT 420e1d56 and RENAMED it "2026 test 1.0" ->
--        "2026 Training Year"; archived 0d39e637, c4aa3393,
--        and additionally its 2027 row 637247a9             — beyond this script
--   708  archived BOTH 2026 rows, INCLUDING ec1a2a05        — REVERSES the
--        decision recorded on line 24 below
--
-- The 708 reversal was deliberate. This script's note says nothing in the
-- database distinguished 708's two 2026 rows, so the choice was arbitrary. By
-- 2026-08-28 more was known: 708's only row holding parade dates is the one
-- numbered 2027 (b482b6ed, 15 dates), and both 2026 rows were empty. Keeping an
-- empty row and discarding the populated one would have been the wrong call.
--
-- Remaining after 2026-08-28: 702 and TEST still hold two active years each.
-- Both already match the intended model (a populated current year plus an empty
-- next year), so neither is a duplicate to archive.
-- ============================================================================

-- REM-134 planning-year resolution — PRODUCTION
-- Verified against production 2026-08-23; alembic revision f6a7b8c9d0e1.
-- 4 duplicate ACTIVE (unit_id, year) groups, 9 active rows, all year 2026.
--
-- LIVE SQUADRON DATA. Read this before running it.
--
-- Nothing is deleted. Rows are ARCHIVED (active_status = false), which is this
-- system's normal way to retire a planning year. Archived rows do not
-- participate in the partial unique index, which is what makes archiving a
-- sufficient resolution. It is also reversible; the undo is at the bottom.
--
-- EVERY row archived below has ZERO dependents — no parade dates, no holiday
-- periods. That was measured, not assumed. Contrast with the staging runbook,
-- where each archived row did hold a training class and that cost is stated
-- explicitly. Here there is nothing to lose.
--
--   703 2026  KEEP    c33ca5b7  4 parade dates   "2026–2027 Training Year"
--             ARCHIVE 57b5c229  no dependents    "2026–2027 Training Year"
--
--   704 2026  KEEP    420e1d56  16 parade dates  "2026 test 1.0"      <- see note
--             ARCHIVE 0d39e637  no dependents    "2026 Training Year"
--             ARCHIVE c4aa3393  no dependents    "2026–2027 Training Year"
--
--   708 2026  KEEP    ec1a2a05  no dependents    "2026 Training Year"  <- user's decision
--             ARCHIVE 79491d55  no dependents    "2026"
--
--   721 2026  KEEP    312b067d  16 parade dates  "2026–2027 Training Year"
--             ARCHIVE 6ea1640f  no dependents    "2026–2027 Training Year"
--
-- 703, 704 and 721 are mechanical: exactly one row in each group holds the
-- parade dates, so keeping it is forced by the data.
--
-- 708 was NOT mechanical. Neither of its rows has any dependents, so nothing in
-- the database distinguished them. Kept "2026 Training Year" (ec1a2a05) on the
-- user's instruction, 2026-08-23; the row named plainly "2026" is archived.
--
-- NOTE ON 704: the row that must be kept is named "2026 test 1.0", because all 16
-- of that squadron's parade dates hang off it. Renaming it is a separate action
-- for 704 to take through the interface — do not move data between rows to make
-- the names tidier.

BEGIN;

UPDATE planning_years SET active_status = false, updated_at = now()
WHERE id IN (
    '57b5c229-647a-4c0a-b47e-8b6420a01a11',   -- 703, no dependents, created 2026-08-04
    '0d39e637-2fd8-4c2b-ae33-e800559a9430',   -- 704, no dependents, created 2026-08-03
    'c4aa3393-7c88-43c0-b66a-76cd9047f454',   -- 704, no dependents, created 2026-08-09
    '79491d55-b84a-44f4-af3c-bfa060c79cce',   -- 708, no dependents, created 2026-08-19, named "2026"
    '6ea1640f-9e67-4295-a46b-e104d41be956'    -- 721, no dependents, created 2026-08-09
);
-- expect: UPDATE 5

-- Verify BEFORE committing. All four must hold.

-- 1. no duplicate active groups remain
SELECT count(*) AS duplicate_groups_must_be_zero FROM (
  SELECT unit_id, year FROM planning_years
  WHERE unit_id IS NOT NULL AND active_status
  GROUP BY unit_id, year HAVING count(*) > 1) x;

-- 2. nothing was deleted
SELECT count(*) AS planning_years_must_be_21 FROM planning_years;

-- 3. every row that carries parade dates is still active
SELECT count(*) AS rows_with_dates_wrongly_archived FROM planning_years py
WHERE NOT py.active_status
  AND EXISTS (SELECT 1 FROM parade_dates pd WHERE pd.planning_year_id = py.id);
-- must be 0

-- 4. the four intended survivors are the ones still active
SELECT s.code, py.name, py.active_status
FROM planning_years py JOIN squadrons s ON s.id = py.unit_id
WHERE py.id IN ('c33ca5b7-2c22-48e8-bfa0-d30cf9f578f8',
                '420e1d56-5f61-40a8-8399-a37380054c5f',
                'ec1a2a05-0bf9-495f-83aa-a82428957203',
                '312b067d-8e4f-478d-9c63-c225b2f97967')
ORDER BY s.code;
-- all four must show active_status = true

COMMIT;   -- or ROLLBACK; if any check failed


-- ── Reversal ────────────────────────────────────────────────────────────────
-- UPDATE planning_years SET active_status = true WHERE id IN (
--     '57b5c229-647a-4c0a-b47e-8b6420a01a11',
--     '0d39e637-2fd8-4c2b-ae33-e800559a9430',
--     'c4aa3393-7c88-43c0-b66a-76cd9047f454',
--     '79491d55-b84a-44f4-af3c-bfa060c79cce',
--     '6ea1640f-9e67-4295-a46b-e104d41be956');


-- ── After this runs ─────────────────────────────────────────────────────────
-- Production is then clear of the REM-134 blocker, but it is 23 migrations
-- behind (f6a7b8c9d0e1 -> d1e4f8a03b27) and that is a separate, larger exercise.
-- Pre-flighted read-only on 2026-08-23: the three table drops, the
-- session_audience dedupe and both orphan cleanups are all no-ops against
-- production's data, so duplicate years were the only blocker. Re-run
-- tools/data-quality/migration_preflight.py immediately before deploying —
-- that result is a point-in-time snapshot.
--
-- Migrate by DEPLOYING, not by running alembic against the database alone:
-- 821e2a4bc3e6 rewrites timing_blocks.block_type and the deployed production
-- backend predates that taxonomy. Staging was deployed this way on 2026-08-23
-- and came up clean.
