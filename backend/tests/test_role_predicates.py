"""Named role predicates in permissions.py are exact replacements for the
inline role checks they replaced in the routers (truth table over all roles)."""
from types import SimpleNamespace

from app import permissions as P

ROLES = ["sqn_general", "sqn_admin", "wing_viewer", "wing_admin",
         "national_viewer", "national_admin", "system_admin", "auditor"]


def _p(role):
    return P.Principal(user_id="u", role=role, wing_id="w", squadron_id="s", national_id="n")


def test_is_wing_equals_the_old_wing_tuple():
    for r in ROLES:
        assert _p(r).is_wing == (r in ("wing_admin", "wing_viewer")), r


def test_is_national_equals_the_old_national_tuple():
    for r in ROLES:
        assert _p(r).is_national == (r in ("national_admin", "national_viewer", "system_admin", "auditor")), r


def test_national_admin_wing_writer_writer_and_read_only_sets():
    for r in ROLES:
        p = _p(r)
        assert P.is_national_admin(p) == (r in {"national_admin", "system_admin"}), r
        assert P.is_wing_writer(p) == (r in {"wing_admin", "national_admin", "system_admin"}), r
        assert P.is_writer(p) == (r in {"sqn_admin", "wing_admin", "national_admin", "system_admin"}), r
        assert P.is_read_only_role(p) == (r in ("sqn_general", "wing_viewer", "national_viewer", "auditor")), r


def test_is_squadron_equals_the_old_squadron_tuple():
    # Replaced 11 inline `p.role in ("sqn_admin", "sqn_general")` scope checks.
    for r in P.ROLES:
        assert _p(r).is_squadron == (r in ("sqn_admin", "sqn_general")), r
