---
name: "Pull Request Workflow"
description: "Land changes on a protected branch (main/master/release) via a feature branch and Pull Request, gated on required CI checks and reviewer approval."
agent: "Gitter"
---

# Gitter Prompt: Pull Request Workflow (Protected Branch Landing)

Use this prompt with the Gitter agent whenever a change must reach a protected branch
(`main`, `master`, `release/*`, or any pattern configured in `GIT_PROTECTED_BRANCHES`).
Direct commits/pushes to protected branches are never permitted — this prompt is the only
sanctioned path onto them, and it relies on the `gh` CLI (promoted tool) rather than raw
GitHub API scripting.

Reuse-first policy:
- Use the `gh` CLI for all GitHub-side operations (PR create/status/merge). Do not write
  custom scripts against the GitHub REST/GraphQL API for this workflow.
- Prefer the existing `gitter-repository-sync` prompt for the local commit/push mechanics
  on the feature branch; this prompt adds the PR + guardrail layer on top.

## Prerequisites

- **GitHub CLI (`gh`)** installed. Install: `winget install --id GitHub.cli` (Windows),
  `brew install gh` (macOS/Linux), or https://cli.github.com/. See
  [gitter-credentials/SKILL.md](../skills/gitter-credentials/SKILL.md#prerequisites) for
  the full requirement table.
- **`GITHUB_PR_TOKEN`** set in `.env` — a least-privilege fine-grained PAT scoped to
  `Contents: Read/write` + `Pull requests: Read/write` on this repo only. This token is
  exported as `GH_TOKEN` for the duration of each `gh` invocation in this prompt; it is
  never persisted via `gh auth login`, and it is distinct from `GITHUB_TOKEN` (which is
  reserved for administrative/one-off operations such as branch protection setup — do not
  use it here).
- Without `gh` or without `GITHUB_PR_TOKEN`, this prompt stops at Step 1 and reports
  `gh_cli_unavailable` / `gh_token_missing` — it does not fall back to raw API calls or to
  `GITHUB_TOKEN`.

```text
@Gitter, land my changes on <protected-branch> using the Pull Request workflow.

STRICT EXECUTION POLICY:

1) Preconditions:
	- Confirm `gh` CLI is installed (`gh --version`). If missing, STOP and report
	  remediation steps; do not fall back to raw API calls.
	- Load `GITHUB_PR_TOKEN` from `.env` and export it as `GH_TOKEN` for this session only
	  (e.g. `$env:GH_TOKEN = <value>` / `export GH_TOKEN=<value>`). If empty, STOP and report
	  failure_reason="gh_token_missing"; do not substitute `GITHUB_TOKEN`.
	- Confirm `gh auth status` succeeds using the exported `GH_TOKEN`.
	- Confirm the target branch (e.g. `main`) is in the protected branch list. If the
	  target is NOT protected, tell the user this prompt is unnecessary and defer to
	  `gitter-repository-sync`.

2) Feature branch:
	- If currently on a protected branch, create a new feature branch from the latest
	  remote state of the target branch. Use a descriptive name:
	  `<type>/<short-scope>-<summary>` (e.g. `feat/gitter-pr-workflow`).
	- If already on a non-protected feature branch with the intended changes, reuse it.

3) Commit & push (delegates to sync mechanics):
	- Stage only relevant changes; report exact files staged.
	- Commit using Conventional Commits: `<type>(<scope>): <summary>`.
	- Push the feature branch to origin (never the protected branch itself).

4) Open the Pull Request:
	- `gh pr create --base <protected-branch> --head <feature-branch> --title "..." --body "..."`
	- Body must summarize the change intent and link any relevant issue/incident.
	- Do not set `--draft` unless the user asks for a draft PR.

5) Guardrail verification (block merge until satisfied):
	- Poll `gh pr checks <pr-number>` until all required status checks report success or
	  failure. Do not proceed to merge while checks are pending.
	- Poll `gh pr view <pr-number> --json reviewDecision` for required review approval.
	- If any required check fails, STOP and report status=failed with the failing check
	  names; do not attempt to merge or bypass.

6) Merge (human-confirmed only):
	- Only after checks=success AND reviewDecision=APPROVED, present the merge option to
	  the user and require explicit confirmation before running
	  `gh pr merge <pr-number> --squash` (or the method the user prefers).
	- NEVER use `--admin` to bypass required checks/reviews.
	- NEVER auto-merge without an explicit human "yes" for this specific merge.

7) Return strict result payload:
	{
	  "status": "success | pending_checks | pending_review | blocked | failed",
	  "target_branch": "string",
	  "feature_branch": "string",
	  "pr_number": "number|null",
	  "pr_url": "string|null",
	  "checks": {
		 "required_total": 0,
		 "passed": 0,
		 "failed": 0,
		 "pending": 0
	  },
	  "review_decision": "APPROVED | REVIEW_REQUIRED | CHANGES_REQUESTED | null",
	  "merged": false,
	  "failure_reason": "string|null",
	  "next_action": "string|null"
	}

DECISION RULES:
- If `gh` is not installed/authenticated: status=failed, failure_reason="gh_cli_unavailable".
- If checks are still running: status=pending_checks, next_action="poll again / wait for CI".
- If checks passed but review missing: status=pending_review, next_action="request review".
- If any required check failed: status=blocked, failure_reason lists failing check names,
  next_action="fix and push additional commits to the same feature branch".
- Only return status=success after an explicit, human-confirmed merge succeeds.
```

## Why this exists

Agent instructions alone cannot prevent a direct `git push origin main` run outside of
Gitter. The actual enforcement is GitHub branch protection on the target branch (required
PR, required status checks, required reviews, no force-push, no direct pushes — including
for admins). This prompt assumes that protection is configured and focuses on guiding
contributors through the compliant path plus verifying the CI/review gate before advising
a merge. Use `scripts/gitter/verify_branch_protection.py` periodically to confirm the
GitHub-side protection has not drifted.

## Usage Example

```text
@Gitter, land my changes on main using the Pull Request workflow.
```

## Troubleshooting

1. `gh auth status` fails:
- Cause: `GH_TOKEN` not exported from `GITHUB_PR_TOKEN`, or the token lacks required scopes.
- Action: confirm `GITHUB_PR_TOKEN` is set in `.env` with `Contents: Read/write` +
  `Pull requests: Read/write` on this repo; re-export and retry. Do not fall back to
  `GITHUB_TOKEN` or raw API calls.

2. Required check missing from `gh pr checks` output:
- Cause: branch protection required-checks list doesn't match the workflow job name.
- Action: verify [python-tests.yml](../workflows/python-tests.yml) job name matches the
  required check configured in branch protection settings.

3. `gh pr merge` rejected:
- Cause: checks pending/failed, or missing approvals, or branch protection blocks it.
- Action: report the specific blocking reason from `gh pr view`; do not retry with
  `--admin` or force flags.

4. Target branch is not actually protected on GitHub:
- Cause: branch protection ruleset was never configured or was removed.
- Action: flag this as a critical gap; recommend enabling protection before continuing to
  rely on this workflow as the sole guardrail.
