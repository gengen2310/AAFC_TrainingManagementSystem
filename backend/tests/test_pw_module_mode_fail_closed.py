"""The Planning Workspace is MODULE-ONLY by architecture.

frontend/src/App.tsx no longer has a MODULE_MODE switch. It always renders
ModuleEntry: a single /planning route with a catch-all redirect and a
NotAuthenticated guard. There is no full-app route table, no AppShell,
and no nav. The fail-closed guarantee is structural — there is no runtime
flag that can expose a duplicate admin surface.

The docker-entrypoint.sh for the frontend service still writes the
aafc-module-mode meta tag (retained for backwards compatibility), but
App.tsx no longer reads it. These tests verify that the entrypoint's
default behaviour (module mode on) is preserved, which is belt-and-
suspenders in case someone adds the meta-tag read back.
"""
import pytest

from test_frontend_deploy_guard import _TARGETS, _run_entrypoint

PW = next(t for t in _TARGETS if t["name"] == "frontend")
GOOD_API = "https://aafc-tms-backend-production.up.railway.app"

MODULE_META = 'name="aafc-module-mode" content="true"'


def _html(env_overrides):
    env = {"RAILWAY_ENVIRONMENT_NAME": "production", PW["api_base_env"]: GOOD_API}
    env.update(env_overrides)
    code, out, err, html = _run_entrypoint(PW, env)
    assert code == 0, f"entrypoint exited {code}\nstdout={out}\nstderr={err}"
    return html


def test_unset_module_mode_defaults_to_module_mode():
    """The dangerous case: nobody set the variable at all."""
    html = _html({})
    assert MODULE_META in html, (
        "a deployed container with MODULE_MODE unset did not write module-mode meta tag"
    )


@pytest.mark.parametrize("value", ["", "TRUE", "1", "yes", "moduel"])
def test_any_value_other_than_false_stays_in_module_mode(value):
    """Only an exact 'false' opts out of the meta tag. Typos must not change it."""
    html = _html({"MODULE_MODE": value})
    assert MODULE_META in html, (
        f'MODULE_MODE={value!r} did not write module-mode meta tag'
    )


def test_explicit_true_is_module_mode():
    assert MODULE_META in _html({"MODULE_MODE": "true"})
