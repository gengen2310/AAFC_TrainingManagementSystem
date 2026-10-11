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
| S-D | `staging_seed` recreates a System Admin from `STAGING_BOOTSTRAP_SYSADMIN_CODE` whenever none exists, without an audit row | code reading (seeds/staging_seed.py:32–91) | **Hardening** queued (audit row + docs: unset the variable after first boot); requires every System Admin to have been hard-deleted first |
| S-E | Weak tests: recovery JWT replay, recovery recipient, 6th forgot-code request, SMTP failure paths, audit PATCH/PUT absence, overview/migrations redaction | coverage map | Tests being added (Phase 2); any failure becomes a D-number |

## Not yet run (Phase 5)

`security-review` skill over the full branch diff (after C3/C4/C6 integrate).
