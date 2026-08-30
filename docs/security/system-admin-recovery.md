# System Administrator recovery

Five ways back in, in the order to try them. Spec:
`docs/superpowers/specs/2026-08-29-account-recovery-design.md`.

Access codes are stored only as passlib hashes. **No procedure here retrieves an
existing code** — every one of them replaces it. If someone offers to send you
your current code, they are describing a system this is not.

---

## 1. Another System Administrator resets it

**Try this first.** Cheapest, fully audited, no email involved.

Any signed-in administrator with authority over the account:

> Account Management → the account → **Reset access code**

The new code is shown **once**. `POST /api/accounts/{uid}/reset-code`, audited
as `access_code_reset`.

---

## 2. Email recovery (self-service)

Requires a **verified** recovery email on the account.

1. Sign-in page → **Forgot access code?**
2. Enter the recovery address.
3. The response is always the same, whether or not an account matched — this
   is deliberate and is not a bug to report.
4. Open the email, use the code within **20 minutes**, set a new access code.

On success: the old code stops working immediately, every existing session for
that account is signed out, the recovery token is consumed, and
`recovery_completed` is audited.

**Eligibility.** Only `system_admin`, `national_admin`, `wing_admin` and
`sqn_admin`, and only when the account is active, not archived, and its address
is verified. **Archived and disabled accounts cannot self-recover** — an
administrator restores the account first (procedure 1). The outward response
never reveals which of these applied.

### Setting the recovery address

> Account Management → the account → **Recovery email**

Requires **your current access code**, because that address becomes a
credential-reset channel: a stolen session must not be enough to redirect
recovery to somebody else's mailbox. A verification link is sent; the address is
unusable until it is followed. Changing an address always clears its
verification — a new address inherits nothing from the old one.

---

## 3. Break-glass (operator)

**When:** no administrator can sign in **and** email recovery is unavailable.

Authority is deployment access — whoever can run a command against the
production service. That is deliberately the same authority that could already
read the database, so this grants nothing new.

```
railway run --service <backend-service-id> -- \
  python -m scripts.breakglass_reset_sa --user-code "<display name>" --i-understand
```

- Refuses without `--i-understand`.
- Refuses an unknown name, an ambiguous name, an archived account, and anything
  that is not a `system_admin`. It restores an administrator; it does not mint
  one.
- Deactivates that account's other codes, clears any lockout, and increments
  `token_version` so every existing session ends.
- Prints the new code **once**. Only the hash is stored.
- Audited as `breakglass_reset` with no principal, because no authenticated
  user performed it.

Sign in and change the code immediately.

---

## 4. Email service unavailable

If SMTP is unconfigured or the provider rejects the send, a freshly minted
recovery token is **rolled back** rather than left valid and undeliverable.

The user still sees the same generic confirmation — a delivery failure must not
become a way to test whether an account exists. The failure is logged at ERROR
with the account id and the provider error, and **never** the token or its hash.

Operators: check the backend log for `SMTP send failed`. With `SMTP_HOST`
unset — the default locally and on staging — nothing is transmitted at all and
the attempt is logged instead. That is what makes recovery safe to exercise in
testing.

Falls through to procedure 1, then 3.

---

## 5. Locked account

Five wrong codes lock an account for 24 hours
(`AccessCode.failed_attempts`, `locked_until`). Separately, a per-IP limiter
throttles repeated login attempts from one address.

- An administrator can clear it: **Unlock** (`POST /api/accounts/{uid}/unlock`).
- Procedures 2 and 3 both clear the lockout as part of setting the new code, so
  a locked-out administrator does not need a separate unlock first.

---

## The last System Administrator

The system refuses to remove the only remaining one. Demote, archive, disable
and delete all return:

> This is the last active System Administrator. Create or activate another
> System Administrator before removing this account.

Create or activate a second System Administrator first. **Two administrators is
the real protection** — every procedure above is a fallback for not having one.

---

## What none of this does

No hard-coded master password. No universal access code. No unauthenticated
reset endpoint. No plaintext code stored, logged or emailed. No security
questions. Nothing bypasses rate limiting or audit.
