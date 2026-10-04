"""permissions.wing_admin_outside_own_wing: the single statement of "a Wing
Admin acts only inside their own Wing", used by 14 Wing-scoped write checks
(each keeps its own error response)."""
import pytest

from app.permissions import Principal, wing_admin_outside_own_wing


def _p(role, wing="W7"):
    return Principal(user_id="u", role=role, squadron_id="S", wing_id=wing, national_id="N")


def test_wing_admin_inside_own_wing_is_not_outside():
    assert not wing_admin_outside_own_wing(_p("wing_admin"), "W7")


@pytest.mark.parametrize("target", ["W8", None, ""])
def test_wing_admin_with_any_other_or_missing_target_is_outside(target):
    assert wing_admin_outside_own_wing(_p("wing_admin"), target)


@pytest.mark.parametrize("role", ["sqn_general", "sqn_admin", "wing_viewer", "national_viewer",
                                  "national_admin", "auditor", "system_admin"])
def test_other_roles_are_not_constrained_by_this_predicate(role):
    assert not wing_admin_outside_own_wing(_p(role), "W8")


from app.permissions import sqn_admin_outside_own_squadron  # noqa: E402


def _s(role, sqn="S1"):
    return Principal(user_id="u", role=role, squadron_id=sqn, wing_id="W7", national_id="N")


def test_sqn_admin_inside_own_squadron_is_not_outside():
    assert not sqn_admin_outside_own_squadron(_s("sqn_admin"), "S1")


@pytest.mark.parametrize("target", ["S2", None, ""])
def test_sqn_admin_with_any_other_or_missing_target_is_outside(target):
    assert sqn_admin_outside_own_squadron(_s("sqn_admin"), target)


@pytest.mark.parametrize("role", ["sqn_general", "wing_viewer", "wing_admin", "national_viewer",
                                  "national_admin", "auditor", "system_admin"])
def test_other_roles_are_not_constrained_by_the_squadron_predicate(role):
    assert not sqn_admin_outside_own_squadron(_s(role), "S2")
