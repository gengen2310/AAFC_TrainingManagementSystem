"""Self-tests for the architecture guard (stdlib unittest; no dependencies).

The router-to-router import check once used a raw-string regex with doubled
backslashes, so it matched a literal backslash and could never see a real
import: the guard reported "0 edges" while being unable to detect a new one.
These tests pin the detection itself, not just the current count.

Run: python -m unittest discover -s tools/architecture -p "test_*.py"
"""
import unittest

from guard import DIRECT_ROLE_RE, router_imports

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


if __name__ == "__main__":
    unittest.main()
