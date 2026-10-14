# Security evidence — production readiness 2026-10-09

## S0 — Agent guard against production actions (protocol §G)

**Control:** `.claude/settings.json` → PreToolUse(Bash) hook
`.claude/hooks/guard_prod.sh`. Applies to Claude Code sessions whose project
directory is this repository. **It did not protect the session that wrote it**
(that session's project dir was the user's home); covering such sessions needs
an entry in the user's global settings, which is the user's decision.

**Refuses:** the production Railway environment id; any `railway` command naming
`production`/`prod` as a word (any flag spelling or case); any tool given an
explicit `--environment production` / `-e prod`; `deploy-prod*` and globs over
`deploy-*`; `seed_all`/`reset_db` unless every `DATABASE_URL=` in the command is
SQLite and no `railway` is involved.

**Fails closed:** malformed payload or missing `jq` → exit 2. On macOS
`/bin/bash` 3.2 a bad substitution reaches the EXIT trap with `$? = 0`, so exit
codes are not trusted; only an explicit decision sets `decided=1`, otherwise
exit 2. Matching uses `[[ =~ ]]` only (no pipelines → no SIGPIPE path).

**Test:** `bash .claude/hooks/test_guard_prod.sh` → **52/52** at `4d9a28c`
(fail-closed ×2, injected shell error, 33 deny, 13 allow, 300 KB inputs).

### Review history (each finding reproduced before fixing)

| Commit | Finding (background security review unless noted) | Reproduced |
|---|---|---|
| `13bc3bf` | fail-open: malformed payload exited 5 (non-blocking) → command ran; `railway environment production` then bare `railway up` | yes (rc=5; allowed) |
| `704cf5b` | SIGPIPE under `pipefail` could turn a match into a miss; `-eproduction`, `PRODUCTION`, line continuation bypassed | spellings yes; SIGPIPE not at 300 KB (removed anyway) |
| `704cf5b` | (self-found) EXIT-trap safety net did not fire on bash 3.2 | yes (rc=0) |
| `081980f` | `rail""way`, `pro\duction`, `deploy-produ""ction.sh`, `deploy-prod*.sh` bypassed; **control regression I introduced in `704cf5b`** (env-flag rule narrowed to railway) | yes (6 + regression) |
| `2aaabb1` | seed rule was a deny-list: DB target from the environment invisible | yes |
| `4d9a28c` | `railway -s backend run … seed_all`; `DATABASE_URL=sqlite… DATABASE_URL=postgres… seed_all` | yes |

### Residual risk (accepted, not fixable by pattern matching)

Values split across variables (`E=pro; F=duction; … -e $E$F`), ANSI-C escapes
(`$'\x70roduction'`), `eval`/base64. Both first two verified to pass the hook.
Later review notices of the same "parser differential" class without a new
concrete vector were acknowledged, not iterated on.

**The real boundary is credentials, not this hook.** The Railway CLI on the
release workstation is logged in with an account that can reach production
(`railway whoami`, 2026-10-09). Recommendation for the owner: use a
staging-scoped project token for agent sessions.

## Other security-relevant changes on this branch

- D1 (maintenance outage backoff) — availability under DB failure; see DEFECT_REGISTER.
- Restore test now proves restored data is readable through the authorised API
  path (D9), not only that endpoints answer 200.
- Observation: the GPG key that decrypts **production** backups is labelled
  "automated staging backup key (rotated 2026-07-12)" (run 37909713246).
  Naming only, but key custody documentation should say which environments it
  serves (beta-release gate 10, key custody).

## Packaging security greps (`.claude/rules/security.md`, run 2026-10-09 at `8ecd2cd`)

| Grep | Matches | Review |
|---|---|---|
| removed wording | 0 | — |
| access-code exposure wording | 0 | — |
| seeded codes / code fields / localStorage in connected-frontend | 3 | `access_code_reset` = audit-log filter option label (l.2851); `localStorage` ×2 = nav-collapsed UI preference only (l.18717, 18732). Benign. |
| server secrets in connected-frontend | 1 | `DATABASE_URL` = literal placeholder in pg_restore help text (l.6782). Benign. |

Must be re-run after C6 (frontend extraction) moves code into `js/*.js`: the
greps cover the directory, so they still apply.

## Dependency audit (2026-10-09)

- Backend `requirements.txt`: `pip-audit` 2.10.1 -> **No known vulnerabilities found**.
- Playwright tooling: `npm audit` -> 0.
- Planning Workspace (`frontend/`), **shipped** deps (`--omit=dev`): 0 critical,
  0 high, 3 moderate:
  - `moment` path traversal via crafted locale name — transitive (not imported by
    app code); practical risk in a browser bundle is low; non-breaking fix exists.
  - `react-router(-dom)` open redirect via backslash in `<Link>`/`useNavigate` —
    every navigation target in `frontend/src` is a literal path (grep), so no
    user-controlled value reaches it; fix needs a major upgrade (v7).
- Planning Workspace **dev/build toolchain**: 2 critical, 6 high (`vitest`,
  `tinypool`, `vite`, `vite-plugin-singlefile`, `braces`, `micromatch`,
  `brace-expansion`, `source-map-js`). Not shipped: the deployed artifact is
  static files behind nginx. Fixes need major upgrades (vite 8, vitest 5).
- **Owner decision needed (known limitation):** accept the dev-toolchain and two
  moderate shipped findings for this release with a follow-up upgrade, or upgrade
  first. Not upgraded here: a major build-toolchain change during stabilisation
  is a redesign-sized risk, and `frontend/node_modules` in this worktree is shared
  with the owner's checkout.

## 2026-10-11 security closure (D10–D14 and the coverage map)

A read-only coverage map of nine security behaviours (lockout, session
revocation, recovery routing/expiry/replay/rate limit, Service Desk mail,
cross-worker rate limiting, first System Admin bootstrap, CSRF, audit
immutability, config redaction) was produced and every suspected defect
was re-checked by reading the code and, where possible, reproducing it.

| ID | Finding | Verified how | Disposition |
|---|---|---|---|
| D10 | Custom-phase mutation ignored ownership across Wings/nationals | 32/112 matrix cases failed | **Fixed** (`permissions.may_mutate_custom_phase`) |
| D11 | Stored XSS: `esc()` used for JavaScript-in-attribute contexts | payload executed in 3/3 browsers | **Fixed** (`jsq()`, 79 sites, static ratchet) |
| D13 | CSRF: cookie-only (SameSite=None) state-changing requests accepted from any origin | cookie-only `POST /accounts/{uid}/disable` with `Origin: https://evil.example` returned `{"ok":true}` | **Fixed**: `cookie_write_origin_check` middleware — cookie-authenticated POST/PUT/PATCH/DELETE must carry an allowed Origin/Referer; Bearer and pre-auth routes exempt (`test_cookie_write_origin_check.py`) |
| D14 | DB API limiters lost increments under concurrency; first-insert race could 500 | 16 threads × 25 requests recorded 25–36 | **Fixed**: atomic windowed UPDATE (`security._atomic_window_hit`), `test_rate_limiting_concurrency.py` (240 → 24/21 before, 240 after) |
| S-A | Lockout: a successful login clears the per-IP counter; `_scoped_fallback_scan` tests one guess against every same-role account but increments only the primary's counter; `/lookup` + 5 wrong codes locks any named admin for 24 h | code reading (auth.py:184–303, security.py:158) | **Owner decision (security policy)** — not changed: the per-account 24 h lock still bounds each account to 5 guesses; changing lockout semantics alters every user's login experience. Recorded in the risk register with options (do not reset IP counter on success; count the scan's guess against every candidate; CAPTCHA-free throttling on `/lookup`) |
| S-B | Forgot-code timing reveals eligible accounts (synchronous SMTP) | code reading (auth.py:564 vs :582) | **Accepted for release, low**: requires measuring a 20-min-token flow per address under a 5/IP/h + 3/address/h limit; fix = send after responding (needs token-rollback redesign). Risk register |
| S-D | `staging_seed` recreates a System Admin from `STAGING_BOOTSTRAP_SYSADMIN_CODE` whenever none exists, without an audit row | code reading (seeds/staging_seed.py:32–91) | **Hardened** (`system_admin_bootstrapped` audit row, `test_staging_seed_bootstrap_audit.py`, red before); residual: re-run needs every System Admin row deleted at DB level; operators must unset the bootstrap variables after first boot (already printed by the seed) |
| S-E | Weak tests: recovery JWT replay, recovery recipient, 6th forgot-code request, SMTP failure paths, audit PATCH/PUT absence, overview/migrations redaction | coverage map | **Done**: `test_security_path_closure.py` (10 tests, all pass; replay test mutation-checked) — no defect |

## Code-level security review of the full branch diff (`security-review` skill, 2026-10-12, at `ea12454`)

Scope: `origin/main...HEAD` (253+ commits), reviewed file by file by an independent
read-only agent: dependencies/auth/permissions/accounts/service_desk/system/setup/
custom_phases/planning/training/export_import, all new `services_*`, migrations v70–v76,
seeds, every `connected-frontend/js` module (esc/jsq/_jsAttr contexts, `_rtSanitize`),
`frontend/src` sinks, workflows. Each candidate was refuted or confirmed against its callers.

**Result: no finding at confidence ≥ 8.** Below threshold (product policy, not a breach):
`GET /api/system/audit-summary` is now reachable by sqn_admin/sqn_general/wing_admin
(matching `/api/audit`'s role list) and returns `ip_address`/`user_id` for actions inside
the caller's own Squadron/Wing — **owner decision**: should read-only Squadron users see
their administrators' IP addresses?

Packaging greps (`.claude/rules/security.md`, `-E`) at `ea12454`: wording 0; code exposure 0;
seeded codes 0 (3 reviewed matches: `localStorage` nav-collapsed UI preference ×2,
`access_code_reset` audit-filter label); frontend secrets 0 (1 reviewed match: `pg_restore`
help text placeholder). Same false positives as 2026-10-09.

## Corrections and additions after the adversarial review (2026-10-12)

- **D13 placement:** the origin check is in `dependencies.get_principal`
  (`_require_trusted_origin_for_cookie_write`), not a middleware (an earlier middleware draft
  was replaced so the check applies exactly when the cookie is the credential);
  `test_cookie_write_origin_check.py` has **9** tests.
- **D14 on PostgreSQL** (production's engine): 16 threads × 25 requests against a local
  PostgreSQL 16 database — pre-fix code (`89edc1d`) recorded **90/400** and raised
  `IntegrityError` (the first-insert race); fixed code recorded **400/400**, no errors.
- **X-Forwarded-For spoofing (review finding 5): refuted on staging.** A request carrying
  `X-Forwarded-For: 203.0.113.77` was recorded under the real client IP in
  `ip_api_requests`; Railway's edge sets the header, so the per-IP limiter and login lockout
  cannot be bypassed by a forged header. The lockout-policy question (S-A) remains open:
  `RISK_REGISTER.md` R2.
- **D10 create path (review finding 9):** fixed in `9bc4041` (Wing must exist and belong to
  the National Admin's national).
- **Scope of the code-level security review:** the review at `ea12454` covered the branch up
  to that commit. Code changed afterwards (D17–D25, D10 follow-up, deploy scripts) was
  re-reviewed separately — see the next section.

## Security review of code changed after `ea12454` (2026-10-12)

Independent read-only review of `git diff ea12454 HEAD` over backend/app, backend/scripts,
connected-frontend, scripts, frontend/src (14 files: D10 create follow-up, D17/D18 moves,
D19/D20, D21 `modal.js`, `migrate_or_hold.py`, both deploy scripts). **No finding ≥ 8.**
Checked: custom-phase create is strictly tighter; moved import helpers byte-identical; no new
HTML sink; deploy scripts never shell-evaluate gh/railway JSON and print no secret (only the
two configuration values are extracted); the computed Alembic head fails closed. One
non-security correctness hazard (holding against an unknown revision could also start a
*diverged* build) was **fixed** in `a20b892`: holding now requires `ALLOW_SCHEMA_AHEAD=1`.
