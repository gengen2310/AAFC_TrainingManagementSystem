"""Governed reference-tag helpers shared by the five tag families (subject
areas, facilitator types, session-status reasons, activity types, training-area
capabilities): name normalisation, the global-visibility and scope-collision
query filters, and each family's response serialiser.

Moved verbatim from routers/training.py (stabilisation Phase 3, C5). Pure
filter construction and dict building: no HTTP, no authorization -- the
create/visibility policy that consumes these stays in the router.
"""
from __future__ import annotations

from .database import iso_z
from .models import (ActivityTypeTag, FacilitatorTypeTag, SessionStatusReasonTag, SubjectAreaTag,
                     TrainingAreaCapabilityTag)


def _normalise_tag(name: str) -> str:
    """Lower-case, collapse internal whitespace, strip edges."""
    import re
    return re.sub(r"\s+", " ", name.strip().lower())


def _tag_global_visible(model, national_id: str | None):
    """"global" means global within one national entity, not installation-wide.

    A NULL national_id is a pre-v60 row whose origin cannot be recovered, so it
    stays visible to everyone -- narrowing it would silently hide existing
    reference data."""
    cond = model.scope == "global"
    if national_id:
        cond = cond & (
            (model.national_id == national_id) | (model.national_id.is_(None))
        )
    return cond


def _tag_conflict_filter(model, scope: str, national_id: str | None,
                         wing_id: str | None, squadron_id: str | None):
    """Tags a new tag would collide with: its own scope, plus any ancestor
    scope that already covers it -- never a sibling.

    The pre-v60 form ORed the scope columns independently, so
    ``wing_id == <my wing>`` matched every tag anywhere in the wing: 703 blocked
    704 from reusing a name, and the 409 body handed 703's tag id to 704."""
    from sqlalchemy import or_ as _or_tag_conflict
    conditions = [_tag_global_visible(model, national_id)]
    if scope in ("wing", "squadron") and wing_id:
        conditions.append((model.scope == "wing") & (model.wing_id == wing_id))
    if scope == "squadron" and squadron_id:
        conditions.append((model.scope == "squadron") & (model.squadron_id == squadron_id))
    return _or_tag_conflict(*conditions)


def _tag_out(t: SubjectAreaTag) -> dict:
    return {
        "tag_id": t.id,
        "display_name": t.display_name,
        "normalised_name": t.normalised_name,
        "scope": t.scope,
        "national_id": t.national_id,
        "squadron_id": t.squadron_id,
        "wing_id": t.wing_id,
        "is_active": t.is_active,
        "created_by": t.created_by,
        "created_at": iso_z(t.created_at) if t.created_at else None,
    }


def _fac_type_out(t: FacilitatorTypeTag) -> dict:
    return {
        "tag_id": t.id,
        "display_name": t.display_name,
        "normalised_name": t.normalised_name,
        "scope": t.scope,
        "national_id": t.national_id,
        "squadron_id": t.squadron_id,
        "wing_id": t.wing_id,
        "is_active": t.is_active,
        "created_by": t.created_by,
        "created_at": iso_z(t.created_at) if t.created_at else None,
    }


def _reason_out(t: SessionStatusReasonTag) -> dict:
    return {
        "tag_id": t.id,
        "display_name": t.display_name,
        "normalised_name": t.normalised_name,
        "scope": t.scope,
        "national_id": t.national_id,
        "squadron_id": t.squadron_id,
        "wing_id": t.wing_id,
        "is_active": t.is_active,
        "created_by": t.created_by,
        "created_at": iso_z(t.created_at) if t.created_at else None,
    }


def _acttype_out(t: ActivityTypeTag) -> dict:
    return {
        "tag_id": t.id,
        "display_name": t.display_name,
        "normalised_name": t.normalised_name,
        "scope": t.scope,
        "national_id": t.national_id,
        "squadron_id": t.squadron_id,
        "wing_id": t.wing_id,
        "is_active": t.is_active,
        "created_by": t.created_by,
        "created_at": iso_z(t.created_at) if t.created_at else None,
    }


def _capability_out(t: TrainingAreaCapabilityTag) -> dict:
    return {
        "tag_id": t.id,
        "display_name": t.display_name,
        "normalised_name": t.normalised_name,
        "scope": t.scope,
        "national_id": t.national_id,
        "squadron_id": t.squadron_id,
        "wing_id": t.wing_id,
        "is_active": t.is_active,
        "created_by": t.created_by,
        "created_at": iso_z(t.created_at) if t.created_at else None,
    }
