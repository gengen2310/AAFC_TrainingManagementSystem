"""Account-role authority rules shared by account and auth workflows.

Keep account-management hierarchy out of HTTP routers so credential changes
and account-management endpoints use exactly the same policy.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from .models import Squadron, User
from .permissions import Principal

CREATE_AUTHORITY: dict[str, set[str]] = {
    "system_admin": {
        "system_admin", "national_admin", "national_viewer",
        "wing_admin", "wing_viewer", "sqn_admin", "sqn_general", "auditor",
    },
    "national_admin": {
        "national_admin", "national_viewer",
        "wing_admin", "wing_viewer", "sqn_admin", "sqn_general", "auditor",
    },
    "wing_admin": {"wing_viewer", "sqn_admin", "sqn_general"},
    "sqn_admin": {"sqn_general"},
}

NATIONAL_SCOPE_ROLES = {"national_admin", "national_viewer", "system_admin", "auditor"}
WING_SCOPE_ROLES = {"wing_admin", "wing_viewer"}
SQN_SCOPE_ROLES = {"sqn_admin", "sqn_general"}


def account_scope_type(role: str) -> str:
    if role in NATIONAL_SCOPE_ROLES:
        return "national"
    if role in WING_SCOPE_ROLES:
        return "wing"
    return "squadron"


def require_manage_authority(p: Principal, target: User, db: DBSession) -> None:
    """Raise 403 when actor lacks management authority over target account."""
    allowed = CREATE_AUTHORITY.get(p.role, set())
    if target.role not in allowed:
        raise HTTPException(403, detail={"error": "forbidden"})

    scope = account_scope_type(target.role)
    if scope == "wing" and p.role == "wing_admin":
        if target.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
    elif scope == "squadron":
        if p.role == "wing_admin":
            squadron = db.get(Squadron, target.squadron_id)
            if not squadron or squadron.wing_id != p.wing_id:
                raise HTTPException(403, detail={"error": "out_of_scope"})
        elif p.role == "sqn_admin":
            if target.squadron_id != p.squadron_id:
                raise HTTPException(403, detail={"error": "out_of_scope"})
