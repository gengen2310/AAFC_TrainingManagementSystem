"""Tests for scripts/check_staging_freshness.py -- REM-112's staging-lag
detector (see the script's own module docstring for the incident this
replaces: a merged endpoint 404ing on staging for ~24h because nothing
redeployed it, caught only by luck)."""
import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from scripts.check_staging_freshness import (
    FreshnessCheckError,
    fetch_deployed_commit,
    is_fresh,
    latest_backend_commit,
)


def _git(repo_dir, *args):
    subprocess.run(["git", *args], cwd=repo_dir, check=True, capture_output=True)


def _init_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    return repo


def _commit(repo, path_rel: str, content: str, message: str) -> str:
    p = repo / path_rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", path_rel)
    _git(repo, "commit", "-q", "-m", message)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


# ── fetch_deployed_commit ────────────────────────────────────────────────────

def test_fetch_deployed_commit_returns_commit_field():
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps({"status": "ready", "commit": "abc1234"}).encode()
    fake_resp.__enter__.return_value = fake_resp
    with patch("scripts.check_staging_freshness.urllib.request.urlopen", return_value=fake_resp):
        assert fetch_deployed_commit("https://example.test/api/health/ready") == "abc1234"


def test_fetch_deployed_commit_raises_on_missing_commit_field():
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps({"status": "ready"}).encode()
    fake_resp.__enter__.return_value = fake_resp
    with patch("scripts.check_staging_freshness.urllib.request.urlopen", return_value=fake_resp):
        with pytest.raises(FreshnessCheckError, match="no 'commit' field"):
            fetch_deployed_commit("https://example.test/api/health/ready")


def test_fetch_deployed_commit_raises_on_unreachable_host():
    with patch("scripts.check_staging_freshness.urllib.request.urlopen", side_effect=OSError("connection refused")):
        with pytest.raises(FreshnessCheckError, match="could not reach"):
            fetch_deployed_commit("https://example.test/api/health/ready")


# ── latest_backend_commit ────────────────────────────────────────────────────

def test_latest_backend_commit_finds_the_right_commit(tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, "README.md", "hello", "docs: initial")
    backend_commit = _commit(repo, "backend/app/main.py", "app = 1", "feat: add app")
    _commit(repo, "README.md", "updated", "docs: unrelated later change")
    assert latest_backend_commit(str(repo), "main") == backend_commit


def test_latest_backend_commit_ignores_docs_and_tests(tmp_path):
    """A docs-only or tests-only change must not count as a 'real' backend
    change requiring redeploy -- matches the instruction's own point 4
    distinguishing docs-only intervening commits from real code changes."""
    repo = _init_repo(tmp_path)
    backend_commit = _commit(repo, "backend/app/main.py", "app = 1", "feat: add app")
    _commit(repo, "backend/tests/test_x.py", "def test_x(): pass", "test: add coverage")
    _commit(repo, "docs/beta/00_release_state.md", "notes", "docs: update")
    assert latest_backend_commit(str(repo), "main") == backend_commit


def test_latest_backend_commit_raises_when_none_found(tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, "README.md", "hello", "docs: initial")
    with pytest.raises(FreshnessCheckError, match="no commits touching backend/"):
        latest_backend_commit(str(repo), "main")


# ── is_fresh ──────────────────────────────────────────────────────────────────

def test_is_fresh_true_when_deployed_commit_is_exactly_latest(tmp_path):
    repo = _init_repo(tmp_path)
    c1 = _commit(repo, "backend/app/main.py", "app = 1", "feat: add app")
    assert is_fresh(c1, c1, str(repo)) is True


def test_is_fresh_true_when_deployed_commit_is_a_later_descendant(tmp_path):
    """Deployed HEAD is newer than the latest backend/-touching commit --
    still fresh, since it necessarily includes it."""
    repo = _init_repo(tmp_path)
    c1 = _commit(repo, "backend/app/main.py", "app = 1", "feat: add app")
    c2 = _commit(repo, "README.md", "docs update", "docs: unrelated")
    assert is_fresh(c2, c1, str(repo)) is True


def test_is_fresh_false_when_deployed_commit_predates_latest(tmp_path):
    """The exact REM-111/112 scenario: staging is running an old commit that
    predates a real backend/ change on main."""
    repo = _init_repo(tmp_path)
    c1 = _commit(repo, "backend/app/main.py", "app = 1", "feat: add app")
    c2 = _commit(repo, "backend/app/main.py", "app = 2", "fix: add missing endpoint")
    assert is_fresh(c1, c2, str(repo)) is False


def test_is_fresh_raises_for_local_placeholder_commit(tmp_path):
    repo = _init_repo(tmp_path)
    c1 = _commit(repo, "backend/app/main.py", "app = 1", "feat: add app")
    with pytest.raises(FreshnessCheckError, match="not a real deployment"):
        is_fresh("local", c1, str(repo))
