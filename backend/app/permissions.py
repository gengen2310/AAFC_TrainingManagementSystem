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
WING_LEVEL = {"wing_viewer", "wing_admin"}
NATIONAL_LEVEL = {"national_viewer", "national_admin", "system_admin", "auditor"}


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


def require_audit_access(p: Principal):
    """Roles permitted to read audit logs."""
    if p.role not in ("system_admin", "national_admin", "auditor"):
        raise HTTPException(403, detail={
            "error": "forbidden",
            "message": "Audit log access is restricted to System Administrator, National Administrator, or Auditor roles.",
        })
