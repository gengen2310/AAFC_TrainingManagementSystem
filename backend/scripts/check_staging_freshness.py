"""Check whether a deployed backend build already includes the latest commit
on a branch that touches backend/.

REM-112: nothing in this project's normal workflow guarantees a service gets
redeployed promptly after a merge to main touches backend/ -- REM-111 found a
merged endpoint 404ing on staging for ~24h because nothing had redeployed,
caught only because a regression test happened to exercise that exact route.
This gives an explicit check instead. Relies on GET /api/health/ready's
`commit` field (RAILWAY_GIT_COMMIT_SHA, injected by Railway at runtime; see
backend/app/routers/health.py).

Deliberately does not import requests/SQLAlchemy — only the standard library,
so it runs in a bare CI container or a quick local pre-deploy check with
nothing extra installed.

Usage:
    python backend/scripts/check_staging_freshness.py <health-url> [--ref main]

Example:
    python backend/scripts/check_staging_freshness.py \\
        https://aafc-tms-backend-staging.up.railway.app/api/health/ready
"""
import argparse
import json
import subprocess
import sys
import urllib.request

# Paths that constitute a real backend behaviour change -- deliberately
# excludes tests/ and docs so a docs-only or test-only commit doesn't get
# treated as something staging must be redeployed for.
_BACKEND_PATHS = ["backend/app", "backend/alembic", "backend/requirements.txt", "backend/Dockerfile"]


class FreshnessCheckError(Exception):
    pass


def fetch_deployed_commit(health_url: str, timeout: float = 15) -> str:
    """GET the health endpoint and return its `commit` field."""
    try:
        with urllib.request.urlopen(health_url, timeout=timeout) as resp:  # noqa: S310 (operator-supplied URL, not user input)
            data = json.loads(resp.read())
    except Exception as e:
        raise FreshnessCheckError(f"could not reach {health_url}: {e}") from e
    commit = data.get("commit")
    if not commit:
        raise FreshnessCheckError(f"{health_url} response has no 'commit' field: {data}")
    return commit


def latest_backend_commit(repo_dir: str, ref: str) -> str:
    """The most recent commit on `ref` that touches a real backend path."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", ref, "--", *_BACKEND_PATHS],
        cwd=repo_dir, capture_output=True, text=True, check=True,
    )
    commit = result.stdout.strip()
    if not commit:
        raise FreshnessCheckError(f"no commits touching backend/ found on {ref}")
    return commit


def is_fresh(deployed_commit: str, latest_commit: str, repo_dir: str) -> bool:
    """True if `latest_commit` is an ancestor of (or equal to) `deployed_commit`
    -- i.e. the deployed build already contains the latest backend change."""
    if deployed_commit == latest_commit:
        return True
    if deployed_commit == "local":
        # Not a real Railway deployment -- can't check ancestry meaningfully.
        raise FreshnessCheckError("deployed commit is 'local' (RAILWAY_GIT_COMMIT_SHA unset) -- not a real deployment, cannot check freshness")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", latest_commit, deployed_commit],
        cwd=repo_dir,
    )
    if result.returncode not in (0, 1):
        raise FreshnessCheckError(
            f"'git merge-base --is-ancestor {latest_commit} {deployed_commit}' failed unexpectedly "
            f"(exit {result.returncode}) -- is {deployed_commit!r} a commit this repo actually knows about?"
        )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("health_url", help="e.g. https://aafc-tms-backend-staging.up.railway.app/api/health/ready")
    parser.add_argument("--repo-dir", default=".", help="path to the git repo (default: current directory)")
    parser.add_argument("--ref", default="main", help="branch to compare against (default: main)")
    args = parser.parse_args()

    try:
        deployed = fetch_deployed_commit(args.health_url)
        latest = latest_backend_commit(args.repo_dir, args.ref)
        fresh = is_fresh(deployed, latest, args.repo_dir)
    except FreshnessCheckError as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(2)

    if fresh:
        print(f"FRESH: deployed commit {deployed[:8]} already includes the latest backend/ change on {args.ref} ({latest[:8]}).")
        sys.exit(0)
    print(
        f"STALE: deployed commit {deployed[:8]} does NOT include the latest backend/ change on "
        f"{args.ref} ({latest[:8]}). Redeploy backend/ to this environment.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
