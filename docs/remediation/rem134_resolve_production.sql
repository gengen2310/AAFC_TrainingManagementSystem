-- REM-134 planning-year resolution — PRODUCTION
-- 9 active rows across 4 duplicate group(s).
-- training_classes table present in this environment: False
--
-- Nothing here deletes anything. Rows are ARCHIVED (active_status = false),
-- which is this system's normal way to retire a planning year, and archived
-- rows do not participate in the partial unique index that migration
-- d1e4f8a03b27 creates. Archiving is reversible; deletion would not be.
--
-- Dependent counts below are parade_dates + holiday_periods.
--
-- RESOLVED AUTOMATICALLY — exactly one row in the group carries data, so
-- the choice is not a judgement call. Kept:
--   703 2026  c33ca5b7-2c22-48e8-bfa0-d30cf9f578f8  pd=4 hp=0 tc=0  2026–2027 Training Year
--   704 2026  420e1d56-5f61-40a8-8399-a37380054c5f  pd=16 hp=0 tc=0  2026 test 1.0
--   721 2026  312b067d-8e4f-478d-9c63-c225b2f97967  pd=16 hp=0 tc=0  2026–2027 Training Year
--
-- NOT HANDLED — no row in these groups carries any data, so there is no
-- basis for preferring one. Ask which name is intended, keep that one,
-- archive the rest by hand:
--   708 2026  ec1a2a05-0bf9-495f-83aa-a82428957203  created 2026-08-17  2026 Training Year
--   708 2026  79491d55-b84a-44f4-af3c-bfa060c79cce  created 2026-08-19  2026

BEGIN;

UPDATE planning_years SET active_status = false, updated_at = now()
WHERE id IN (
    '57b5c229-647a-4c0a-b47e-8b6420a01a11',   -- 703 2026, no dependents, created 2026-08-04
    '0d39e637-2fd8-4c2b-ae33-e800559a9430',   -- 704 2026, no dependents, created 2026-08-03
    'c4aa3393-7c88-43c0-b66a-76cd9047f454',   -- 704 2026, no dependents, created 2026-08-09
    '6ea1640f-9e67-4295-a46b-e104d41be956'   -- 721 2026, no dependents, created 2026-08-09
);
-- expect: UPDATE 4

-- Verify BEFORE committing. Both queries must return zero rows.
SELECT unit_id, year, count(*) FROM planning_years
WHERE unit_id IS NOT NULL AND active_status = true
GROUP BY unit_id, year HAVING count(*) > 1;

SELECT py.id FROM planning_years py
WHERE py.active_status = false AND EXISTS (
  SELECT 1 FROM parade_dates pd WHERE pd.planning_year_id = py.id);
-- ^ nothing archived here should own parade dates

COMMIT;   -- or ROLLBACK; if either check returned rows
