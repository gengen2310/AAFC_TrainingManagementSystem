# Operational Workflow Audit

**Audited:** 2026-10-03  
**Branch:** `stabilise/predictable-architecture-post-pr68`

This note records the current code-level behaviour of the operational workflows
that are easy to misunderstand. It is descriptive: it does not invent policy
where the implementation or product decision is absent.

## Backup

Production uses the scheduled PostgreSQL workflow in
`.github/workflows/backup-postgresql.yml`, not the old SQLite pilot copy
procedure. The production dump is checksum-protected, GPG-encrypted, retained
as a private Actions artifact for 30 days, and has a separate automated restore
test. Staging uses separate secrets/workflows.

The System Console's `last_backup_at` describes only a backup initiated
through the application. It is not a global "last scheduled backup" indicator.

Remaining operational evidence gap: automated restore has release evidence;
the documented literal human manual DR drill is still a separate task.

## Service Desk — new-ticket notification

When a ticket is created, the backend derives the authoritative Wing from the
selected Squadron/Wing and builds the notification recipient set from
`ServiceDeskEmailConfig`.

A Squadron/Wing-scoped ticket is sent to:

1. every configured **system** Service Desk notification address;
2. every configured **national** Service Desk notification address;
3. the configured **matching Wing** notification address.

A different Wing's address is excluded. Duplicate email addresses are
de-duplicated before delivery. These operational addresses are SMTP-envelope
recipients and are not exposed to one another in the visible To/Cc headers.

If SMTP fails, the ticket remains persisted. Email is notification, not the
transaction that creates the ticket.

## Service Desk — Assigned To

`assigned_to_user_id` is the canonical assignment field. Eligible assignees
are active, non-archived `system_admin`, `national_admin`, or
`wing_admin` accounts. A Wing administrator can only own a ticket in the
same Wing. A Wing administrator acting on a ticket can only assign another
eligible Wing administrator in that same Wing.

The legacy `assigned_to_name` path cannot accept arbitrary free text; it must
resolve to exactly one eligible active support account.

A status or assignment change sends a workflow-update email to the **ticket
submitter's email address**. Admin-only notes are not emailed.

There is currently **no separate assignee-targeted email channel**. The User
model's recovery email is a credential-recovery channel and must not be reused
silently as an operational Service Desk contact address.

## Service Desk — configured notification ownership

- `system_admin`: can view/manage all Service Desk notification scopes.
- `national_admin`: can view system/national config but can change national,
  not system.
- `wing_admin`: can manage only the notification address for their own Wing.

Each configured value is validated as one email address. An empty string clears
delivery for that scope.

## Reset access code using email

Self-service recovery uses `User.recovery_email` only.

The forgot-code endpoint normalises the supplied email and proceeds only when
it identifies exactly one eligible account. Eligibility requires:

- active and not archived;
- role in `system_admin`, `national_admin`, `wing_admin`, or
  `sqn_admin`;
- a recovery email is present;
- that recovery email has been verified.

The reset token is emailed to that verified **recovery email**. It is not sent
to the Service Desk notification address, Squadron/Wing address, or any
display-name-derived address.

The outward forgot-code response is deliberately identical for matching,
non-matching and ineligible addresses to resist account enumeration. A reset
token expires after 20 minutes, is single-use, and is removed if email delivery
fails. Successful reset retires existing access codes and invalidates live
JWTs.

## Initial account setup

Administrator-created accounts receive an initial access code that is returned
once to the creator. The account is created with `must_change_code=True`, so
the holder must choose their own code on first sign-in.

A new `system_admin` must be created with a recovery email. Other
recovery-eligible administrator roles may have one. When a recovery address is
provided it must be unique, a verification token is minted, and verification
mail is sent to that address. Recovery is not eligible until verification
succeeds.

`GET /api/setup/status` separately reports the number of active System
Administrators whose recovery email is not verified. That is operational
information, not a Squadron setup checklist item.

## Maintenance Mode

Maintenance is controlled by System Administrator endpoints. Enabling it has a
PENDING/drain phase before LOCKED so in-flight work is not cut off
instantaneously. The configuration can independently choose whether reads and
new logins are blocked; writes are the principal protected path.

The System Administrator recovery/control path remains reachable so an
administrator is not permanently locked out of the controls required to end
maintenance. Maintenance state is persisted in system settings and exposed to
the UI with title/message/expected-return fields.

The existing maintenance qualification includes enforcement, cache
single-flight, event-loop and login-lookup regressions. Stabilisation work
should preserve those tests rather than reimplement maintenance policy in
individual routers.

## Curriculum import

There are two concepts that must not be conflated.

`POST /api/program-imports/preview` is a generic workbook-inspection endpoint.
It requires a write-capable administrator role, reads workbook structure, and
persists SourceFile/audit metadata. It does **not** commit curriculum.

The canonical curriculum upsert paths are:

- `POST /api/curriculum/import`
- `POST /api/curriculum/import-csv`
- `POST /api/curriculum/import-xlsm`

These currently require `national_admin` or `system_admin`, including when
the imported rows will be Wing- or Squadron-owned. A Wing-level import must
name a valid `wing_id`; a Squadron-level import must name a valid
`squadron_id`. This prevents orphan ownership and cross-Wing overwrite.

CSV accepts the governed fields requested for curriculum upload, including
Training Phase, Experiential/Module Code, Title, Elements,
Foundation/Extension, Instructor Suitability, Timing/Duration, Location, and
Learning Hub URL. Header matching is case-insensitive/order-independent.

The import performs identifier-first upsert, falling back to
`(code, part_number)` within the target ownership scope. `preview=true`
uses the same classification path and rolls the transaction back so a preview
does not create/update curriculum. File-size limits are enforced before
parsing. XLSM reads workbook values with formulas not executed.

The permission difference is explicit: workbook **inspection preview** is
available to every write-capable administrator, while actual curriculum
bulk-import is National/System Administrator only. That is the current policy
surface; changing it requires a product authority decision rather than a
silent refactor.
