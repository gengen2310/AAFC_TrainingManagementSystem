"""Account management and Flight administration.

Accounts:
  GET    /api/accounts            — list (scoped to actor's authority)
  POST   /api/accounts            — create (returns new code once)
  GET    /api/accounts/{id}       — single account
  PATCH  /api/accounts/{id}       — update display_name / flight_id
  POST   /api/accounts/{id}/change-role — change role/access type (same scope level only)
  POST   /api/accounts/{id}/change-scope — move account to a different Squadron/Wing (same scope level only)
  POST   /api/accounts/{id}/reset-code  — generate or set new code (returned once)
  POST   /api/accounts/{id}/disable     — deactivate user
  POST   /api/accounts/{id}/reactivate  — reactivate user
  POST   /api/accounts/{id}/archive     — soft-delete (reversible via .../restore)

Flights (Squadron-local groupings only — no tenancy, no permissions):
  GET    /api/flights              — list (scoped)
  POST   /api/flights              — create (sqn_admin or above)
  PATCH  /api/flights/{fid}        — rename / toggle active
  POST   /api/flights/{fid}/archive — soft-delete

Security invariants enforced here:
  • Plaintext codes are NEVER stored or returned except as a one-time response.
  • Code hashes are NEVER included in any response.
  • Actors may only manage accounts within their own authority scope.
  • Flight assignment never grants or restricts permissions — it is display-only.
  • Viewers and auditors are read-only (no create / update / reset / disable).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.exc import IntegrityError

from ..database import get_db, utcnow, iso_z
from ..models import User, AccessCode, Wing, Squadron, Flight, NationalEntity, AuditLog
from ..dependencies import get_principal
from ..permissions import sqn_admin_outside_own_squadron  # noqa: E402
from ..permissions import has_known_role, is_national_admin  # noqa: E402
from ..permissions import wing_admin_outside_own_wing  # noqa: E402
from ..permissions import Principal, require_write_role
from ..permissions import (  # noqa: E402
    may_view_account, squadron_scope_clause, wing_or_squadron_scope_clause,
)
import re

from ..security import hash_code, generate_code, verify_code
from ..services_recovery import (
    RECOVERY_ROLES, VERIFY_TTL_MINUTES, mask_email, mint_token,
)
from ..email_service import send_mail
from ..services import audit, fk_dependents
from ..services_accounts import CREATE_AUTHORITY, account_scope_type, require_manage_authority
from ..permissions import ROLES as _ALL_ROLES

router = APIRouter(prefix="/api", tags=["accounts"])

# ─────────────────────────────────────────────
# Role authority maps
# ─────────────────────────────────────────────

# Which roles an actor may read/manage. sqn_general reads its own squadron's
# accounts read-only (2026-09-28 product decision); scope is enforced below
# (list filter + _can_read_account) and writes stay behind the central write-role policy.


# ─────────────────────────────────────────────
# Scope authority checks
# ─────────────────────────────────────────────

def _require_write_actor(p: Principal) -> None:
    require_write_role(p)


def _validate_create_scope(p: Principal, target_role: str,
                            nat_id: str | None, wing_id: str | None, sqn_id: str | None,
                            db: DBSession) -> None:
    """Raise 403/404/422 if the actor is not permitted to create an account with this role+scope."""
    allowed = CREATE_AUTHORITY.get(p.role, set())
    if target_role not in allowed:
        raise HTTPException(403, detail={"error": "forbidden",
                                          "message": f"Your role ({p.role}) cannot create {target_role} accounts."})

    scope = account_scope_type(target_role)

    if scope == "national":
        pass  # no additional scope constraint — national_admin/system_admin verified above

    elif scope == "wing":
        if not wing_id:
            raise HTTPException(422, detail={"error": "wing_id_required"})
        w = db.get(Wing, wing_id)
        if not w or w.is_archived:
            raise HTTPException(404, detail={"error": "wing_not_found"})
        if wing_admin_outside_own_wing(p, wing_id):
            raise HTTPException(403, detail={"error": "out_of_scope",
                                              "message": "Wing Admin can only create accounts in their own Wing."})

    elif scope == "squadron":
        if not sqn_id:
            raise HTTPException(422, detail={"error": "squadron_id_required"})
        sqn = db.get(Squadron, sqn_id)
        if not sqn or sqn.is_archived:
            raise HTTPException(404, detail={"error": "squadron_not_found"})
        if wing_admin_outside_own_wing(p, sqn.wing_id):
            raise HTTPException(403, detail={"error": "out_of_scope",
                                              "message": "Wing Admin can only create accounts for SQNs in their Wing."})
        if sqn_admin_outside_own_squadron(p, sqn_id):
            raise HTTPException(403, detail={"error": "out_of_scope",
                                              "message": "SQN Admin can only create accounts in their own Squadron."})


def _can_read_account(p: Principal, target: User, db: DBSession) -> bool:
    return may_view_account(p, target, db)


# ─────────────────────────────────────────────
# Response serialiser (never includes code_hash)
# ─────────────────────────────────────────────

def _accounts_context(db: DBSession, users: list) -> dict:
    """Pre-load what _account_out() needs for MANY accounts in a constant number
    of queries. Per-account lookups cost ~3 queries per account (measured: 419
    queries for /api/accounts on the national qualification dataset)."""
    ids = [u.id for u in users]
    ctx: dict = {"code": {}, "sqn": {}, "wing": {}, "nat": {}, "flight": {}}
    if not ids:
        return ctx
    for ac in (db.query(AccessCode).filter(AccessCode.user_id.in_(ids), AccessCode.active_status == True)  # noqa: E712
               .order_by(AccessCode.user_id, AccessCode.created_at).all()):
        ctx["code"].setdefault(ac.user_id, ac)
    for key, model, attr in (("sqn", Squadron, "squadron_id"), ("wing", Wing, "wing_id"),
                             ("nat", NationalEntity, "national_id"), ("flight", Flight, "flight_id")):
        wanted = {getattr(u, attr) for u in users if getattr(u, attr)}
        if wanted:
            ctx[key] = {o.id: o for o in db.query(model).filter(model.id.in_(wanted)).all()}
    return ctx


def _account_out(u: User, db: DBSession, ctx: "dict | None" = None) -> dict:
    if ctx is not None:
        ac = ctx["code"].get(u.id)
    else:
        ac = db.query(AccessCode).filter(AccessCode.user_id == u.id,
                                         AccessCode.active_status == True).first()  # noqa: E712

    def _get(key, model, oid):
        return ctx[key].get(oid) if ctx is not None else db.get(model, oid)
    # Resolve unit names
    sqn_code = sqn_name = wing_code = wing_name = nat_name = flight_name = None
    if u.squadron_id:
        s = _get("sqn", Squadron, u.squadron_id)
        if s:
            sqn_code, sqn_name = s.code, s.name
    if u.wing_id:
        w = _get("wing", Wing, u.wing_id)
        if w:
            wing_code, wing_name = w.code, w.name
    if u.national_id:
        n = _get("nat", NationalEntity, u.national_id)
        if n:
            nat_name = n.short_name
    if u.flight_id:
        fl = _get("flight", Flight, u.flight_id)
        if fl:
            flight_name = fl.name

    return {
        "user_id": u.id,
        "display_name": u.display_name,
        "role": u.role,
        "scope_type": account_scope_type(u.role),
        "national_id": u.national_id,
        "national_name": nat_name,
        "wing_id": u.wing_id,
        "wing_code": wing_code,
        "wing_name": wing_name,
        "squadron_id": u.squadron_id,
        "squadron_code": sqn_code,
        "squadron_name": sqn_name,
        "flight_id": u.flight_id,
        "flight_name": flight_name,
        "active_status": u.active_status,
        "is_archived": u.is_archived,
        "archived_at": iso_z(u.archived_at) if u.archived_at else None,
        "last_login_at": iso_z(u.last_login_at) if u.last_login_at else None,
        "created_at": iso_z(u.created_at) if u.created_at else None,
        "created_by": u.created_by,
        # Access-code metadata only (never hash, never plaintext)
        "code_active": ac.active_status if ac else False,
        "code_last_changed": iso_z(ac.updated_at) if ac and ac.updated_at else None,
        "code_changed_by": ac.updated_by if ac else None,
        "locked_until": iso_z(ac.locked_until) if ac and ac.locked_until else None,
        "recovery_email": mask_email(u.recovery_email) if u.recovery_email else None,
        "recovery_email_verified": bool(u.recovery_email_verified_at),
        "must_change_code": bool(getattr(u, "must_change_code", False)),
    }


# ─────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────

class AccountCreateIn(BaseModel):
    display_name: str
    role: str
    national_id: str | None = None
    wing_id: str | None = None
    squadron_id: str | None = None
    flight_id: str | None = None
    new_code: str | None = None   # if omitted, auto-generated
    recovery_email: str | None = None



def _normalise_recovery_email(raw: str | None) -> str | None:
    if raw is None:
        return None
    addr = raw.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr) or len(addr) > 254:
        raise HTTPException(400, detail={
            "error": "invalid_email", "message": "Enter a valid email address."})
    return addr


def _ensure_recovery_email_available(
    db: DBSession, addr: str, *, exclude_user_id: str | None = None
) -> None:
    """Prevent ambiguous recovery routing without disclosing another account."""
    q = db.query(User).filter(User.recovery_email == addr)
    if exclude_user_id:
        q = q.filter(User.id != exclude_user_id)
    if q.first() is not None:
        raise HTTPException(409, detail={
            "error": "recovery_email_in_use",
            "message": "That recovery email is already assigned to another account.",
        })


def _commit_recovery_safe(db: DBSession) -> None:
    """Commit while translating the DB-level recovery-email race into HTTP 409."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        detail = str(getattr(exc, "orig", exc)).lower()
        if "recovery_email" in detail and ("unique" in detail or "duplicate" in detail):
            raise HTTPException(409, detail={
                "error": "recovery_email_in_use",
                "message": "That recovery email is already assigned to another account.",
            }) from exc
        raise


def _flush_recovery_safe(db: DBSession) -> None:
    """Flush a newly-created account while preserving the recovery-email 409 contract."""
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        detail = str(getattr(exc, "orig", exc)).lower()
        if "recovery_email" in detail and ("unique" in detail or "duplicate" in detail):
            raise HTTPException(409, detail={
                "error": "recovery_email_in_use",
                "message": "That recovery email is already assigned to another account.",
            }) from exc
        raise


class AccountUpdateIn(BaseModel):
    display_name: str | None = None
    flight_id: str | None = None  # pass "" or null to clear


class RecoveryEmailIn(BaseModel):
    email: str
    # Re-authentication. This address becomes a credential-reset channel, so
    # changing it is a credential-level act -- a stolen session must not be
    # enough to redirect recovery to an attacker's mailbox.
    current_code: str


class ResetCodeIn(BaseModel):
    new_code: str | None = None      # if omitted, auto-generated
    current_code: str | None = None  # required when resetting own code


class FlightIn(BaseModel):
    name: str
    squadron_id: str


class FlightUpdateIn(BaseModel):
    name: str | None = None
    active_status: bool | None = None


# ─────────────────────────────────────────────
# Account endpoints
# ─────────────────────────────────────────────

@router.get("/accounts")
def list_accounts(wing_id: str | None = None, squadron_id: str | None = None,
                  flight_id: str | None = None, role: str | None = None,
                  active_status: bool | None = None, include_archived: bool = False,
                  db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if not has_known_role(p):
        raise HTTPException(403, detail={"error": "forbidden"})
    q = db.query(User)
    if not include_archived:
        q = q.filter(User.is_archived == False)  # noqa: E712

    # Scope filtering based on actor role
    if p.is_national:
        if wing_id:
            # Filter by wing: both direct wing users and sqn users in that wing
            sqns_in_wing = [s.id for s in db.query(Squadron).filter(Squadron.wing_id == wing_id)]
            q = q.filter((User.wing_id == wing_id) | (User.squadron_id.in_(sqns_in_wing)))
        if squadron_id:
            q = q.filter(User.squadron_id == squadron_id)
    else:
        # Wing: own-Wing accounts plus accounts in the Wing's Squadrons;
        # Squadron: own Squadron (permissions.wing_or_squadron_scope_clause).
        q = q.filter(wing_or_squadron_scope_clause(
            p, db, wing_column=User.wing_id, squadron_column=User.squadron_id))
        if p.is_wing and squadron_id:
            q = q.filter(User.squadron_id == squadron_id)

    if flight_id:
        q = q.filter(User.flight_id == flight_id)
    if role:
        q = q.filter(User.role == role)
    if active_status is not None:
        q = q.filter(User.active_status == active_status)

    users = q.order_by(User.display_name).all()
    ctx = _accounts_context(db, users)
    return [_account_out(u, db, ctx) for u in users]


@router.post("/accounts")
def create_account(body: AccountCreateIn, db: DBSession = Depends(get_db),
                   p: Principal = Depends(get_principal)):
    _require_write_actor(p)
    if body.role not in _ALL_ROLES:
        raise HTTPException(422, detail={"error": "invalid_role"})

    name = body.display_name.strip()
    if not name:
        raise HTTPException(422, detail={"error": "invalid_display_name",
                                         "message": "Display name cannot be empty."})
    if len(name) > 100:
        raise HTTPException(422, detail={"error": "invalid_display_name",
                                         "message": "Display name cannot exceed 100 characters."})

    # Validate actor authority and scope
    _validate_create_scope(p, body.role, body.national_id, body.wing_id, body.squadron_id, db)

    recovery_email = _normalise_recovery_email(body.recovery_email)
    if body.role == "system_admin" and not recovery_email:
        raise HTTPException(422, detail={
            "error": "recovery_email_required",
            "message": "System Administrator accounts require a recovery email.",
        })
    if recovery_email:
        if body.role not in RECOVERY_ROLES:
            raise HTTPException(422, detail={"error": "role_not_recoverable"})
        _ensure_recovery_email_available(db, recovery_email)

    # Flight assignment: only valid for squadron-scoped accounts, and must belong to correct SQN
    flight_id = None
    if body.flight_id:
        if account_scope_type(body.role) != "squadron":
            raise HTTPException(422, detail={"error": "flight_only_for_squadron_scope"})
        fl = db.get(Flight, body.flight_id)
        if not fl or fl.is_archived:
            raise HTTPException(404, detail={"error": "flight_not_found"})
        if fl.squadron_id != body.squadron_id:
            raise HTTPException(422, detail={"error": "flight_not_in_squadron"})
        flight_id = fl.id

    # Derive nat_id for national-scope roles; derive wing_id from squadron for sqn-scope roles
    # so that p.wing_id is populated for wing calendar scope checks.
    nat_id = body.national_id
    wing_id = body.wing_id
    sqn_id = body.squadron_id
    if account_scope_type(body.role) == "squadron" and not wing_id and sqn_id:
        sqn_obj = db.get(Squadron, sqn_id)
        if sqn_obj:
            wing_id = sqn_obj.wing_id
    if account_scope_type(body.role) == "national" and not nat_id:
        nat = db.query(NationalEntity).first()
        nat_id = nat.id if nat else None

    u = User(display_name=name, role=body.role,
             national_id=nat_id, wing_id=wing_id, squadron_id=sqn_id,
             flight_id=flight_id, active_status=True, created_by=p.user_id,
             # Every administrator-issued initial credential is known to
             # someone other than the account holder, whether generated or
             # manually entered. Force the holder to choose their own code on
             # first sign-in.
             must_change_code=True,
             recovery_email=recovery_email,
             recovery_email_verified_at=None,
             recovery_email_updated_at=utcnow() if recovery_email else None,
             recovery_email_updated_by=p.user_id if recovery_email else None)
    db.add(u)
    if recovery_email:
        _flush_recovery_safe(db)
    else:
        db.flush()  # get u.id

    # Generate or hash the initial code
    if body.new_code:
        raw = body.new_code.strip()
        if len(raw) < 6:
            raise HTTPException(422, detail={"error": "invalid_code",
                                             "message": "Access code must be at least 6 characters."})
        if len(raw) > 128:
            raise HTTPException(422, detail={"error": "invalid_code",
                                             "message": "Access code is too long (maximum 128 characters)."})
        plain = raw
    else:
        plain = generate_code()
    ac = AccessCode(user_id=u.id, code_hash=hash_code(plain),
                    active_status=True, created_by=p.user_id,
                    updated_by=p.user_id, updated_at=utcnow())
    db.add(ac)
    verification_raw = None
    if recovery_email:
        verification_raw = mint_token(
            db, u, "verify_email", VERIFY_TTL_MINUTES, None
        )
    if recovery_email:
        _commit_recovery_safe(db)
    else:
        db.commit()

    verification_sent = False
    if recovery_email and verification_raw:
        verification_sent = send_mail(
            recovery_email,
            "Verify your AAFC TMS recovery email",
            "Confirm this address so it can be used to recover your access code.\n\n"
            f"Verification code: {verification_raw}\n\n"
            "It expires in 24 hours. If you did not request this, ignore this email.",
        )

    audit(db, p, object_type="account", object_id=u.id, action="account_created",
          new={"role": body.role, "display_name": body.display_name})
    audit(db, p, object_type="access_code", object_id=u.id, action="code_generated")

    out = _account_out(u, db)
    # Return new code once only — it will not be retrievable again
    out["new_code"] = plain
    out["new_code_notice"] = "This code will not be shown again. Copy it now."
    if recovery_email:
        out["recovery_email"] = mask_email(recovery_email)
        out["recovery_email_verified"] = False
        out["recovery_verification_sent"] = verification_sent
    return out


@router.get("/accounts/{uid}")
def get_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if not has_known_role(p):
        raise HTTPException(403, detail={"error": "forbidden"})
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    if not _can_read_account(p, u, db):
        raise HTTPException(403, detail={"error": "forbidden"})
    return _account_out(u, db)


@router.patch("/accounts/{uid}")
def update_account(uid: str, body: AccountUpdateIn, db: DBSession = Depends(get_db),
                   p: Principal = Depends(get_principal)):
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    # Editing your OWN account (display name / flight only -- AccountUpdateIn
    # has no role/scope field, so this carries no privilege-escalation risk)
    # must not go through _require_manage_authority: that check is keyed off
    # CREATE_AUTHORITY, whose wing_admin/sqn_admin entries deliberately don't
    # include their own role (so they can't mass-create peer-level accounts)
    # -- which meant a wing_admin/sqn_admin editing even their own display
    # name always 403'd. Every other account-management endpoint
    # (change-role, archive, disable, reset-code, ...) keeps its own existing
    # self-action guards untouched; this bypass is scoped to this endpoint only.
    if uid != p.user_id:
        require_manage_authority(p, u, db)

    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(422, detail={"error": "invalid_display_name",
                                             "message": "Display name cannot be empty."})
        if len(name) > 100:
            raise HTTPException(422, detail={"error": "invalid_display_name",
                                             "message": "Display name cannot exceed 100 characters."})
        u.display_name = name

    if body.flight_id is not None:
        if body.flight_id == "":
            u.flight_id = None
        else:
            if account_scope_type(u.role) != "squadron":
                raise HTTPException(422, detail={"error": "flight_only_for_squadron_scope"})
            fl = db.get(Flight, body.flight_id)
            if not fl or fl.is_archived:
                raise HTTPException(404, detail={"error": "flight_not_found"})
            if fl.squadron_id != u.squadron_id:
                raise HTTPException(422, detail={"error": "flight_not_in_squadron"})
            u.flight_id = fl.id

    u.updated_by = p.user_id
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_updated",
          new={"display_name": u.display_name, "flight_id": u.flight_id})
    return {"ok": True}


class ChangeRoleIn(BaseModel):
    new_role: str


@router.post("/accounts/{uid}/change-role")
def change_role(uid: str, body: ChangeRoleIn, db: DBSession = Depends(get_db),
                p: Principal = Depends(get_principal)):
    """Change a target account's role/access type, within the same scope level
    (squadron/wing/national) the account already belongs to. Cross-scope changes
    (e.g. squadron -> wing) are rejected -- that requires reassigning the account's
    org membership too, which is a materially different, riskier operation than a
    permission-level change and isn't handled here."""
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    if uid == p.user_id:
        raise HTTPException(400, detail={"error": "cannot_change_own_role"})
    require_manage_authority(p, u, db)

    new_role = body.new_role
    if new_role not in _ALL_ROLES:
        raise HTTPException(422, detail={"error": "invalid_role"})
    allowed = CREATE_AUTHORITY.get(p.role, set())
    if new_role not in allowed:
        raise HTTPException(403, detail={"error": "forbidden",
                                          "message": f"Your role ({p.role}) cannot assign {new_role}."})
    if new_role == u.role:
        raise HTTPException(400, detail={"error": "role_unchanged"})
    if account_scope_type(new_role) != account_scope_type(u.role):
        raise HTTPException(422, detail={"error": "cross_scope_role_change",
                                          "message": "Changing role across scope levels isn't supported here. Archive this account and create a new one with the target role/scope instead."})
    if (u.role == "system_admin" and u.active_status
            and _last_active_system_admin_count(db) <= 1):
        raise HTTPException(409, detail={"error": "last_active_system_admin",
                                          "message": "Cannot change the role of the last active System Administrator."})

    old_role = u.role
    u.role = new_role
    u.updated_by = p.user_id
    # Force re-login so the new role/permissions take effect immediately rather
    # than the old JWT continuing to carry stale role/scope claims.
    u.token_version = (u.token_version or 0) + 1
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="role_changed",
          old={"role": old_role}, new={"role": new_role, "display_name": u.display_name})
    return {"ok": True}


class ChangeScopeIn(BaseModel):
    new_squadron_id: str | None = None
    new_wing_id: str | None = None


@router.post("/accounts/{uid}/change-scope")
def change_scope(uid: str, body: ChangeScopeIn, db: DBSession = Depends(get_db),
                 p: Principal = Depends(get_principal)):
    """REM-05: move a squadron-scoped account to a different Squadron, or a
    wing-scoped account to a different Wing -- the org-membership move
    change-role explicitly does not attempt (see its own docstring). Never
    changes role or scope LEVEL (still squadron->squadron or wing->wing only)
    -- to change scope level, archive and recreate the account with the
    target role, same guidance change-role gives for cross-scope role changes.

    Safe by construction: every other model with a squadron_id/wing_id stores
    its OWN independent tenancy (a Session's squadron_id is the session's
    squadron, never derived from the creating user's squadron_id at creation
    time), and AuditLog snapshots the actor's scope at time of action with no
    FK to User -- so this never retroactively changes the meaning of any
    historical record. It only changes this account's future write/view scope,
    which permissions.py already re-resolves live from the DB on every request.
    """
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    if uid == p.user_id:
        raise HTTPException(400, detail={"error": "cannot_change_own_scope"})
    require_manage_authority(p, u, db)

    scope = account_scope_type(u.role)
    if scope == "national":
        raise HTTPException(422, detail={"error": "scope_change_not_applicable",
                                          "message": "National-scope accounts have no Squadron/Wing to move."})

    if scope == "wing":
        if body.new_squadron_id:
            raise HTTPException(422, detail={"error": "unexpected_field",
                                              "message": "This account is Wing-scoped; provide new_wing_id, not new_squadron_id."})
        if not body.new_wing_id:
            raise HTTPException(422, detail={"error": "wing_id_required"})
        w = db.get(Wing, body.new_wing_id)
        if not w or w.is_archived:
            raise HTTPException(404, detail={"error": "wing_not_found"})
        if body.new_wing_id == u.wing_id:
            raise HTTPException(400, detail={"error": "scope_unchanged"})
        # _require_manage_authority above already restricts which actors can
        # even reach this branch: wing_admin cannot manage other wing_admin/
        # wing_viewer accounts at all (not in its own CREATE_AUTHORITY set),
        # so only system_admin/national_admin ever get here -- no further
        # destination-authority check is needed.
        old_wing = db.get(Wing, u.wing_id) if u.wing_id else None
        old = {"wing_id": u.wing_id, "wing_code": old_wing.code if old_wing else None}
        u.wing_id = w.id
        u.updated_by = p.user_id
        # Same reasoning as change-role: not required for correctness (scope is
        # read live from the DB every request), but forces a clean re-auth
        # after a materially significant tenancy move, and clears any stale
        # squadron/wing display the target's own already-open UI is holding.
        u.token_version = (u.token_version or 0) + 1
        db.commit()
        audit(db, p, object_type="account", object_id=u.id, action="scope_changed",
              old=old, new={"wing_id": w.id, "wing_code": w.code, "display_name": u.display_name})
        return {"ok": True}

    # scope == "squadron"
    if body.new_wing_id:
        raise HTTPException(422, detail={"error": "unexpected_field",
                                          "message": "This account is Squadron-scoped; provide new_squadron_id, not new_wing_id."})
    if not body.new_squadron_id:
        raise HTTPException(422, detail={"error": "squadron_id_required"})
    sqn = db.get(Squadron, body.new_squadron_id)
    if not sqn or sqn.is_archived:
        raise HTTPException(404, detail={"error": "squadron_not_found"})
    if body.new_squadron_id == u.squadron_id:
        raise HTTPException(400, detail={"error": "scope_unchanged"})
    if wing_admin_outside_own_wing(p, sqn.wing_id):
        raise HTTPException(403, detail={"error": "out_of_scope",
                                          "message": "Wing Admin can only move accounts to Squadrons in their own Wing."})
    if p.role == "sqn_admin":
        # sqn_admin's manage-authority already restricts them to accounts in
        # their own Squadron, and they can never have a valid *different*
        # destination Squadron -- reject explicitly rather than falling
        # through to a check that would always fail anyway.
        raise HTTPException(403, detail={"error": "out_of_scope",
                                          "message": "Squadron Admin cannot move accounts to a different Squadron."})

    old_sqn = db.get(Squadron, u.squadron_id) if u.squadron_id else None
    old = {"squadron_id": u.squadron_id, "squadron_code": old_sqn.code if old_sqn else None,
           "wing_id": u.wing_id, "flight_id": u.flight_id}
    u.squadron_id = sqn.id
    u.wing_id = sqn.wing_id  # keep denormalised wing_id in sync -- wing-calendar scope checks read User.wing_id directly
    # Flight is squadron-local (Flight.squadron_id) -- the old flight almost
    # certainly doesn't belong to the new Squadron. Clear it; the admin can
    # reassign a new one afterward via the existing edit-account PATCH.
    u.flight_id = None
    u.updated_by = p.user_id
    u.token_version = (u.token_version or 0) + 1
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="scope_changed",
          old=old, new={"squadron_id": sqn.id, "squadron_code": sqn.code, "wing_id": sqn.wing_id,
                        "display_name": u.display_name})
    return {"ok": True}


@router.post("/accounts/{uid}/reset-code")
def reset_code(uid: str, body: ResetCodeIn, db: DBSession = Depends(get_db),
               p: Principal = Depends(get_principal)):
    """Generate or set a new access code for the target account.

    The new code is returned ONCE in this response. It cannot be retrieved again.
    The existing code hash is never returned. The new code is stored as a hash only.
    """
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})

    # Self-service: any authenticated user may reset their own code,
    # but must re-authenticate with the current code first — a stolen JWT
    # alone must not be sufficient to rotate the access credential.
    if uid == p.user_id:
        caller_codes = db.query(AccessCode).filter(
            AccessCode.user_id == p.user_id,
            AccessCode.active_status == True  # noqa: E712
        ).all()
        if not any(verify_code(body.current_code or "", ac.code_hash) for ac in caller_codes):
            raise HTTPException(403, detail={
                "error": "reauth_required",
                "message": "Enter your current access code to change it."})
    else:
        require_manage_authority(p, u, db)

    raw = (body.new_code or "").strip()
    if raw:
        if len(raw) < 6:
            raise HTTPException(422, detail={"error": "invalid_code",
                                             "message": "Access code must be at least 6 characters."})
        if len(raw) > 128:
            raise HTTPException(422, detail={"error": "invalid_code",
                                             "message": "Access code is too long (maximum 128 characters)."})
        plain = raw
    else:
        plain = generate_code()
    ac = db.query(AccessCode).filter(
        AccessCode.user_id == u.id,
        AccessCode.active_status == True  # noqa: E712
    ).first()
    if not ac:
        ac = AccessCode(user_id=u.id, code_hash="", created_by=p.user_id)
        db.add(ac)
    ac.code_hash = hash_code(plain)
    ac.active_status = bool(u.active_status)  # preserve disabled state
    ac.updated_at = utcnow()
    ac.updated_by = p.user_id
    u.token_version = (u.token_version or 0) + 1
    # Self-service reset with the current credential is the holder choosing a
    # new code. An administrator-issued reset is a temporary credential and
    # must be rotated by the target on first use.
    u.must_change_code = uid != p.user_id
    db.commit()

    action = "change_own_code" if uid == p.user_id else "reset_access"
    audit(db, p, object_type="access_code", object_id=u.id, action=action,
          new={"target_display_name": u.display_name, "target_role": u.role})

    return {
        "ok": True,
        "new_code": plain,
        "new_code_notice": "This code will not be shown again. Copy it now.",
    }


@router.post("/accounts/{uid}/recovery-email")
def set_recovery_email(uid: str, body: RecoveryEmailIn,
                       db: DBSession = Depends(get_db),
                       p: Principal = Depends(get_principal)):
    """Set or change an account's recovery email. Always leaves it UNVERIFIED.

    Entering an address must not by itself make it a trusted channel, so this
    clears any existing verification and mails a fresh verification link. A new
    address inherits nothing from the old one.
    """
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    if uid != p.user_id:
        _require_write_actor(p)
        require_manage_authority(p, u, db)

    if u.role not in RECOVERY_ROLES:
        raise HTTPException(400, detail={
            "error": "role_not_recoverable",
            "message": "Recovery email is only held for administrator accounts."})

    addr = _normalise_recovery_email(body.email)
    assert addr is not None
    _ensure_recovery_email_available(db, addr, exclude_user_id=u.id)

    # Re-authenticate the CALLER against their own live code.
    caller_codes = db.query(AccessCode).filter(
        AccessCode.user_id == p.user_id, AccessCode.active_status == True).all()  # noqa: E712
    if not any(verify_code(body.current_code or "", ac.code_hash) for ac in caller_codes):
        raise HTTPException(403, detail={
            "error": "reauth_failed",
            "message": "Enter your current access code to change a recovery email."})

    old_addr = u.recovery_email
    u.recovery_email = addr
    u.recovery_email_verified_at = None
    u.recovery_email_updated_at = utcnow()
    u.recovery_email_updated_by = p.user_id

    raw = mint_token(db, u, "verify_email", VERIFY_TTL_MINUTES, None)
    _commit_recovery_safe(db)

    sent = send_mail(
        addr,
        "Verify your AAFC TMS recovery email",
        "Confirm this address so it can be used to recover your access code.\n\n"
        f"Verification code: {raw}\n\n"
        "It expires in 24 hours. If you did not request this, ignore this email.",
    )
    audit(db, p, object_type="user", object_id=uid, action="recovery_email_changed",
          old={"had_address": bool(old_addr)}, new={"verified": False})
    return {"ok": True, "recovery_email": mask_email(addr),
            "verified": False, "email_sent": sent, "verification_sent": sent}


@router.post("/accounts/{uid}/disable")
def disable_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    if uid == p.user_id:
        raise HTTPException(400, detail={"error": "cannot_disable_self"})
    require_manage_authority(p, u, db)
    if (u.role == "system_admin" and u.active_status
            and _last_active_system_admin_count(db) <= 1):
        raise HTTPException(409, detail={
            "error": "last_active_system_admin",
            "message": "This is the last active System Administrator. Create or "
                       "activate another System Administrator before removing "
                       "this account."})
    u.active_status = False
    u.updated_by = p.user_id
    # Invalidate any live JWTs immediately by incrementing token_version — without
    # this, a disabled account's existing token remains valid until its natural
    # expiry (typically 8 h), leaving the session live after the disable.
    u.token_version = (u.token_version or 0) + 1
    # Also deactivate the access code so login is blocked immediately
    for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
        ac.active_status = False
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_disabled",
          new={"display_name": u.display_name, "role": u.role})
    return {"ok": True}


@router.post("/accounts/{uid}/reactivate")
def reactivate_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    require_manage_authority(p, u, db)
    u.active_status = True
    u.updated_by = p.user_id
    for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
        ac.active_status = True
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_reactivated",
          new={"display_name": u.display_name, "role": u.role})
    return {"ok": True}


def _last_active_system_admin_count(db: DBSession) -> int:
    return db.query(User).filter(User.role == "system_admin", User.active_status == True,  # noqa: E712
                                 User.is_archived == False).count()  # noqa: E712


@router.post("/accounts/{uid}/archive")
def archive_account(uid: str, reason: str | None = None, db: DBSession = Depends(get_db),
                    p: Principal = Depends(get_principal)):
    """Archive (not delete) a single account: active_status=False + is_archived=True.
    Reversible via .../restore. Extends the existing disable mechanism rather
    than a parallel one -- archiving implies disabling (access is revoked)."""
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    if uid == p.user_id:
        raise HTTPException(400, detail={"error": "cannot_archive_self"})
    require_manage_authority(p, u, db)
    if u.role == "system_admin" and u.active_status and _last_active_system_admin_count(db) <= 1:
        raise HTTPException(409, detail={"error": "last_active_system_admin",
                                          "message": "Cannot archive the last active System Administrator."})
    u.active_status = False
    u.is_archived = True
    u.archived_at = utcnow()
    u.updated_by = p.user_id
    u.token_version = (u.token_version or 0) + 1  # invalidate pre-archive JWTs
    for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
        ac.active_status = False
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_archived",
          new={"display_name": u.display_name, "role": u.role}, reason=reason)
    return {"ok": True}


@router.post("/accounts/{uid}/restore")
def restore_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Restore an archived account directly to active (not merely un-archived-but-
    still-disabled) -- a restored account should be immediately usable pending a
    fresh decision to disable it again, not left in a confusing third state."""
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or not u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    require_manage_authority(p, u, db)
    u.is_archived = False
    u.archived_at = None
    u.active_status = True
    u.updated_by = p.user_id
    u.token_version = (u.token_version or 0) + 1  # prevent pre-archive JWTs resurrecting
    for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
        ac.active_status = True
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_restored",
          new={"display_name": u.display_name, "role": u.role})
    return {"ok": True}


@router.delete("/accounts/{uid}")
def delete_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Permanent delete -- only when already archived AND a dependency check
    shows the account performed no privileged actions of its own and has
    never actually been used (no last_login_at). Deliberately does NOT block
    on audit entries where this account is merely the *target* (e.g. its own
    account_created/account_archived rows) -- those are just this account's
    own lifecycle history, not another record depending on it, and archiving
    is itself a required precondition here, so treating it as a blocker
    would make every hard-delete unreachable. AuditLog.user_id has no
    DB-level foreign key (deliberately decoupled so audit history survives
    account changes), so the "performed privileged actions" check below is a
    policy choice, not something the database enforces on its own -- matching
    "block where audit or operational history requires the account
    identifier". Additive to the existing archive path; archive remains the
    default whenever any dependent exists."""
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, detail={"error": "not_found"})
    require_manage_authority(p, u, db)
    if not u.is_archived:
        raise HTTPException(409, detail={"error": "not_archived",
                                          "message": "Archive this account first before permanently deleting it."})
    # Protected transitively -- deletion requires archiving first, and archive is
    # already guarded -- but stated locally so the invariant survives someone
    # relaxing the archive-first rule later.
    if (u.role == "system_admin" and u.active_status
            and _last_active_system_admin_count(db) <= 1):
        raise HTTPException(409, detail={
            "error": "last_active_system_admin",
            "message": "This is the last active System Administrator. Create or "
                       "activate another System Administrator before removing "
                       "this account."})

    # fk_dependents walks every real foreign key pointing at users.id (today:
    # ProxySession.actor_user_id; automatically covers anything added later)
    # -- access_codes.user_id is excluded since those rows are intentionally
    # cascade-deleted below as part of the account, not a blocker.
    dependents = fk_dependents(db, "users", uid)
    dependents.pop("access_codes.user_id", None)
    audit_as_actor = db.query(AuditLog).filter(AuditLog.user_id == uid).count()
    if audit_as_actor:
        dependents["audit_log_as_actor"] = audit_as_actor
    if u.last_login_at is not None:
        dependents["has_logged_in"] = 1
    if dependents:
        raise HTTPException(409, detail={
            "error": "has_dependents", "dependents": dependents,
            "message": "This account has audit or login history and cannot be permanently deleted. It remains archived.",
        })

    display_name, role = u.display_name, u.role
    for ac in db.query(AccessCode).filter(AccessCode.user_id == uid).all():
        db.delete(ac)
    db.delete(u)
    db.commit()
    audit(db, p, object_type="account", object_id=uid, action="delete",
          old={"display_name": display_name, "role": role})
    return {"ok": True}


class BatchArchiveIn(BaseModel):
    account_ids: list[str]
    reason: str
    effective_at: str | None = None  # audit-display only -- no job scheduler exists in this codebase
    confirm_session_revocation: bool = False


@router.post("/accounts/batch-archive")
def batch_archive_accounts(body: BatchArchiveIn, db: DBSession = Depends(get_db),
                           p: Principal = Depends(get_principal)):
    """Archive multiple accounts in one guided operation. Each account is its own
    commit (not one outer transaction) so one bad row's failure never discards
    already-decided, already-correct outcomes for the rest of the batch -- every
    item gets an explicit, inspectable per-item result, never a silent partial
    success. One batch_id correlates every row's audit entry plus one summary row."""
    import uuid as _uuid
    _require_write_actor(p)
    if not (body.reason or "").strip() or len(body.reason.strip()) < 10:
        raise HTTPException(400, detail={"error": "reason_required",
                                          "message": "A reason of at least 10 characters is required."})
    if not body.confirm_session_revocation:
        raise HTTPException(400, detail={"error": "session_revocation_not_confirmed",
                                          "message": "You must confirm that active sessions will be revoked."})
    if not body.account_ids:
        raise HTTPException(400, detail={"error": "no_accounts_selected"})

    batch_id = str(_uuid.uuid4())
    remaining_active_system_admins = _last_active_system_admin_count(db)
    results = []
    for uid in body.account_ids:
        try:
            u = db.get(User, uid)
            if not u:
                results.append({"account_id": uid, "result": "failed", "reason": "not_found"})
                continue
            if u.is_archived:
                results.append({"account_id": uid, "result": "already_archived",
                               "display_name": u.display_name, "role": u.role})
                continue
            if uid == p.user_id:
                results.append({"account_id": uid, "result": "skipped", "reason": "cannot_archive_self",
                               "display_name": u.display_name, "role": u.role})
                continue
            try:
                require_manage_authority(p, u, db)
            except HTTPException:
                results.append({"account_id": uid, "result": "failed", "reason": "out_of_scope",
                               "display_name": u.display_name, "role": u.role})
                continue
            if u.role == "system_admin" and u.active_status:
                if remaining_active_system_admins <= 1:
                    results.append({"account_id": uid, "result": "skipped", "reason": "last_active_system_admin",
                                   "display_name": u.display_name, "role": u.role})
                    continue
                remaining_active_system_admins -= 1
            u.active_status = False
            u.is_archived = True
            u.archived_at = utcnow()
            u.updated_by = p.user_id
            u.token_version = (u.token_version or 0) + 1  # invalidate pre-archive JWTs
            for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
                ac.active_status = False
            audit(db, p, object_type="account", object_id=u.id, action="account_archived",
                  new={"display_name": u.display_name, "role": u.role}, reason=body.reason,
                  batch_id=batch_id, commit=False)
            db.commit()
            results.append({"account_id": uid, "result": "archived",
                           "display_name": u.display_name, "role": u.role})
        except Exception as e:
            db.rollback()
            # R5-L03: do not expose raw SQLAlchemy exception (leaks table/constraint names)
            results.append({"account_id": uid, "result": "failed", "reason": "database_error"})

    summary = {
        "archived": sum(1 for r in results if r["result"] == "archived"),
        "already_archived": sum(1 for r in results if r["result"] == "already_archived"),
        "skipped": sum(1 for r in results if r["result"] == "skipped"),
        "failed": sum(1 for r in results if r["result"] == "failed"),
    }
    audit(db, p, object_type="account_archive_batch", object_id=batch_id, action="batch_archive",
          new={"total": len(body.account_ids), **summary}, reason=body.reason, batch_id=batch_id)
    return {"ok": True, "batch_id": batch_id, "results": results, "summary": summary}


@router.post("/accounts/{uid}/unlock")
def unlock_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Reset the per-account login lockout for a user.

    Clears failed_attempts and locked_until on the user's active access code.
    Requires the same management authority as reset-code (wing_admin for squadron
    accounts in their wing, national_admin / system_admin for wider scope).
    """
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    require_manage_authority(p, u, db)
    ac = db.query(AccessCode).filter(AccessCode.user_id == u.id,
                                     AccessCode.active_status == True).first()  # noqa: E712
    if not ac:
        raise HTTPException(404, detail={"error": "not_found"})
    ac.failed_attempts = 0
    ac.locked_until = None
    db.commit()
    audit(db, p, object_type="access_code", object_id=u.id, action="lockout_reset",
          new={"display_name": u.display_name, "role": u.role})
    return {"ok": True}


# ─────────────────────────────────────────────
# Flight endpoints (Squadron-local groupings)
# ─────────────────────────────────────────────

def _can_write_flight(p: Principal, sqn_id: str, db: DBSession) -> None:
    """Only sqn_admin (own SQN), wing_admin (own Wing), nat_admin, system_admin."""
    if is_national_admin(p):
        return
    if p.role == "wing_admin":
        sqn = db.get(Squadron, sqn_id)
        if not sqn or sqn.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
        return
    if p.role == "sqn_admin":
        if sqn_id != p.squadron_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
        return
    raise HTTPException(403, detail={"error": "forbidden"})


@router.get("/flights")
def list_flights(squadron_id: str | None = None, include_archived: bool = False,
                 db: DBSession = Depends(get_db),
                 p: Principal = Depends(get_principal)):
    q = db.query(Flight)
    if not include_archived:
        q = q.filter(Flight.is_archived == False)  # noqa: E712
    scope = squadron_scope_clause(p, db, Flight.squadron_id)
    if scope is not None:
        q = q.filter(scope)
    if squadron_id:
        # A Squadron account naming another Squadron gets [] (the two filters
        # cannot both hold), as it always did.
        q = q.filter(Flight.squadron_id == squadron_id)
    return [_flight_out(f, db) for f in q.order_by(Flight.name).all()]


@router.post("/flights")
def create_flight(body: FlightIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    _can_write_flight(p, body.squadron_id, db)
    f = Flight(squadron_id=body.squadron_id, name=body.name.strip(),
               active_status=True, created_by=p.user_id)
    db.add(f)
    db.commit()
    audit(db, p, object_type="flight", object_id=f.id, action="flight_created",
          new={"name": f.name, "squadron_id": f.squadron_id})
    return {**_flight_out(f, db), "ok": True}


@router.patch("/flights/{fid}")
def update_flight(fid: str, body: FlightUpdateIn, db: DBSession = Depends(get_db),
                  p: Principal = Depends(get_principal)):
    f = db.get(Flight, fid)
    if not f or f.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    _can_write_flight(p, f.squadron_id, db)
    if body.name is not None:
        f.name = body.name.strip()
    if body.active_status is not None:
        f.active_status = body.active_status
    f.updated_by = p.user_id
    db.commit()
    audit(db, p, object_type="flight", object_id=f.id, action="flight_updated")
    return {"ok": True}


@router.post("/flights/{fid}/archive")
def archive_flight(fid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    f = db.get(Flight, fid)
    if not f or f.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    _can_write_flight(p, f.squadron_id, db)
    # Clear flight assignment from any users first
    db.query(User).filter(User.flight_id == f.id).update({"flight_id": None}, synchronize_session=False)
    f.is_archived = True
    f.archived_at = utcnow()
    f.updated_by = p.user_id
    db.commit()
    audit(db, p, object_type="flight", object_id=f.id, action="flight_archived")
    return {"ok": True}


@router.post("/flights/{fid}/restore")
def restore_flight(fid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """REM-108: Flight archive existed with no restore counterpart -- following
    the exact same dependency-gated archive/restore pattern already used for
    Account/Wing/Squadron/PlanningYear (see restore_squadron in
    organisations.py, this endpoint's direct template)."""
    f = db.get(Flight, fid)
    if not f:
        raise HTTPException(404, detail={"error": "not_found"})
    _can_write_flight(p, f.squadron_id, db)
    if not f.is_archived:
        raise HTTPException(409, detail={"error": "not_archived"})
    f.is_archived = False
    f.archived_at = None
    f.updated_by = p.user_id
    db.commit()
    audit(db, p, object_type="flight", object_id=f.id, action="flight_restored")
    return {"ok": True}


def _flight_out(f: Flight, db: DBSession | None = None) -> dict:
    sqn_code = sqn_name = None
    if db and f.squadron_id:
        s = db.get(Squadron, f.squadron_id)
        if s:
            sqn_code, sqn_name = s.code, s.name
    return {"flight_id": f.id, "squadron_id": f.squadron_id,
            "squadron_code": sqn_code, "squadron_name": sqn_name,
            "name": f.name, "active_status": f.active_status,
            "is_archived": f.is_archived,
            "created_at": iso_z(f.created_at) if f.created_at else None}
