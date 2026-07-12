# Planning Workspace RC1 — Test Report

## Environment

| Item | Value |
|------|-------|
| Report date | 2026-07-13 |
| Railway project | exemplary-emotion (`f5d9524f-8a57-44ff-86b7-ab66aec00e73`) |
| Environment | production (`571a8028-3640-4542-a4ab-7a1ee6b1f693`) |
| Frontend service | `aafc-tms-planning-workspace-preview` |
| Backend service | `aafc-tms-backend` |
| Frontend URL | https://aafc-tms-planning-workspace-preview-production.up.railway.app |
| Backend URL | https://aafc-tms-backend-production.up.railway.app |

## Commit and Migration State

| Item | Value |
|------|-------|
| Source branch | `main` |
| RC branch | `release/planning-workspace-rc1` |
| RC branch head | `45a757f` — feat: unified Activities tab + fix cea_import_batches migration |
| Previous commits | `3f8145c` perf: night-summaries waterfall fix; `3fc6ff7` fix: custom range 422; `34a7690` fix: v35 migration |
| Migration head (code) | `x9y0z1a2b3c4` (v36 — add created_by/updated_by to cea_import_batches) |
| Last known DB migration | `w8x9y0z1a2b3` (v35) — v36 pending deploy |

## Deploy Status at RC Cut

| Service | Deploy ID | State | Note |
|---------|-----------|-------|------|
| Backend | `7abd5982` | Online, deploy-failed badge | Old code running; v36 migration not yet applied |
| Frontend | `ee95c76f` | Online, deploy-failed badge | Old frontend build running |
| Old TMS | — | Online | Unaffected |

**Root cause of failed deploys:** `railway up` manual uploads failed silently (build-phase failures, root cause undetermined). GitHub push to `main` triggered on 2026-07-13 — Railway auto-deploy expected to resolve.

---

## Tests Executed

> Status key: ✅ Pass · ❌ Fail · ⚠️ Partial · 🔲 Not tested

### Phase 2 — End-to-end workflow

#### Planning year

| Test | Status | Notes |
|------|--------|-------|
| Create planning year | 🔲 | Not tested in this cycle |
| Reopen existing planning year | 🔲 | |
| Switch planning years | 🔲 | |
| Empty planning year state | 🔲 | |
| Term generation | 🔲 | |
| Parade night generation | 🔲 | |
| No freeze after creation | 🔲 | |

#### Range views

| Test | Status | Notes |
|------|--------|-------|
| Year view loads | 🔲 | |
| Term view loads | 🔲 | |
| 8-week view loads | 🔲 | |
| 2-week view loads | 🔲 | |
| Parade night view loads | 🔲 | |
| Custom range view | 🔲 | |
| Calendar/list toggle | 🔲 | |
| No 422 for valid ranges | 🔲 | Fixed in commit `3fc6ff7` |
| Consistent data across ranges | 🔲 | |

#### Lesson planning

| Test | Status | Notes |
|------|--------|-------|
| Schedule from Year view | 🔲 | |
| Schedule from 8-week view | 🔲 | |
| Edit existing lesson | 🔲 | |
| Move lesson | 🔲 | |
| Remove lesson | 🔲 | |
| Assign facilitator | 🔲 | |
| Assign room | 🔲 | |
| Autosave | 🔲 | Verified in prior session via curl (backend confirmed saves) |

#### Activities tab

| Test | Status | Notes |
|------|--------|-------|
| Open Activities tab | 🔲 | Pending deploy |
| CEA activities visible | 🔲 | |
| Anchor events visible | 🔲 | New in this RC |
| Holidays visible | 🔲 | New in this RC |
| Filter by source | 🔲 | |
| Filter by status | 🔲 | |
| Filter by date range | 🔲 | |
| Sort columns | 🔲 | |
| Import CEA (toolbar button) | 🔲 | New in this RC |
| Duplicate detection by Activity ID | 🔲 | |
| Classify activity | 🔲 | |
| Create manual activity | 🔲 | |
| CEA History tab | ❌ | 500 error — `cea_import_batches.created_by` missing (v36 migration pending) |

---

## Known Failures

### BUG-004 — CEA History tab returns 500

- **Severity:** Medium (CEA History tab, not main Activities tab)
- **Affected endpoint:** `GET /api/planning/years/{id}/cea/batches`
- **Root cause:** `cea_import_batches` table missing `created_by` and `updated_by` columns. SQLAlchemy model includes these (via `TimestampMixin`) but migration v34 did not add them.
- **Fix:** Migration v36 (`x9y0z1a2b3c4`) adds the columns. Pending deploy.
- **Workaround:** CEA History tab is non-critical. Import itself works; result banner shown inline on the Activities tab. Avoid CEA History tab until deploy lands.

### DEPLOY-001 — railway up builds failing silently

- **Severity:** Infrastructure (no user impact while old deploy is live)
- **Symptom:** `railway up` uploads succeed but builds never surface a new deployment ID
- **Suspected cause:** Railway manual upload build path differs from GitHub integration build path
- **Fix:** Push to GitHub `main` (committed 2026-07-13) — Railway GitHub auto-deploy should resolve

---

## Performance Results

*Not yet measured in this cycle. See Phase 6 targets.*

**Observed from prior session:**
- `annual-program` endpoint: ~1.9–2.1s (consistently)
- Night-summaries call eliminated (merged into annual-program)
- localStorage year prefetch eliminates 1.6s waterfall on repeat visits

---

## Permission Results

*Not yet tested in this cycle. See Phase 4.*

---

## Data Integrity Results

*Not yet tested in this cycle. See Phase 5.*

---

## Remaining Limitations

1. CEA History tab broken until v36 migration deploys
2. Annual-program endpoint slow (~2s) — acceptable but noted
3. Parade night grid view not tested under load
4. Custom date range long-range view not exercised with edge dates

---

## Release Recommendation

**Status: NOT YET ASSESSED — pending successful deploy of v36 migration**

Cannot issue GO/NO-GO until:
- v36 migration lands in production
- CEA History tab confirmed working
- End-to-end workflow testing completed (Phases 2–10)

Update this report after deploy confirms and full test cycle runs.
