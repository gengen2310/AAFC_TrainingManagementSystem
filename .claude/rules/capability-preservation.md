# Capability Preservation & Bug-Resolution Protocol — AAFC TMS

Created for the "Complete System Remediation, Integration and Workflow Program"
(docs/remediation/master_remediation_plan.md). These rules apply to all future work
on this repository, not just that program.

## 1. Capability preservation

Do not touch, alter, remove, rename, hide, or delete an existing feature,
capability, route, endpoint, role, data field, import format, or workflow
without:

1. Identifying the existing capability.
2. Identifying all users/roles that depend on it.
3. Recording the proposed impact.
4. Proving an equivalent or improved replacement.
5. Preserving data and historical access.
6. Preserving a compatibility path where required.
7. Obtaining explicit user authorisation where the capability is to be removed.

A bug fix must not cause unrelated features to disappear. A visual redesign must
not silently remove actions. A navigation consolidation must not remove deep
links. A model consolidation must not discard historical records. **A new
implementation is not proof of parity.**

Before modifying a functional area, compare: frontend pages, routes, buttons/
actions, backend endpoints, permissions, database fields, imports/exports, tests,
audit events, help documentation. After modifying it, repeat the comparison.

Any reduction must be recorded as `USER-AUTHORISED REMOVAL` in the relevant gap
register entry, or it is a regression.

**Standing authorisation (2026-08-04, this program only)**: merge Training Summary
content into Dashboard, and remove the separate Training Summary nav tab — but only
after complete content/action parity is proven and a route redirect/compatibility
message is preserved for old deep links. No other feature removal is
pre-authorised; everything else needs a fresh explicit ask.

## 2. Bug-resolution protocol

For every bug: reproduce it; record role, org scope, frontend, route, exact
request, response status/payload category, backend log, browser console result,
current Git SHA; find the root cause; check current official documentation for
any framework/library/protocol behaviour that's unclear (prefer official docs,
primary specs, current package docs, this repo's own source and tests — never copy
an unvalidated workaround from a blog); record documentation references used;
produce a brief before-code impact assessment (affected features/roles/data,
migration requirement, security implications, compatibility implications);
implement the smallest safe correction that addresses the root cause; add a
regression test that fails before the fix and passes after; run affected tests,
then the relevant full suite; verify in staging through the rendered authenticated
application. Do not mark a bug closed from source inspection alone.

If the minimum fix would damage an existing feature: do not remove the feature;
document the conflict; design a compatibility solution; implement the least
disruptive option; record any residual limitation.

## 3. No false closure

Do not close an issue because: the database has the value but the frontend
doesn't render it; the button exists but the endpoint 403s; it works for
system_admin but not the intended role; staging works but production hasn't been
checked; a summary card works but its chart fails; one frontend works but the
other doesn't; a test passes only because it bypasses real login/UI; no records
exist and the UI treats the empty set as success; an inherited record was copied
instead of inherited; the error was hidden by changing the message.

Every closure requires user-visible and backend evidence where relevant — see
`docs/remediation/master_gap_register.csv`'s status column definitions.

## 4. Data safety

Do not: reset a database; reseed production; delete operational or audit history;
run destructive production tests; use raw SQL for ordinary application
operations; auto-merge ambiguous records; silently change organisation ownership;
alter credentials; expose access codes or hashes; put secrets in source, reports,
screenshots, or logs.

All destructive operations require: dependency preview, reason, confirmation,
audit event, safe failure, and an archive alternative. Archive remains the normal
operational action. Permanent deletion is restricted to erroneous, unused records
with no required historical dependency — see the dependency-gated delete pattern
already shipped for Account/Wing/Squadron/PlanningYear
(`app/services.py::fk_dependents`) as the template for any new entity that needs
this.

## 5. Git and release safety

Small, coherent commits; each message identifies functional area, behaviour
changed, tests added/updated. Do not combine unrelated fixes in one commit. Do not
merge `main` into a working branch as a shortcut. Do not deploy production under
this program. Do not rewrite published history. After every stage: push the
remediation branch, update the master gap register, record tests/evidence, confirm
no capability disappeared (compare against `capability_manifest_before.json`).

## 6. Security

Do not weaken security to eliminate a 403. Do not broaden a role globally because
one route uses the wrong scope helper — fix that route's helper choice (see
`.claude/rules/architecture.md`'s permission/scope helper selection guidance). Do
not return access-code hashes. Do not create a master login code. Do not retrieve
existing access codes (reset is the only path, one-time display). Do not remove
Proxy or Intervention requirements from protected delegated writes.
