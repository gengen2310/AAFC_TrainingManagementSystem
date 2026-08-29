# Account Management — capability matrix

Date: 2026-08-30
Addendum §13–18, §25

## Audit result

**The backend was already canonical and the UI already reached all of it.** No
second account-management implementation exists, and none was built. The audit
found exactly one defect, and it was a wording defect rather than a missing
capability.

| capability | endpoint | TMS UI | state |
|---|---|---|---|
| List | `GET /api/accounts` | Accounts tab | present |
| Create | `POST /api/accounts` | Add account | present |
| Read | `GET /api/accounts/{uid}` | row detail | present |
| Edit | `PATCH /api/accounts/{uid}` | Edit | present |
| Change role | `POST .../change-role` | Edit | present |
| Change scope | `POST .../change-scope` | Edit | present |
| Reset access code | `POST .../reset-code` | Reset access code | present |
| Disable | `POST .../disable` | Disable | present |
| Reactivate | `POST .../reactivate` | Reactivate | present |
| Archive | `POST .../archive` | **Archive** (was "Delete") | **fixed** |
| Restore | `POST .../restore` | Restore | present |
| Permanent delete | `DELETE /api/accounts/{uid}` | Delete Permanently… | present |
| Unlock | `POST .../unlock` | Unlock | present |
| Batch archive | `POST /accounts/batch-archive` | bulk action | present |

## The defect (§16)

An active account's button read **Delete** but called `/archive`, while an
archived account's button read **Delete Permanently…** and called `DELETE`.
The same word therefore meant two different things depending on which row you
were looking at — reversible on one, irreversible on the other.

Renamed to **Archive**, with matching confirm and toast copy. Now:

- **Archive** — reversible. Revokes access, leaves the active list.
- **Delete Permanently…** — irreversible, archived accounts only, type-to-confirm.

## Already correct, and left alone

- **Refusal is explained** (§16). A blocked permanent delete reports the actual
  dependents from the API — *"Cannot permanently delete — history exists
  (audit_log_as_actor: 12). It remains archived."* — rather than hiding the
  reason or the button.
- **Show archived** (§17) exists and is off by default; archived rows are
  distinguished by their action set (Restore / Delete Permanently…), not by
  colour alone.
- **Actions are hidden, not disabled**, where a role cannot perform them
  (`canWrite` gate), per §14.
- **Account Management lives in TMS** (§18). Planning Workspace has no separate
  implementation.

## Tests

`frontend/e2e-connected/account-management.spec.ts` — 4, scoped to `#acct-table`
specifically. The same page renders `wings-table` and `units-table`, whose
Rename/Delete are legitimate; an unscoped assertion finds those and reports an
account defect that does not exist. The rename is red-green verified.
