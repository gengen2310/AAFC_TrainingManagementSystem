"""RBAC + multi-tenant scoping — enforced entirely server-side.

A Principal is built from the JWT and live proxy state. All scope decisions
(which wing/squadron a request may read or write) flow through this module so
no router re-implements tenancy ad hoc.
"""
from dataclasses import dataclass
from fastapi import HTTPException

# Role catalogue
ROLES = {
    "sqn_general", "sqn_admin",
    "wing_viewer", "wing_admin",
    "national_viewer", "national_admin",
    "system_admin", "auditor",
}
WRITE_ROLES = {"sqn_admin", "wing_admin", "national_admin", "system_admin"}
SQUADRON_LEVEL = {"sqn_general", "sqn_admin"}
WING_LEVEL = {"wing_viewer", "wing_admin"}
NATIONAL_LEVEL = {"national_viewer", "national_admin", "system_admin", "auditor"}
# Named role sets used for authorization decisions across routers (previously
# re-declared or spelled out inline in each router).
NATIONAL_ADMIN_ROLES = frozenset({"national_admin", "system_admin"})
WING_WRITE_ROLES = frozenset({"wing_admin", "national_admin", "system_admin"})
READ_ONLY_ROLES = frozenset({"sqn_general", "wing_viewer", "national_viewer", "auditor"})


def is_national_admin(p: "Principal") -> bool:
    """national_admin or system_admin (e.g. may edit national curriculum)."""
    return p.role in NATIONAL_ADMIN_ROLES


def is_wing_writer(p: "Principal") -> bool:
    """May write Wing-owned data: wing_admin, national_admin, system_admin."""
    return p.role in WING_WRITE_ROLES


def is_writer(p: "Principal") -> bool:
    """Any write-capable role (WRITE_ROLES)."""
    return p.role in WRITE_ROLES


def is_read_only_role(p: "Principal") -> bool:
    """Roles with no write authority anywhere."""
    return p.role in READ_ONLY_ROLES


def sqn_admin_outside_own_squadron(p: "Principal", squadron_id: str | None) -> bool:
    """True when a Squadron Admin is acting on a target outside their own
    Squadron (the Squadron counterpart of wing_admin_outside_own_wing). Each
    caller keeps its own error response."""
    return p.role == "sqn_admin" and squadron_id != p.squadron_id


def has_known_role(p: "Principal") -> bool:
    """Any recognised role. Gates written as "role in <every role>" only refuse
    a principal whose role is unrecognised (corrupt or retired)."""
    return p.role in ROLES


def wing_admin_outside_own_wing(p: "Principal", wing_id: str | None) -> bool:
    """True when a Wing Admin is acting on a target outside their own Wing.

    The rule "a Wing Admin acts only inside their own Wing" was written inline
    at every Wing-scoped write (accounts, organisations, training reference
    data, Wing calendar, Service Desk, custom phases). Each caller keeps its own
    error response; only the condition lives here. Other roles are not
    constrained by this predicate (their scope is checked elsewhere)."""
    return p.role == "wing_admin" and wing_id != p.wing_id


def may_view_cadet_records(p: "Principal") -> bool:
    """Cadet personal and training records (cadet list, risk, class
    membership and rosters, training-record matrix/export, a cadet's record,
    sessions needing attention). sqn_general is excluded; every other role
    still passes its own scope checks afterwards.

    Policy question open with the product owner: whether sqn_general, a
    read-only Squadron role, is meant to be refused these reads. This is the
    one place that decides it."""
    return p.role != "sqn_general"


def may_record_session_outcomes(p: "Principal") -> bool:
    """Deliver / cancel / reschedule a session. sqn_general is excluded; the
    session write checks that follow apply to everyone else."""
    return p.role != "sqn_general"


@dataclass
class Principal:
    user_id: str
    role: str
    wing_id: str | None
    squadron_id: str | None
    national_id: str | None
    # live intervention state (resolved from active ProxySession)
    proxy_session_id: str | None = None
    proxy_mode: str | None = None              # proxy | delegated_intervention
    acting_wing_id: str | None = None
    acting_squadron_id: str | None = None

    # ── scope helpers ──
    @property
    def is_national(self) -> bool:
        return self.role in NATIONAL_LEVEL

    @property
    def is_squadron(self) -> bool:
        return self.role in SQUADRON_LEVEL

    @property
    def is_wing(self) -> bool:
        return self.role in WING_LEVEL

    @property
    def is_system_admin(self) -> bool:
        return self.role == "system_admin"

    @property
    def is_auditor(self) -> bool:
        return self.role == "auditor"

    @property
    def active_squadron_id(self) -> str | None:
        """The squadron this caller is working ON, as opposed to who they are.

        Authorisation uses the base identity -- can_write_squadron deliberately
        checks self.squadron_id and the proxy mode. Data SELECTION uses this:
        which squadron does an unqualified request mean?

        For a squadron account that is their own squadron. For a wing or
        national account it is the proxy / delegated-intervention target, and
        None when no session is active -- those accounts have no home squadron,
        so an endpoint that defaults from squadron_id alone silently resolves to
        None for them and skips whatever guard sits behind `if squadron_id:`.
        """
        return self.acting_squadron_id or self.squadron_id

    def can_view_squadron(self, squadron_id: str, wing_id: str | None) -> bool:
        if self.role in ("national_viewer", "national_admin", "system_admin", "auditor"):
            return True
        if self.role in ("wing_viewer", "wing_admin"):
            return wing_id == self.wing_id
        return squadron_id == self.squadron_id

    def can_view_wing(self, wing_id: str) -> bool:
        if self.is_national:
            return True
        if self.is_wing:
            return wing_id == self.wing_id
        return False

    def can_write_squadron(self, squadron_id: str, wing_id: str | None) -> bool:
        if self.role == "sqn_admin":
            return squadron_id == self.squadron_id
        if self.role == "wing_admin":
            # only through an active proxy into THIS squadron
            return self.proxy_mode == "proxy" and self.acting_squadron_id == squadron_id
        if self.role in ("national_admin", "system_admin"):
            # only through delegated intervention into THIS squadron
            return self.proxy_mode == "delegated_intervention" and self.acting_squadron_id == squadron_id
        return False

    def can_write_activity(self, owning_level: str, wing_id: str | None, squadron_id: str | None) -> bool:
        """Activity write authority is resolved from the ROW's own owning_level/
        wing_id/squadron_id (the caller must fetch the row first), never from
        caller-supplied context -- otherwise a Squadron admin could PATCH a
        Wing/National-owned Activity by ID-guessing."""
        if owning_level == "national":
            return self.role in ("national_admin", "system_admin")
        if owning_level == "wing":
            if self.role == "wing_admin":
                # Wing Admin writes their own Wing's activities directly, no
                # proxy needed -- matches wing_calendar.py's existing convention
                # for Wing-owned records.
                return wing_id == self.wing_id
            if self.role in ("national_admin", "system_admin"):
                # No standalone "wing-level" intervention mode exists -- acting_wing_id
                # is only ever set as a side effect of entering Delegated Intervention
                # into a squadron (see organisations.py enter_mode), so this requires
                # an active intervention session on some squadron within this Wing.
                return self.acting_wing_id == wing_id
            return False
        # squadron-owned (or unowned, which is never writable)
        if not squadron_id:
            return False
        return self.can_write_squadron(squadron_id, wing_id)


def require_can_write_squadron(p: Principal, squadron_id: str, wing_id: str | None):
    if p.can_write_squadron(squadron_id, wing_id):
        return
    if p.role == "wing_admin":
        raise HTTPException(403, detail={"error": "proxy_required",
                                         "message": "Wing Admin must enter Proxy Mode to edit squadron data."})
    if p.role in ("national_admin", "system_admin"):
        raise HTTPException(403, detail={"error": "intervention_required",
                                         "message": "National Admin or System Administrator must enter Delegated Intervention Mode to edit this data."})
    raise HTTPException(403, detail={"error": "forbidden"})


def require_can_view_squadron(p: Principal, squadron_id: str, wing_id: str | None):
    if p.can_view_squadron(squadron_id, wing_id):
        return
    if p.role in ("wing_viewer", "wing_admin"):
        msg = "This squadron belongs to a different Wing than your account."
    elif p.role in ("sqn_admin", "sqn_general"):
        msg = "This record belongs to a different Squadron than your account."
    else:
        msg = "You do not have access to this squadron."
    raise HTTPException(403, detail={"error": "forbidden", "message": msg})


def require_can_view_wing(p: Principal, wing_id: str):
    if p.can_view_wing(wing_id):
        return
    if p.is_wing:
        msg = "This Wing belongs to a different command than your account."
    elif p.role in ("sqn_admin", "sqn_general"):
        msg = "Squadron accounts cannot view Wing-level records."
    else:
        msg = "You do not have access to this Wing."
    raise HTTPException(403, detail={"error": "forbidden", "message": msg})


def require_can_write_activity(p: Principal, owning_level: str, wing_id: str | None, squadron_id: str | None):
    if p.can_write_activity(owning_level, wing_id, squadron_id):
        return
    if owning_level == "national":
        raise HTTPException(403, detail={"error": "cannot_edit_national_activity"})
    if owning_level == "wing":
        if p.role == "wing_admin":
            raise HTTPException(403, detail={"error": "out_of_scope"})
        if p.role in ("national_admin", "system_admin"):
            raise HTTPException(403, detail={
                "error": "intervention_required",
                "message": ("National Admin or System Administrator must enter Delegated "
                            "Intervention Mode (into a squadron within this Wing) to edit this data."),
            })
        raise HTTPException(403, detail={"error": "cannot_edit_wing_activity"})
    require_can_write_squadron(p, squadron_id, wing_id)


def require_role(p: Principal, *roles: str):
    if p.role not in roles:
        allowed = ", ".join(sorted(roles))
        raise HTTPException(403, detail={
            "error": "forbidden",
            "message": f"This action requires one of the following roles: {allowed}.",
        })


def require_write_role(p: Principal, message: str | None = None):
    """Require one of the system's write-capable roles."""
    if p.role not in WRITE_ROLES:
        raise HTTPException(403, detail={
            "error": "forbidden",
            "message": message or "This action requires write-capable administrator access.",
        })


def resolve_view_squadron_id(p: Principal, squadron_id: str | None, db) -> str | None:
    """Resolve the Squadron an unqualified READ means.

    An explicit Squadron is validated through the same central view-policy used
    everywhere else. With no explicit target, a Squadron account reads its
    home Squadron and a higher-scope account reads its current proxy/
    intervention target (or None when no Squadron has been selected).

    This helper intentionally performs no write authorization.
    """
    if squadron_id:
        from .models import Squadron
        squadron = db.get(Squadron, squadron_id)
        if not squadron:
            raise HTTPException(404, detail={"error": "squadron_not_found"})
        require_can_view_squadron(p, squadron.id, squadron.wing_id)
        return squadron.id
    return p.active_squadron_id


def require_system_admin(p: Principal):
    if not p.is_system_admin:
        raise HTTPException(403, detail={
            "error": "forbidden",
            "message": "This action is restricted to System Administrators.",
        })


def require_system_or_nat_admin(p: Principal):
    if p.role not in ("system_admin", "national_admin"):
        raise HTTPException(403, detail={
            "error": "forbidden",
            "message": "This action requires National Administrator or System Administrator access.",
        })


AUDIT_READ_ROLES = frozenset({
    "auditor",
    "sqn_admin",
    "sqn_general",
    "wing_admin",
    "national_admin",
    "national_viewer",
    "system_admin",
})


def require_audit_access(p: Principal):
    """Central policy for read-only audit-log access.

    Scope filtering remains the caller's responsibility; this helper answers
    only whether the role may read audit records at all.
    """
    if p.role not in AUDIT_READ_ROLES:
        raise HTTPException(403, detail={
            "error": "forbidden",
            "message": "This role does not have audit-log read access.",
        })
