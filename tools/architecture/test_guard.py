"""Self-tests for the architecture guard (stdlib unittest; no dependencies).

The router-to-router import check once used a raw-string regex with doubled
backslashes, so it matched a literal backslash and could never see a real
import: the guard reported "0 edges" while being unable to detect a new one.
These tests pin the detection itself, not just the current count.

Run: python -m unittest discover -s tools/architecture -p "test_*.py"
"""
import unittest

from guard import DIRECT_ROLE_RE, inline_scope_comparisons, router_imports

NAMES = {"training", "planning", "dashboard", "timing", "accounts", "auth"}


class RouterImportDetection(unittest.TestCase):
    def deps(self, text, me="dashboard"):
        return router_imports(text, NAMES, me)

    def test_relative_sibling_import(self):
        self.assertEqual(self.deps("from .training import router\n"), {"training"})

    def test_function_local_indented_import(self):
        self.assertEqual(self.deps("def f():\n    from .planning import x\n"), {"planning"})

    def test_package_qualified_import(self):
        self.assertEqual(self.deps("from ..routers.timing import a, b\n"), {"timing"})

    def test_from_package_import_module_names(self):
        self.assertEqual(self.deps("from . import training, accounts\n"), {"training", "accounts"})
        self.assertEqual(self.deps("from ..routers import auth as a\n"), {"auth"})

    def test_absolute_import(self):
        self.assertEqual(self.deps("from app.routers.training import x\n"), {"training"})
        self.assertEqual(self.deps("import app.routers.planning\n"), {"planning"})

    def test_non_router_modules_and_self_are_ignored(self):
        text = "from ..permissions import p\nfrom ..services_timing import t\nfrom .dashboard import d\n"
        self.assertEqual(self.deps(text), set())

    def test_mentions_in_strings_or_comments_are_not_imports(self):
        self.assertEqual(self.deps('x = "from .training import y"  # from .planning import z\n'), set())


class RoleCheckDetection(unittest.TestCase):
    def test_counts_each_direct_role_comparison_form(self):
        text = "p.role == 'a'\np.role != 'b'\np.role in X\np.role not in Y\nrole = p.role\n"
        self.assertEqual(len(DIRECT_ROLE_RE.findall(text)), 4)



class InlineScopeComparisonDetection(unittest.TestCase):
    def test_counts_comparisons_against_the_principals_own_or_acting_scope(self):
        text = (
            "q.filter(Squadron.wing_id == p.wing_id)\n"
            "x = [s for s in sqns if s.id == p.squadron_id]\n"
            "if p.wing_id != wing_id: pass\n"
            "if squadron_id != p.acting_squadron_id: pass\n"
            "ok = a.wing_id == p.acting_wing_id\n"
        )
        self.assertEqual(inline_scope_comparisons(text), 5)

    def test_ignores_non_comparisons_other_names_and_strings(self):
        text = (
            "level_scope_clause(p, wing_column=AuditLog.wing_id)\n"
            "wing_id = p.acting_wing_id or p.wing_id\n"
            "require_can_write_squadron(p, sqn_id, p.wing_id)\n"
            "if principal.wing_id == w: pass\n"
            "if p.role == 'x': pass\n"
            "s = 'Squadron.wing_id == p.wing_id'  # q.filter(X.wing_id == p.wing_id)\n"
        )
        self.assertEqual(inline_scope_comparisons(text), 0)

    def test_chained_and_membership_forms(self):
        self.assertEqual(inline_scope_comparisons("a == p.wing_id == b\n"), 1)
        self.assertEqual(inline_scope_comparisons("x in (p.wing_id,)\n"), 0)


if __name__ == "__main__":
    unittest.main()
