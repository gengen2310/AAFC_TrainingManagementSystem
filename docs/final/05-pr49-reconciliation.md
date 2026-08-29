# PR #49 reconciliation

Instruction Part 5. Date: 2026-08-30.

## The instruction's premise is stale

Part 5 states PR #49 contains *"System Administrator recovery DESIGN ONLY"* and
warns against duplicating its work. **That was true when the instruction was
written and is no longer true.**

| | |
|---|---|
| PR #49 | **MERGED** 2026-08-29T16:38:46Z |
| Title | year selector, notification spacing, account recovery, account management |
| Open PRs now | **none** |

This is precisely the staleness Part 95 describes, in the instruction itself
rather than in a repository document. Recording it rather than implementing a
second year selector or a second recovery system.

## Disposition of each item

| item | state | evidence |
|---|---|---|
| Training Year selector | **MERGED, reuse** | 1.5px border / 6px radius / `--surface`, 38px vs a 37px neighbour; 18 e2e |
| Notification spacing | **MERGED, reuse** | `--toast-pad-y/-x/-gap/-edge/-max-w` declared in *both* frontends |
| Getting Started cadet row | **MERGED, reuse** | staging returns 14 steps, none cadet; served SPA has no such string |
| Account recovery | **IMPLEMENTED, not design-only** | see below |

## Account recovery is implemented, not specified

Part 5 lists what recovery requires beyond a specification. Each exists:

| requirement | evidence |
|---|---|
| model | `User.recovery_email*` (4 columns), `RecoveryToken` |
| migration | `v59 c3a7f2e91b48`, rehearsed forward and back |
| backend | `POST /api/auth/forgot-code`, `/reset-code`, `/verify-recovery-email`, `/api/accounts/{uid}/recovery-email` |
| email verification | token, 24h, clears on address change |
| recovery-token flow | SHA-256 stored, single use, 20 min, superseded by newer |
| frontend | *Forgot access code?* on the sign-in screen, plus request and reset panels |
| rate limiting | per IP and per submitted address, separate from the login limiter |
| audit | `recovery_requested`, `recovery_completed`, `recovery_email_changed`, `recovery_email_verified`, `breakglass_reset` |
| session invalidation | `token_version` increment; `dependencies.py:117` rejects a stale `tv` |
| tests | 20 backend + 5 e2e; enumeration asserted by comparing response **bytes** |
| break-glass docs | `docs/security/system-admin-recovery.md`, five procedures |

Verified live on staging: `forgot-code` returns a byte-identical body for an
unknown address, a malformed address and an empty string.

**The one genuine gap** is that `SMTP_HOST` is unset on staging, so delivery is
logged rather than sent. Recovery has never been exercised against a real
mailbox. That is a Part 49 completeness gap and needs a staging mailbox, not
more code.

## Conclusion

**Nothing in PR #49 needs reimplementing.** Do not build a second year selector,
a second toast system, or a second recovery flow. The remaining recovery work is
configuration and an end-to-end mail test.
