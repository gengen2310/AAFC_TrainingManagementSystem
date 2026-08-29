# Training Year Context — Frontend Cleanup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the old `active_status`-based year lifecycle UI (rollover modal, Archive/Restore as normal workflow, Manage Years "Create" button, Rename, "(archived)" labels) and replace with the calendar-context model already implemented in the backend (PR #40) and partially in the frontend.

**Architecture:** Almost all year-nav logic is ALREADY implemented (`ynInit`, `ynNav`, `_ynRenderYearNotice`, `ynCopySetupFrom`, `setCurrentYear`). This plan removes the old lifecycle code that still shadows the new code. No new functions needed — only pruning and small renames.

**Tech Stack:** Single-file SPA (`connected-frontend/index.html`, ~400KB, no build step); React/Vite (`frontend/`). Changes to the SPA are raw edits with `Edit` tool. PW changes are TypeScript/React.

**Spec:** `docs/superpowers/specs/2026-08-28-training-year-context-model.md`

## Global Constraints

- Never use `innerHTML` with unescaped user content — always use `esc()` helper.
- Do not touch `active_status` column logic in the backend — that is the backend-only write/read concern.
- Do not remove `ynArchiveYear` / `ynRestoreYear` functions — they are needed for remediation use by wing_admin/system_admin. Only restrict their UI surface.
- Do not remove the Manage Training Years modal entirely — it is still needed for wing_admin/system_admin remediation. Only remove the "Create next year" button.
- Keep `ynExportYear` and the Export button intact.
- Do not remove `ynDeleteYear` — the backend is dependency-gated; deletion is legitimate for empty stray rows.
- XSS: any user-visible string from API goes through `esc()` before innerHTML.
- After every task: run `cd backend && source .venv/bin/activate && python -m pytest tests/ -q` from the repo root. Must still pass.
- Do NOT deploy to staging. Do NOT push unless explicitly directed.

---

### Task 1: Fix `_pickDefaultYear` — remove `active_status` filter

**Context:** `_pickDefaultYear` (line 15779) still filters by `active_status` as its first priority. In the new model, the API's `include_unmaterialised=true` response already includes a `state` field (`"past"` | `"current"` | `"future"`). The default selection should prefer `state === "current"`, then the earliest future, then the latest past — no `active_status` check.

**Files:**
- Modify: `connected-frontend/index.html` lines 15779–15792

**Interfaces:**
- Consumes: `P.years[]` — each entry has `.year` (int), `.planning_year_id` (string|null), `.state` ("past"|"current"|"future"), `.active_status` (bool, ignore)
- Produces: the same function signature `_pickDefaultYear(list) → yearObject | null`

- [ ] **Step 1: Understand what to replace**

  Read lines 15779–15792 of `connected-frontend/index.html`. The current code:
  ```js
  function _pickDefaultYear(list){
    const yrs=(list||[]).filter(Boolean);
    if(!yrs.length) return null;
    const act=yrs.filter(y=>y.active_status);       // <-- remove these two lines
    const pool=act.length?act:yrs;                  // <-- remove these two lines
    const now=new Date().getFullYear();
    const exact=pool.find(y=>parseInt(y.year,10)===now);
    if(exact) return exact;
    const ahead=pool.filter(y=>parseInt(y.year,10)>now).sort((a,b)=>a.year-b.year);
    if(ahead.length) return ahead[0];
    const behind=pool.filter(y=>parseInt(y.year,10)<now).sort((a,b)=>b.year-a.year);
    if(behind.length) return behind[0];
    return pool[0];
  }
  ```

- [ ] **Step 2: Replace with state-aware version**

  Replace the function body to remove `active_status` filtering:
  ```js
  function _pickDefaultYear(list){
    const yrs=(list||[]).filter(Boolean);
    if(!yrs.length) return null;
    // Prefer the year whose state is 'current' (derived from wing-local calendar date).
    // Falls back to earliest future, then latest past — same tiebreak logic.
    const cur=yrs.find(y=>y.state==='current');
    if(cur) return cur;
    const ahead=yrs.filter(y=>y.state==='future').sort((a,b)=>a.year-b.year);
    if(ahead.length) return ahead[0];
    const behind=yrs.filter(y=>y.state==='past').sort((a,b)=>b.year-a.year);
    if(behind.length) return behind[0];
    return yrs[0];
  }
  ```
  Note: the `state` field is supplied by `GET /api/planning/years?include_unmaterialised=true` via `services_year.year_state()`. If an old entry lacks `.state`, the calendar-year fallback (`new Date().getFullYear()`) was already removed in this list — that fallback was only needed for the `active_status` path.

  Add a safety fallback for missing `.state` (older API responses):
  ```js
  function _pickDefaultYear(list){
    const yrs=(list||[]).filter(Boolean);
    if(!yrs.length) return null;
    const cur=yrs.find(y=>y.state==='current');
    if(cur) return cur;
    const now=new Date().getFullYear();
    const exact=yrs.find(y=>parseInt(y.year,10)===now);
    if(exact) return exact;
    const ahead=yrs.filter(y=>y.state==='future'||parseInt(y.year,10)>now).sort((a,b)=>a.year-b.year);
    if(ahead.length) return ahead[0];
    const behind=yrs.filter(y=>y.state==='past'||parseInt(y.year,10)<now).sort((a,b)=>b.year-a.year);
    if(behind.length) return behind[0];
    return yrs[0];
  }
  ```

- [ ] **Step 3: Update `_ynPopulateYearSelects` — remove "(archived)" label**

  At line ~15831 (within `_ynPopulateYearSelects`):
  ```js
  o.textContent = prefix + (y.name || String(y.year)) + (y.active_status?'':' (archived)');
  ```
  Change to:
  ```js
  const stateTag = y.state === 'past' ? ' — record' : y.state === 'future' ? ' — upcoming' : '';
  o.textContent = prefix + String(y.year) + stateTag;
  ```
  The year has no user-editable name (spec §6), so show only the integer. The state tag is a quiet hint, not a badge.

- [ ] **Step 4: Run tests**

  ```bash
  cd backend && source .venv/bin/activate && python -m pytest tests/ -q
  ```
  Expected: same pass count as baseline (no backend changes in this task).

- [ ] **Step 5: Commit**

  ```bash
  git add connected-frontend/index.html
  git commit -m "feat: year picker uses state not active_status; remove (archived) label"
  ```

---

### Task 2: Remove Rollover modal; clean up year list renderer

**Context:** `m-rollover-year` modal (line 4124) calls the old `/api/planning/years/{id}/rollover` endpoint. The new equivalent is `ynCopySetupFrom()`, already in the year-notice area (`_ynRenderYearNotice`). The Manage Years year list (`_ynRenderYearList`) still shows a "Roll over →" button. Remove both; replace with a "Copy setup →" link that calls the existing `ynCopySetupFrom`.

Also: `_ynRenderYearList` shows Archive/Restore to any write-capable user. Per spec §5, Archive is remediation-only. Restrict to `wing_admin`/`system_admin`.

**Files:**
- Modify: `connected-frontend/index.html`
  - Remove: `m-rollover-year` modal HTML (lines 4124–4160)
  - Remove: `ynDoRollover`, `ynOpenRollover` functions (lines 12656–12712)
  - Modify: `_ynRenderYearList` (lines 12542–12610)

- [ ] **Step 1: Delete rollover modal HTML**

  Delete the entire block from `<div class="modal-bg" id="m-rollover-year"` through its closing `</div>` (lines 4124–4160, inclusive). Confirm by reading those lines first.

- [ ] **Step 2: Delete `ynOpenRollover` and `ynDoRollover` functions**

  Delete lines 12656 (the `// ── Year rollover ──` comment) through 12712 (the end of `ynDoRollover`'s catch block). Read first to confirm bounds.

- [ ] **Step 3: Update `_ynRenderYearList` — remove "Roll over" button**

  In `_ynRenderYearList`, the section:
  ```js
  if(canWrite && active){
    acts += '<button class="btn btn-xs btn-sky" ... onclick="ynOpenRollover(...)">Roll over →</button>';
  }
  ```
  Delete those 2 lines entirely. The copy-setup action is already surfaced in the year-notice area (`_ynRenderYearNotice`) and is more discoverable there.

- [ ] **Step 4: Restrict Archive/Restore to wing_admin/system_admin**

  Still in `_ynRenderYearList`, the current Archive/Restore section:
  ```js
  if(canWrite){
    acts += active
      ? '<button ... onclick="ynArchiveYear(...)">Archive</button>'
      : '<button ... onclick="ynRestoreYear(...)">Restore</button>';
    if(!active){
      acts += '<button ... onclick="ynDeleteYear(...)">Delete</button>';
    }
  }
  ```
  Add a role check. The variable `canWrite` = `canWriteSquadron()` which is true even for `sqn_admin`. Archive/Restore are remediation-only:
  ```js
  const canRemediate = ['wing_admin','system_admin'].includes(S.role||'');
  if(canWrite && canRemediate){
    acts += active
      ? '<button ... onclick="ynArchiveYear(...)">Archive</button>'
      : '<button ... onclick="ynRestoreYear(...)">Restore</button>';
    if(!active){
      acts += '<button ... onclick="ynDeleteYear(...)">Delete</button>';
    }
  }
  ```
  Note: `ynDeleteYear` is also restricted — correct, since Delete is destructive and SysAdmin-only in practice.

- [ ] **Step 5: Update year meta label**

  In `_ynRenderYearList`, the meta line:
  ```js
  const meta = [ active?'Active':'Archived', created?('Created '+created):'' ]
    .filter(Boolean).join(' · ');
  ```
  Change to use state:
  ```js
  const stateLabel = y.state === 'current' ? 'Current' : y.state === 'past' ? 'Record' : 'Upcoming';
  const meta = [ stateLabel, created?('Created '+created):'' ]
    .filter(Boolean).join(' · ');
  ```

- [ ] **Step 6: Run tests**

  ```bash
  cd backend && source .venv/bin/activate && python -m pytest tests/ -q
  ```

- [ ] **Step 7: Commit**

  ```bash
  git add connected-frontend/index.html
  git commit -m "feat: remove rollover modal; restrict Archive/Restore to wing_admin+; use year state labels"
  ```

---

### Task 3: Remove Manage Years "Create" button; fix `_renderPyActionBtns`; fix "No active year" message

**Context:**
1. `m-manage-years` modal still has a "Create next year" button (`ynCreateYear`). In the calendar model, a year exists as soon as you navigate to it — explicit creation is gone. Remove the button.
2. `_renderPyActionBtns` (line 15850) still shows Rename, Archive, and Restore buttons. Rename is gone (year has no user-editable name, spec §6). Archive/Restore are remediation-only (same as task 2).
3. `_acLoadConflicts` (line 6204) shows "No active year — select one from Training Plans first." This language assumes the old lifecycle. Update to the new model.
4. `S.trainingYear` init (line 5475) hardcodes `2026` as a fallback. Update to derive from the calendar year.

**Files:**
- Modify: `connected-frontend/index.html`

- [ ] **Step 1: Remove "Create next year" button from Manage Years modal**

  In `m-manage-years` modal HTML, find and remove:
  ```html
  <button class="btn btn-sky" id="ynCreateBtn" onclick="ynCreateYear()" style="margin-bottom:18px">+ Create <span id="ynCreateLabel">next year</span></button>
  ```
  Do not delete `ynCreateYear()` function yet — it may still be referenced elsewhere. Check first with grep; if no other callers, delete it too.

  ```bash
  grep -n "ynCreateYear" connected-frontend/index.html
  ```
  If only the modal HTML and the function definition remain, delete both.

- [ ] **Step 2: Update `_renderPyActionBtns` — remove Rename; restrict Archive/Restore**

  Current code at line ~15854:
  ```js
  el.innerHTML=
    `<button ... onclick="exportAnnualProgram()">Export Annual</button>`+
    `<button ... onclick="exportSchedule()">Export Schedule</button>`+
    `<button ... onclick="doRenamePlanningYear()">Rename</button>`+
    (y.active_status
      ? `<button ... onclick="doArchivePlanningYear()">Archive</button>`
      : `<button ... onclick="doRestorePlanningYear()">Restore</button>`)+
    `<button ... onclick="doDeletePlanningYear()">Delete…</button>`;
  ```
  New version:
  ```js
  const canRemediate = ['wing_admin','system_admin'].includes(S.role||'');
  el.innerHTML=
    `<button ... onclick="exportAnnualProgram()">Export Annual</button>`+
    `<button ... onclick="exportSchedule()">Export Schedule</button>`+
    (canRemediate
      ? (y.active_status
          ? `<button ... onclick="doArchivePlanningYear()">Archive</button>`
          : `<button ... onclick="doRestorePlanningYear()">Restore</button>`)
      : '')+
    (canRemediate ? `<button ... onclick="doDeletePlanningYear()">Delete…</button>` : '');
  // Rename removed: year integer is the canonical identity, not the name (spec §6)
  ```

  Note: the `plan-write-el` display:none show/hide pattern (last line) still applies to whatever buttons remain. Verify the guard still runs.

- [ ] **Step 3: Fix "No active year" message in `_acLoadConflicts` (line 6204)**

  Current:
  ```js
  if(el)el.outerHTML='<div style="...">No active year — select one from Training Plans first.</div>';
  ```
  This fires when `!P.currentYearId` (year is not materialised). Replace with:
  ```js
  const yrLabel = P.currentYearInt ? 'Nothing has been configured for '+(P.currentYearInt)+' yet.' : 'No training year selected.';
  if(el)el.outerHTML='<div style="font-size:var(--fs-sm);color:var(--muted)">'+yrLabel+' Planning conflicts appear once the year has training data.</div>';
  ```

- [ ] **Step 4: Fix `S.trainingYear` init (line 5475)**

  Current:
  ```js
  S.trainingYear=(uicfg&&uicfg.training_year)||2026;
  ```
  The `uicfg` object likely doesn't include `training_year` in the new API. Change to:
  ```js
  S.trainingYear=(uicfg&&uicfg.training_year)||new Date().getFullYear();
  ```
  This is a safe change: `S.trainingYear` is used as a default query param for curriculum API calls, so defaulting to the current calendar year is correct.

- [ ] **Step 5: Run tests**

  ```bash
  cd backend && source .venv/bin/activate && python -m pytest tests/ -q
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add connected-frontend/index.html
  git commit -m "feat: remove Create Year button; restrict Rename/Archive/Restore; fix no-year message"
  ```

---

### Task 4: GuidedYearSetupModal — replace rollover with copy-setup

**Context:** `GuidedYearSetupModal.tsx` still offers two creation methods: `"new"` (empty) and `"rollover"` (copies from previous year using old `/rollover` endpoint). In the new model:
- A year doesn't need to be "created" — it's materialised on first write.
- The modal is now reached when the year is NOT materialised (`materialised === false` in the year object).
- The modal should offer: "Set up [year]" with an optional "Copy class structure from [prev year]" checkbox.
- Uses `POST /api/planning/years` (materialise) + `POST /api/planning/years/copy-setup` (if checkbox checked).

The connected-frontend already has `ynSetUpYear` + `ynCopySetupFrom` as the reference implementation.

**Files:**
- Modify: `frontend/src/components/planning/GuidedYearSetupModal.tsx`
- Modify: `frontend/src/api/index.ts` (remove `rolloverYear`, add `copySetup` if not present)

- [ ] **Step 1: Read the current GuidedYearSetupModal.tsx**

  Read the full file to understand the current structure:
  ```bash
  cat frontend/src/components/planning/GuidedYearSetupModal.tsx
  ```

- [ ] **Step 2: Read planningApi / api/index.ts for existing copySetup**

  Check if `copySetup` / `copy-setup` is already in the API wrapper:
  ```bash
  grep -n "copy.setup\|rolloverYear\|copySetup" frontend/src/api/index.ts
  ```

- [ ] **Step 3: Replace modal method state**

  Remove:
  ```tsx
  const [method, setMethod] = useState<"new" | "rollover">(mostRecent ? "rollover" : "new");
  const [newYearName, setNewYearName] = useState<string>(`${targetYear} Training Year`);
  ```
  Replace with:
  ```tsx
  const [copyFrom, setCopyFrom] = useState<boolean>(!!mostRecent);
  ```

- [ ] **Step 4: Replace `runStart` logic**

  Current `runStart` (called on primary action):
  ```tsx
  if (method === "rollover" && mostRecent) {
    const r = await planningApi.rolloverYear(mostRecent.planning_year_id!, {});
    ...
  } else {
    await planningApi.createYear({ year: targetYear, name: newYearName, active_status: true });
    ...
  }
  ```
  New `runStart`:
  ```tsx
  // Step 1: materialise the row (name derives from year integer)
  await planningApi.createYear({ year: targetYear, name: String(targetYear) });
  if (copyFrom && mostRecent) {
    // Step 2: copy class structure from previous year
    await planningApi.copySetup({
      source_year: mostRecent.year,
      target_year: targetYear,
      copy_classes: true,
      copy_parade_pattern: false,
    });
  }
  ```
  Note: `planningApi.createYear` must NOT send `active_status: true` — the new model has no active/archived concept from the user's perspective. Check if the backend's `POST /api/planning/years` still requires it; if so, keep `active_status: true` silently.

- [ ] **Step 5: Replace modal UI**

  Remove the radio-button method selection and `newYearName` input. Replace with a simple checkbox:
  ```tsx
  <div className="ys-modal-body">
    <p>Setting up {targetYear} will create your planning workspace for this year.</p>
    {mostRecent && (
      <label>
        <input
          type="checkbox"
          checked={copyFrom}
          onChange={e => setCopyFrom(e.target.checked)}
        />
        {" "}Copy training class structure from {mostRecent.year}
      </label>
    )}
    <p className="ys-hint">
      Parade nights, sessions, and cadet records are never copied.
    </p>
  </div>
  <div className="ys-modal-actions">
    <Button variant="secondary" onClick={onClose}>Cancel</Button>
    <Button onClick={runStart} disabled={loading}>
      Set up {targetYear}
    </Button>
  </div>
  ```

- [ ] **Step 6: Add `copySetup` to `api/index.ts` if missing**

  If `planningApi.copySetup` doesn't exist, add it (after checking what `rolloverYear` looked like):
  ```ts
  async copySetup(params: {
    source_year: number;
    target_year: number;
    copy_classes?: boolean;
    copy_parade_pattern?: boolean;
  }): Promise<{ classes_copied: number }> {
    const r = await this.client.post('/api/planning/years/copy-setup', params);
    return r.data;
  }
  ```

- [ ] **Step 7: Remove `rolloverYear` from `api/index.ts`**

  After verifying no other caller uses `rolloverYear` (check `frontend/src/` with grep), remove it from the API client.

  ```bash
  grep -rn "rolloverYear" frontend/src/
  ```
  If only `GuidedYearSetupModal.tsx` (now updated) and the definition remain, delete the definition.

- [ ] **Step 8: TypeScript compile check**

  ```bash
  cd frontend && npm run build 2>&1 | tail -20
  ```
  Fix any type errors.

- [ ] **Step 9: Run backend tests**

  ```bash
  cd backend && source .venv/bin/activate && python -m pytest tests/ -q
  ```

- [ ] **Step 10: Commit**

  ```bash
  git add frontend/src/components/planning/GuidedYearSetupModal.tsx frontend/src/api/index.ts
  git commit -m "feat: replace rollover modal with copy-setup in PW GuidedYearSetupModal"
  ```

---

### Task 5: Connected-frontend rebuild and full test pass

**Context:** `connected-frontend/index.html` is the built output of the React Planning Workspace (`frontend/`) combined with the legacy SPA. The `make connected` command runs `npm run build:single` and copies the output. After all changes, verify the build and run all tests.

Note: If `connected-frontend/index.html` was edited directly (Tasks 1-3) AND the PW was rebuilt (Task 4), confirm the PW rebuild does not overwrite the Task 1-3 edits. If it does, re-apply Task 1-3 changes after the rebuild.

**Files:**
- Verify: `connected-frontend/index.html` (all task edits intact)
- Run: full backend test suite

- [ ] **Step 1: Check if `make connected` or `npm run build:single` would overwrite edits**

  ```bash
  head -5 connected-frontend/index.html
  # Check if it's a generated file with a build comment at the top
  ```
  If `connected-frontend/index.html` is the output of a build step, then Tasks 1-3 edits must be applied to the React source too, or they'll be overwritten on next build.

  Check CLAUDE.md: "frontend/ — React + Vite + TypeScript 'Planning Workspace'. Also has a `--mode single` build... that inlines everything into one file via `vite-plugin-singlefile, used by `make connected` to regenerate `connected-frontend/index.html` from the React source"

  **Critical finding:** `connected-frontend/index.html` IS the output of `make connected`. If you run `make connected`, Tasks 1-3 edits are overwritten.

  **Resolution:** Tasks 1-3 edit the COMPILED output directly. This is valid if we do NOT rebuild. Since the PW code is in `frontend/src/` and the SPA code (`_pickDefaultYear`, `ynDoRollover`, etc.) is NOT part of the React source (it's the legacy JS embedded in the SPA section), the edits to the SPA JS survive a PW rebuild — the build only replaces the React component bundle section.

  Verify by checking what `make connected` does:
  ```bash
  cat Makefile | grep -A5 "connected:"
  ```

- [ ] **Step 2: Run full backend test suite**

  ```bash
  cd backend && source .venv/bin/activate && python -m pytest tests/ -q --tb=short
  ```
  Expected: same pass count as baseline.

- [ ] **Step 3: Start local servers and verify the year nav in a browser**

  ```bash
  cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000 &
  cd connected-frontend && python3 -m http.server 8080 &
  ```
  Log in as sqn_admin, navigate to Activities. Verify:
  - Year nav shows `‹ 2026 ▾ ›`
  - Clicking `›` moves to 2027 (future), shows setup notice
  - No "Roll over →" in Manage Years
  - No "Rollover training year" modal
  - "Archive" button not visible for sqn_admin

- [ ] **Step 4: Final commit**

  ```bash
  git add connected-frontend/index.html
  git commit -m "chore: verify training year context frontend changes complete"
  ```

---

## Post-implementation: close PR #42

PR #42 ("Fix wing timezone backfill") is stale — its fix is already in `main` via `a7c4e91b2f60`. Close it with a comment explaining it's superseded.

This is an informational note only — it requires user authorisation to close a GitHub PR. Do not close it automatically.
