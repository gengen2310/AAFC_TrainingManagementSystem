# System Administrator account recovery — design

Date: 2026-08-29
Addendum: §5–§12, §27–§29
Baseline: `376f11d`

## 1. The problem

If the only available System Administrator loses their access code in
production, there is currently no way back in. Access codes are stored only as
passlib hashes (`AccessCode.code_hash`), so the plaintext cannot be re-sent —
which is correct and must stay true. `User` has no email address, and there is
no unauthenticated recovery path of any kind.

An authenticated administrator can already reset another account's code
(`POST /api/accounts/{uid}/reset-code`). That covers every case **except** the
one that matters: no administrator is available to do it.

## 2. What already exists

Verified against the baseline, not assumed:

| capability | where | state |
|---|---|---|
| Hashed codes, plaintext never stored | `AccessCode.code_hash`, `security.hash_code` | keep as is |
| Per-account lockout, 5 attempts / 24h | `auth.py:57-58,159-161` | reuse |
| Per-IP login limiter | `security.py` | reuse |
| **Session invalidation** | JWT carries `tv`; `dependencies.py:117` rejects a mismatch against `User.token_version` | **reuse — §10 needs no new mechanism** |
| SMTP sending | `app/email_service.py` (`smtplib`), `SMTP_HOST/PORT/USER/PASS/FROM` | extend with a generic sender |
| Audit | `services.audit(db, principal, *, object_type, object_id, action, …)` | reuse |
| Last-System-Admin guard | `accounts.py:456,688` — covers demote and archive | extend to disable/delete |

**Nothing here requires a new provider, a new session model, or a new audit
system.** Recovery is assembled from parts that already exist.

## 3. Decisions taken (user, 2026-08-29)

1. **Recovery email is required for `system_admin`** and offered to the other
   privileged roles — `national_admin`, `wing_admin`, `sqn_admin`. Not stored
   for `sqn_general`, viewers or cadets.
2. **Break-glass is a Railway one-off command**, run by an operator with
   production project access. Not a web endpoint, not an env-var-at-boot.
3. **Archived and disabled accounts cannot self-recover.** An administrator
   must restore or reactivate first. The outward response does not reveal this.
4. Changing a recovery email **requires re-entering the current access code**
   (author's recommendation, adopted): that address becomes a credential-reset
   channel, so changing it is a credential-level act.

## 3a. What "required" means for System Admin

The decision says a verified recovery email is *required* for `system_admin`.
Enforcement has to be stated or it means nothing:

- **New `system_admin` accounts:** `POST /api/accounts` requires
  `recovery_email` when `role == "system_admin"`. A verification mail is sent
  immediately; the account is usable before verification, because refusing to
  create it would leave an org with no administrator at all.
- **Existing `system_admin` accounts:** NOT retro-fitted by migration — there
  is no address to fill in, and inventing one is worse than none. Instead
  `GET /api/setup/status` gains a warning for any `system_admin` without a
  verified recovery email, and the Account Management row shows it. Visible and
  actionable, not silently broken.
- **Never blocks login.** An administrator locked out by a missing recovery
  email is the exact failure this feature exists to prevent.

## 4. Data model

Four columns on `User`, all nullable:

```python
recovery_email:            Mapped[str | None]       # String(254), stored lowercase
recovery_email_verified_at: Mapped[datetime | None] # UTCDateTime
recovery_email_updated_at:  Mapped[datetime | None]
recovery_email_updated_by:  Mapped[str | None]      # FK users.id
```

An address is a usable recovery channel only when `recovery_email_verified_at`
is non-NULL. Setting or changing the address **clears** it.

New table `recovery_tokens`:

```python
id, user_id (FK, indexed), token_hash (String(255), indexed),
purpose (String(20)),        # "reset" | "verify_email"
expires_at (UTCDateTime), consumed_at (UTCDateTime | None),
created_at, created_ip (String(45) | None)
```

The token is **never stored in plaintext** — the same rule the access code
already follows. `token_hash` is SHA-256 of the raw token: unlike a user-chosen
code, a 256-bit random token needs no slow KDF, and passlib would make lookup
by hash impossible.

## 5. Flow — forgot access code

```
POST /api/auth/forgot-code   {email}
  -> ALWAYS 200 {"message": "If an eligible account matches those details,
                             recovery instructions have been sent."}
```

`email` is the **recovery email address**, not a display name or a squadron
code. Matching on a name would let anyone who knows a colleague's name trigger
mail to them, and names are not unique.

Behind that constant response:

1. Resolve the account. Eligible only if: exists, **not** archived, **not**
   disabled, has a verified recovery email, and its role is in the recovery-
   enabled set.
2. Invalidate any outstanding unconsumed `reset` tokens for that user.
3. Mint 32 random bytes (`secrets.token_urlsafe(32)`), store the SHA-256, set
   `expires_at = now + 20 minutes`.
4. Send the link to the **stored** address — never to an address supplied in
   the request.
5. Audit `recovery_requested`.

If any step fails — no such account, archived, unverified email — the response
is byte-identical and no email is sent. Timing is equalised by doing the same
work regardless (a dummy hash computation on the miss path), so response time
does not distinguish the cases.

```
POST /api/auth/reset-code    {token, new_code}
```

1. Hash the token, look it up, reject if consumed, expired, or unknown.
2. Re-check eligibility — the account may have been archived since the mint.
3. Validate the new code against the existing strength rules.
4. Deactivate every current `AccessCode` for the user and insert one new row.
   **Never leave two valid codes.**
5. Reset `failed_attempts = 0`, `locked_until = NULL`.
6. `user.token_version += 1` — every existing JWT dies at
   `dependencies.py:117`.
7. Mark the token consumed; invalidate the user's other unconsumed tokens.
8. Audit `recovery_completed`.

## 6. Enumeration resistance

- One response body for every outcome of `forgot-code`.
- Never "no account with that email".
- Rate limited on **both** the client IP and a hash of the submitted
  email, so neither an IP rotation nor a fixed IP can enumerate.
- `reset-code` returns one generic failure for consumed, expired and unknown
  tokens alike.

## 7. Rate limits

| endpoint | limit |
|---|---|
| `forgot-code` per IP | 5 / hour |
| `forgot-code` per submitted email | 3 / hour |
| `reset-code` per IP | 10 / hour |

These sit alongside — never replace — the existing per-IP login limiter and the
5-attempt/24h account lockout.

## 8. Email verification

`POST /api/accounts/{uid}/recovery-email` — sets or changes the address.

- Authority: own account, or an administrator already authorised over that
  account by existing RBAC. No new permission model.
- **Requires the caller's current access code in the body** (decision 4).
- Clears `recovery_email_verified_at`, mints a `verify_email` token (24h),
  sends the verification link, audits `recovery_email_changed`.
- `POST /api/auth/verify-recovery-email {token}` sets
  `recovery_email_verified_at` and audits `recovery_email_verified`.

Displayed masked — `g••••••••@example.com` — and returned **only** to the
account holder or an administrator authorised over that account. Never in
listings, exports or analytics.

## 9. Email delivery failure (§28)

`email_service` returns a boolean rather than raising. On a definitive
rejection:

- the token is **rolled back**, so no unusable token is left outstanding;
- the response is still the same generic 200 — a delivery failure must not
  become an enumeration oracle;
- the failure is logged at ERROR with the user id and provider error, and
  **never the token, the token hash or the address**;
- when `SMTP_HOST` is unset the service logs instead of sending, which is what
  makes local and staging testing safe by default (§34).

## 10. Break-glass (§12)

`backend/scripts/breakglass_reset_sa.py`, run by an operator through Railway
against the production service:

```
railway run --service <backend> -- python -m scripts.breakglass_reset_sa --user-code SYSADMIN
```

- Refuses unless `ENVIRONMENT` is set and a `--i-understand` flag is passed.
- Targets exactly one named `system_admin`; will not create a new one.
- Generates a code, prints it **once** to stdout, stores only the hash.
- Deactivates that user's other codes, clears lockout, bumps `token_version`.
- Writes an audit row with `principal=None` and
  `action="breakglass_reset"`, recording that no authenticated principal
  performed it.
- No hard-coded secret, nothing in Git, no HTTP route. Authority is Railway
  production access.

## 11. Last System Administrator (§11)

`_last_active_system_admin_count()` already guards demote (`accounts.py:456`)
and archive (`:688`). To audit and extend to **disable** and **DELETE**, with
one message:

> This is the last active System Administrator. Create or activate another
> System Administrator before removing this account.

## 12. Audit events

`recovery_email_changed`, `recovery_email_verified`, `recovery_requested`,
`recovery_completed`, `recovery_failed`, `breakglass_reset`,
`last_system_admin_protection_rejected`.

Never logged: plaintext access code, plaintext recovery token, recovery email
in a non-privileged context.

## 13. Testing (§27)

Eligible request; nonexistent account; archived; disabled; unverified email;
non-privileged role; expired token; reused token; superseded token; wrong
token; rate limit on IP; rate limit on identifier; old code stops working;
existing sessions die; two codes never coexist; SMTP failure path; masked
display; unauthorised read of another user's recovery email.

Response-body equality across the enumeration cases is asserted directly —
comparing the actual bytes, not eyeballing that both "look generic".

## 14. Out of scope

Password/code strength policy changes; MFA; SSO; per-user email preferences;
notifying a user that their code was reset by an administrator.
