#!/usr/bin/env python3
"""Read-only verification that GitHub branch protection is configured on protected branches.

Confirms the *actual* GitHub-side guardrail (required PR, required status checks,
required reviews, no force-push, no direct pushes) exists for each branch listed in
GIT_PROTECTED_BRANCHES. This script never modifies protection settings; it only
reports drift so a repo admin can remediate. Requires the GitHub CLI (`gh`), the
promoted tool for GitHub-side operations.

Usage:
    python scripts/gitter/verify_branch_protection.py [--branch main] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_protected_branches() -> list[str]:
    """Read GIT_PROTECTED_BRANCHES from .env (fallback: main,master)."""
    env_path = PROJECT_ROOT / ".env"
    branches = "main,master"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("GIT_PROTECTED_BRANCHES="):
                branches = line.split("=", 1)[1].strip() or branches
                break
    literal = [b.strip() for b in branches.split(",") if b.strip() and "*" not in b]
    return literal or ["main"]


def gh_available() -> bool:
    return shutil.which("gh") is not None


def check_branch_protection(repo_slug: str, branch: str) -> dict:
    """Query branch protection via `gh api`. Returns a normalized status dict."""
    cmd = [
        "gh", "api",
        f"repos/{repo_slug}/branches/{branch}/protection",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {
            "branch": branch,
            "protected": False,
            "error": proc.stderr.strip()[:400] or "branch protection not configured or branch not found",
        }
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"branch": branch, "protected": False, "error": "unparseable gh api response"}

    required_pr = bool(data.get("required_pull_request_reviews"))
    required_checks = data.get("required_status_checks") or {}
    required_check_contexts = required_checks.get("contexts", []) or required_checks.get("checks", [])
    allow_force_pushes = bool((data.get("allow_force_pushes") or {}).get("enabled"))
    enforce_admins = bool((data.get("enforce_admins") or {}).get("enabled"))

    gaps = []
    if not required_pr:
        gaps.append("required_pull_request_reviews not enforced")
    if not required_check_contexts:
        gaps.append("no required status checks configured")
    if allow_force_pushes:
        gaps.append("force pushes are allowed (should be blocked)")
    if not enforce_admins:
        gaps.append("admins are exempt from protection (should be enforced)")

    return {
        "branch": branch,
        "protected": not gaps,
        "required_pull_request_reviews": required_pr,
        "required_status_checks": required_check_contexts,
        "allow_force_pushes": allow_force_pushes,
        "enforce_admins": enforce_admins,
        "gaps": gaps,
    }


def resolve_repo_slug() -> str | None:
    proc = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)["nameWithOwner"]
    except (json.JSONDecodeError, KeyError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", action="append", help="Branch to check (repeatable). Defaults to GIT_PROTECTED_BRANCHES.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output only.")
    args = parser.parse_args()

    if not gh_available():
        print("ERROR: GitHub CLI (`gh`) is not installed or not on PATH. Install it: https://cli.github.com/", file=sys.stderr)
        return 2

    branches = args.branch or load_protected_branches()
    repo_slug = os.environ.get("GH_REPO") or resolve_repo_slug()
    if not repo_slug:
        print("ERROR: Could not resolve repository (run inside a `gh`-authenticated git repo, or set GH_REPO=owner/repo).", file=sys.stderr)
        return 2

    results = [check_branch_protection(repo_slug, b) for b in branches]
    all_protected = all(r["protected"] for r in results)

    if args.json:
        print(json.dumps({"repository": repo_slug, "branches": results, "all_protected": all_protected}, indent=2))
    else:
        print(f"Branch protection verification for {repo_slug}\n")
        for r in results:
            status = "OK" if r["protected"] else "GAP"
            print(f"[{status}] {r['branch']}")
            for gap in r.get("gaps", []):
                print(f"    - {gap}")
            if r.get("error"):
                print(f"    - {r['error']}")
        print()
        print("Result: all protected branches enforce required guardrails." if all_protected
              else "Result: one or more protected branches are missing required guardrails. Remediate in GitHub repo settings before relying on this as the merge gate.")

    return 0 if all_protected else 1


if __name__ == "__main__":
    sys.exit(main())
