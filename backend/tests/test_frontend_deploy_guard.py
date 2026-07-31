"""Automated checks against the *actual* resolved production runtime artefact
for both frontends (connected-frontend/ and frontend/), not just source review.

Per the original defect brief: "A production build must fail closed if a
resolved API configuration contains: localhost; 127.0.0.1; backend-staging;
an unresolved placeholder; an empty API base. The guard must inspect the
actual resolved runtime configuration rather than legitimate development
comments or source text."

These tests execute the *real* connected-frontend/docker-entrypoint.sh and
frontend/docker-entrypoint.sh scripts (verbatim guard logic — only the two
hardcoded container filesystem paths are redirected into a temp directory so
the test doesn't need root/Docker) against a temp copy of the real
index.html + nginx.conf, with controlled environment variables, and asserts
on the actual resulting file content and the script's exit code — exactly
what a Railway deploy would see, not a reimplementation of the guard's rules.

Background: GAP-20 (docs/beta/qualification_gap_register.md) records the
production incident this class of guard exists to prevent (AAFC_API_BASE
misconfigured to point at the staging backend). GAP-11 records a separate,
still-open, *local-dev-only* documentation inconsistency — not a production
defect — see docs/beta/qualification_gap_register.md and
connected-frontend/RUN_TMS_CONNECTED_FRONTEND_MAC.sh.
"""
import os
import shutil
import subprocess
import tempfile

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_TARGETS = [
    {
        "name": "connected-frontend",
        "dir": os.path.join(REPO_ROOT, "connected-frontend"),
        "api_base_env": "AAFC_API_BASE",
    },
    {
        "name": "frontend",
        "dir": os.path.join(REPO_ROOT, "frontend"),
        "api_base_env": "VITE_API_BASE_URL",
    },
]


def _run_entrypoint(target: dict, env_overrides: dict) -> tuple[int, str, str, str]:
    """Run the real docker-entrypoint.sh for `target` against a sandboxed copy
    of its index.html/nginx.conf. Returns (exit_code, stdout, stderr,
    resolved_index_html_content)."""
    src_dir = target["dir"]
    entrypoint_src = os.path.join(src_dir, "docker-entrypoint.sh")
    index_src = os.path.join(src_dir, "index.html")
    nginx_src = os.path.join(src_dir, "nginx.conf")
    assert os.path.isfile(entrypoint_src), entrypoint_src
    assert os.path.isfile(index_src), index_src
    assert os.path.isfile(nginx_src), nginx_src

    with tempfile.TemporaryDirectory() as tmp:
        html_dir = os.path.join(tmp, "html")
        conf_dir = os.path.join(tmp, "conf")
        os.makedirs(html_dir)
        os.makedirs(conf_dir)
        html_path = os.path.join(html_dir, "index.html")
        conf_path = os.path.join(conf_dir, "default.conf")
        shutil.copy(index_src, html_path)
        shutil.copy(nginx_src, conf_path)

        entrypoint_content = open(entrypoint_src).read()
        # Redirect the two hardcoded container paths into the sandbox, and
        # replace the final `exec nginx ...` with a clean-success sentinel --
        # the guard logic above it (every sed/grep/if block) runs verbatim,
        # unmodified; only "then actually launch the web server" is skipped,
        # since that's not what this test is verifying.
        version_json_path = os.path.join(html_dir, "version.json")
        sandboxed = (
            entrypoint_content
            .replace("/usr/share/nginx/html/index.html", html_path)
            .replace("/usr/share/nginx/html/version.json", version_json_path)
            .replace("/etc/nginx/conf.d/default.conf", conf_path)
            .replace('exec nginx -g "daemon off;"', 'echo "[test] would exec nginx here"; exit 0')
            # Test-harness-only portability shim: the real script's bare `sed -i`
            # is correct for its actual runtime (Alpine/BusyBox sed in the real
            # container), but BSD sed on a macOS test host requires an explicit
            # (possibly empty) backup-extension argument. `-i.bak` is accepted
            # identically by BSD, GNU and BusyBox sed, so this does not change
            # which lines get matched/rewritten -- only makes the substitution
            # step itself portable enough to run outside the container. The
            # guard's actual decision logic (grep/if/exit below) is untouched.
            .replace('sed -i ', 'sed -i.bak ')
        )
        script_path = os.path.join(tmp, "entrypoint.sh")
        with open(script_path, "w") as f:
            f.write(sandboxed)
        os.chmod(script_path, 0o755)

        env = dict(os.environ)
        # Start from a clean slate -- the real Railway container never has
        # any of these set except what Railway itself injects.
        for k in ("AAFC_API_BASE", "VITE_API_BASE_URL", "AAFC_PW_BASE", "AAFC_TMS_BASE",
                  "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_GIT_COMMIT_SHA", "PORT", "MODULE_MODE"):
            env.pop(k, None)
        env.update(env_overrides)

        proc = subprocess.run(["sh", script_path], env=env, capture_output=True, text=True, timeout=30)
        resolved_html = open(html_path).read() if os.path.exists(html_path) else ""
        return proc.returncode, proc.stdout, proc.stderr, resolved_html


@pytest.mark.parametrize("target", _TARGETS, ids=lambda t: t["name"])
def test_production_deploy_with_correct_api_base_boots_cleanly(target):
    code, out, err, html = _run_entrypoint(target, {
        "RAILWAY_ENVIRONMENT_NAME": "production",
        target["api_base_env"]: "https://aafc-tms-backend-production.up.railway.app",
    })
    assert code == 0, f"stdout={out}\nstderr={err}"
    assert 'content="https://aafc-tms-backend-production.up.railway.app"' in html


@pytest.mark.parametrize("target", _TARGETS, ids=lambda t: t["name"])
@pytest.mark.parametrize("bad_value", [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://aafc-tms-backend-staging.up.railway.app",
])
def test_production_deploy_refuses_to_boot_with_forbidden_api_base(target, bad_value):
    code, out, err, html = _run_entrypoint(target, {
        "RAILWAY_ENVIRONMENT_NAME": "production",
        target["api_base_env"]: bad_value,
    })
    assert code != 0, f"guard should have refused to boot for {bad_value!r}, but exited 0. stdout={out}"
    assert "FATAL" in err


@pytest.mark.parametrize("target", _TARGETS, ids=lambda t: t["name"])
def test_production_deploy_refuses_to_boot_with_empty_api_base(target):
    """connected-frontend's checked-in default currently points at production
    (not empty), so this only reproduces the empty case if the operator
    genuinely never sets the env var *and* the checked-in default is ever
    changed to empty -- frontend/'s checked-in default already ships empty,
    so this is the live-today case for that target."""
    code, out, err, html = _run_entrypoint(target, {
        "RAILWAY_ENVIRONMENT_NAME": "production",
        # Deliberately do not set target["api_base_env"] at all.
    })
    if _current_api_base(html) != "":
        pytest.skip(f"{target['name']}'s checked-in default is non-empty; empty-API-base case not reproducible without editing source")
    assert code != 0, f"guard should have refused to boot with an empty API base. stdout={out}"
    assert "FATAL" in err


@pytest.mark.parametrize("target", _TARGETS, ids=lambda t: t["name"])
def test_production_deploy_refuses_to_boot_with_unresolved_placeholder(target):
    """Simulates a hypothetical future regression where the checked-in default
    is a "__"-style placeholder (matching this codebase's own __PORT__/
    __CSP_CONNECT_SRC__/__APP_BUILD__ convention) that never got substituted."""
    src_dir = target["dir"]
    index_src = os.path.join(src_dir, "index.html")
    with tempfile.TemporaryDirectory() as tmp:
        patched_index = os.path.join(tmp, "index.html")
        content = open(index_src).read()
        content = content.replace(
            f'<meta name="aafc-api-base" content="{_current_api_base(content)}">',
            '<meta name="aafc-api-base" content="__API_BASE__">',
        )
        with open(patched_index, "w") as f:
            f.write(content)
        # Reuse _run_entrypoint's machinery but against the patched index.
        patched_target = dict(target)
        patched_dir = os.path.join(tmp, "src")
        os.makedirs(patched_dir)
        shutil.copy(patched_index, os.path.join(patched_dir, "index.html"))
        shutil.copy(os.path.join(src_dir, "nginx.conf"), os.path.join(patched_dir, "nginx.conf"))
        shutil.copy(os.path.join(src_dir, "docker-entrypoint.sh"), os.path.join(patched_dir, "docker-entrypoint.sh"))
        patched_target["dir"] = patched_dir

        code, out, err, html = _run_entrypoint(patched_target, {
            "RAILWAY_ENVIRONMENT_NAME": "production",
            # No AAFC_API_BASE/VITE_API_BASE_URL set -- the placeholder is left as-is.
        })
    assert code != 0, f"guard should have refused to boot with an unresolved placeholder. stdout={out}"
    assert "FATAL" in err


def _current_api_base(html_content: str) -> str:
    import re
    m = re.search(r'<meta name="aafc-api-base" content="([^"]*)">', html_content)
    assert m, "aafc-api-base meta tag not found in index.html"
    return m.group(1)


@pytest.mark.parametrize("target", _TARGETS, ids=lambda t: t["name"])
def test_non_production_environment_is_not_guarded(target):
    """Staging/local dev must never be blocked by this guard -- it's
    production-only by design."""
    code, out, err, html = _run_entrypoint(target, {
        "RAILWAY_ENVIRONMENT_NAME": "staging",
        target["api_base_env"]: "http://localhost:8000",
    })
    assert code == 0, f"guard must not apply outside production. stdout={out}\nstderr={err}"
