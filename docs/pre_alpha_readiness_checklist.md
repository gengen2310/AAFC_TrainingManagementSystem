# AAFC TMS — Pre-Alpha Readiness Checklist

Use this checklist before delivering the system to pilot users.

## A. Product Readiness

- [ ] Login works for all demo access codes
- [ ] Role navigation works per scope (squadron/wing/national/auditor/system_admin)
- [ ] Local curriculum creation and display works
- [ ] Wing curriculum visible to wing and national roles
- [ ] National curriculum visible to all roles
- [ ] Account creation works (sqn_admin, wing_admin, national_admin, system_admin)
- [ ] Access code reset works (one-time display only)
- [ ] Account disable/reactivate works
- [ ] Unit creation works (Wing, Squadron via organisations endpoints)
- [ ] Training Planner works — mission assignment reflects in Annual Program
- [ ] Annual Program calendar shows parade nights, holidays, activities
- [ ] Parade Night Program works — builder and Weekly Program preview
- [ ] Weekly Program preview in Parade Night Program builder works
- [ ] System Console loads correctly for system_admin
- [ ] Maintenance mode enable/disable works with typed confirmation
- [ ] Backup creation works (SQLite demo)
- [ ] Audit log visible to system_admin and auditor

## B. Data Readiness

- [ ] Seed data correct — all demo accounts, units, curriculum seeded
- [ ] Demo data separated from production (SQLite only, not seeded in production)
- [ ] Alembic migrations run cleanly from empty DB: `alembic upgrade head`
- [ ] Historical data retained (no destructive schema change)
- [ ] Annual rollover tested (2026 → 2027 creates new planning year)
- [ ] Backup created before delivery: `bash scripts/backup_sqlite_demo.sh`
- [ ] Backup restore procedure documented: `docs/backup_and_restore.md`
- [ ] No destructive seed reset in production

## C. Security Readiness

- [ ] No plaintext access codes in API responses
- [ ] No access-code hashes in API responses
- [ ] No seeded access codes in frontend JS (grep check passes)
- [ ] JWT secret length enforced in production config validation
- [ ] Production config refuses to start with dev secrets
- [ ] CORS locked down in production settings
- [ ] COOKIE_SECURE enforced in production settings
- [ ] HTTP-only cookies used (set by backend, not JS)
- [ ] CSP/security headers present (X-Frame-Options, X-Content-Type-Options, etc.)
- [ ] Role checks tested — every system endpoint returns 403 for non-system roles
- [ ] Cross-scope access denied (SQN admin cannot access another SQN)
- [ ] IDOR checks passed (changing IDs in requests returns 403)
- [ ] Audit log captures login, logout, access code reset, account changes, maintenance, backup
- [ ] Failed login rate limiting tested (429 after 5 bad attempts)
- [ ] system_admin actions appear in audit log
- [ ] Maintenance controls require typed confirmation
- [ ] Frontend greps pass (see `.claude/rules/security.md`)

## D. Privacy Readiness

- [ ] No unnecessary personal data collected (no names/emails beyond display_name)
- [ ] Role/scope access limited — users only see data for their scope
- [ ] Audit log does not expose access-code hashes or JWT secrets
- [ ] Backup files stored locally only — not uploaded to external services
- [ ] Retention approach documented (not yet formalised — flag as known gap)

## E. Operational Readiness

- [ ] Deployment steps documented: `docs/deployment_guide.md`
- [ ] Maintenance window procedure documented: `docs/maintenance_procedure.md`
- [ ] Rollback procedure documented (restore from backup + alembic downgrade)
- [ ] Backup before deployment documented
- [ ] Health check endpoint working: `GET /api/health/ready`
- [ ] Smoke tests pass: `bash scripts/smoke_test_local.sh`
- [ ] Pre-alpha check script passes: `bash scripts/pre_alpha_check.sh`
- [ ] Known limitations documented (see below)

## F. User Readiness

- [ ] Local pilot guide exists: `AAFC_TMS_Pilot_Run_Guide.md`
- [ ] System admin guide exists: `docs/system_admin_console.md`
- [ ] Role matrix documented: `docs/role_matrix.md`
- [ ] Deployment guide exists: `docs/deployment_guide.md`

## Known Limitations (V17 Alpha)

1. **Maintenance mode** does not block normal user logins in the frontend — frontend notification only; backend middleware enforcement is a post-alpha task
2. **Production deployment** requires PostgreSQL, HTTPS, and managed infrastructure not provided in the local demo package
3. **Browser-based backup restore** is intentionally not implemented — restore requires manual file operations
4. **Wing/Squadron create-via-console** uses existing organisations API endpoints, not a dedicated System Console UI form (post-alpha)
5. **Session revocation** (force logout) is not implemented — JWT expiry is the current control
6. **Multi-year historical data** has not been load-tested beyond demo volume
7. **Annual rollover to 2027** tested in automated tests but not browser-tested with a full 2026 dataset
