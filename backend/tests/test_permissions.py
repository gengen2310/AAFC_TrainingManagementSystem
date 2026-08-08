"""Direct unit tests against app.permissions.Principal.

Qualification program Phase D, 2026-08-08: hand-crafted mutation testing against
permissions.py (the single module all tenancy/RBAC decisions flow through)
found two mutations the existing test suite did NOT catch, out of 7 tried:

- can_write_squadron's wing_admin branch, with the `and self.acting_squadron_id
  == squadron_id` clause removed (an IDOR-class mutation: a wing_admin in Proxy
  Mode for ANY squadron would be able to write to ANY squadron, not just the
  one they proxied into) -- SURVIVED.
- can_view_wing's wing-role branch, with `wing_id == self.wing_id` inverted to
  `!=` -- SURVIVED.

No dedicated unit-test file for permissions.py existed before this -- every
prior test exercised these checks only indirectly, through full HTTP-endpoint
tests, which happened not to isolate these two specific branches precisely
enough to fail when they broke. These tests construct Principal directly (no
HTTP, no DB) so they test the exact branch, nothing more.
"""
from app.permissions import Principal


def _principal(**overrides) -> Principal:
    base = dict(
        user_id="u1", role="wing_admin", wing_id="WING-A", squadron_id=None,
        national_id=None, proxy_session_id=None, proxy_mode=None,
        acting_wing_id=None, acting_squadron_id=None,
    )
    base.update(overrides)
    return Principal(**base)


def test_wing_admin_proxy_write_requires_matching_acting_squadron_id():
    """Regression for mutation-testing survivor M3 (2026-08-08). A wing_admin
    in Proxy Mode for squadron A must not be able to write to squadron B just
    because *some* proxy session is active -- acting_squadron_id must match
    the specific target squadron_id being written to."""
    p = _principal(
        role="wing_admin", proxy_session_id="ps1", proxy_mode="proxy",
        acting_squadron_id="SQN-A",
    )
    assert p.can_write_squadron("SQN-A", "WING-A") is True, (
        "wing_admin in Proxy Mode for SQN-A must be able to write to SQN-A"
    )
    assert p.can_write_squadron("SQN-B", "WING-A") is False, (
        "wing_admin in Proxy Mode for SQN-A must NOT be able to write to a "
        "different squadron (SQN-B) merely because some proxy session is "
        "active -- this is the exact IDOR-class bug mutation-tested and "
        "confirmed undetected before this test was added"
    )


def test_national_admin_intervention_write_requires_matching_acting_squadron_id():
    """Same IDOR-class check for the national_admin/system_admin Delegated
    Intervention path (the sibling branch to the wing_admin one above)."""
    p = _principal(
        role="national_admin", wing_id=None,
        proxy_session_id="ps1", proxy_mode="delegated_intervention",
        acting_squadron_id="SQN-A",
    )
    assert p.can_write_squadron("SQN-A", "WING-A") is True
    assert p.can_write_squadron("SQN-B", "WING-A") is False, (
        "Delegated Intervention into SQN-A must not grant write access to "
        "SQN-B"
    )


def test_sqn_admin_without_proxy_cannot_write_other_squadron():
    """Baseline (already covered indirectly elsewhere, restated here for a
    complete positive/negative pair in the same file as the mutation-tested
    branches)."""
    p = _principal(role="sqn_admin", wing_id="WING-A", squadron_id="SQN-A")
    assert p.can_write_squadron("SQN-A", "WING-A") is True
    assert p.can_write_squadron("SQN-B", "WING-A") is False


def test_can_view_wing_requires_matching_wing_id_for_wing_role():
    """Regression for mutation-testing survivor M7 (2026-08-08). A
    wing_viewer/wing_admin may view their OWN wing but not an arbitrary other
    wing -- can_view_wing's equality check must not be silently invertible
    without a test noticing."""
    p = _principal(role="wing_admin", wing_id="WING-A")
    assert p.can_view_wing("WING-A") is True, (
        "wing_admin must be able to view their own wing"
    )
    assert p.can_view_wing("WING-B") is False, (
        "wing_admin must NOT be able to view a different wing -- this is "
        "the exact inversion mutation-tested and confirmed undetected "
        "before this test was added"
    )


def test_can_view_wing_national_roles_can_view_any_wing():
    """National-level roles are the intentional bypass (matches
    can_view_squadron's equivalent national bypass, mutation M1, already
    covered) -- restated for can_view_wing specifically."""
    for role in ("national_viewer", "national_admin", "system_admin", "auditor"):
        p = _principal(role=role, wing_id=None)
        assert p.can_view_wing("ANY-WING") is True, f"{role} must be able to view any wing"


def test_can_view_wing_squadron_roles_cannot_view_any_wing():
    """sqn_admin/sqn_general have no wing-level view authority at all."""
    for role in ("sqn_admin", "sqn_general"):
        p = _principal(role=role, wing_id="WING-A", squadron_id="SQN-A")
        assert p.can_view_wing("WING-A") is False, (
            f"{role} has no wing-level view authority, even for their own wing"
        )
