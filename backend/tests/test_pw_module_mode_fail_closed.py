"""The Planning Workspace's route split must fail CLOSED.

frontend/src/App.tsx serves two different route tables. In module mode it
serves /planning and a catch-all. Otherwise it serves twenty routes, eighteen
of which duplicate surfaces the connected-frontend owns -- /accounts, /admin,
/settings, /audit, /imports among them.

Which table a deployed container serves was decided entirely by a Railway
environment variable: docker-entrypoint.sh rewrote the meta tag only when
MODULE_MODE was exactly "true". An unset, misspelled, or cleared variable
therefore served the full duplicate admin surface -- a fail-OPEN default on
the single control separating the two frontends.

A deployed container now defaults to module mode. Serving the full route table
requires an explicit MODULE_MODE=false opt-out.

Local development and the e2e suite are unaffected: they run Vite directly and
never execute this entrypoint, so the meta tag stays empty and App.tsx serves
the full app exactly as before. That is what keeps frontend/e2e's 141 tests
meaningful.
"""
import pytest

from test_frontend_deploy_guard import _TARGETS, _run_entrypoint

PW = next(t for t in _TARGETS if t["name"] == "frontend")
GOOD_API = "https://aafc-tms-backend-production.up.railway.app"

MODULE_META = 'name="aafc-module-mode" content="true"'
FULL_APP_META = 'name="aafc-module-mode" content=""'


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
        "a deployed container with MODULE_MODE unset served the full 20-route "
        "app, exposing /accounts, /admin, /settings, /audit and /imports"
    )


@pytest.mark.parametrize("value", ["", "TRUE", "1", "yes", "moduel"])
def test_any_value_other_than_false_stays_in_module_mode(value):
    """Only an exact "false" opts out. Typos must not open the full app."""
    html = _html({"MODULE_MODE": value})
    assert MODULE_META in html, (
        f'MODULE_MODE={value!r} served the full route table; only "false" may'
    )


def test_explicit_true_is_module_mode():
    assert MODULE_META in _html({"MODULE_MODE": "true"})


def test_explicit_false_opts_into_the_full_app():
    """The opt-out must still work -- this is how a full-app deploy is chosen."""
    html = _html({"MODULE_MODE": "false"})
    assert FULL_APP_META in html, (
        "MODULE_MODE=false no longer opts into the full route table"
    )
