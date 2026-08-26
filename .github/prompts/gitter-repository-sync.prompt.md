---
name: "Local Repo Sync"
description: "Synchronize a local Git branch with its remote using safe validation gates, conventional commits, and strict status reporting."
agent: "Gitter"
---

# Gitter Prompt: Local Repository Synchronization (Strict)

Use this prompt with the Gitter agent to synchronize local repository state with the remote branch while preserving auditability and minimizing risk.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@Gitter, synchronize my local branch with remote using strict validation and reporting.

STRICT EXECUTION POLICY:

1) Validate repository context first:
	- Confirm current branch name.
	- Confirm upstream tracking branch exists.
	- Fetch remote state before making decisions.
	- Load `GIT_PROTECTED_BRANCHES` from `.env` (default: `main,master`). If the current branch matches any protected pattern, apply Protected Branch Routing (Step 1a) before staging/committing. Never push directly to a protected branch under any circumstance.

1a) Protected Branch Routing (only when current branch is protected):
	- If there are no local changes to sync (clean tree, nothing staged/unstaged), skip routing — just report sync status for the protected branch as-is; there is nothing to route.
	- Otherwise, auto-route: create and check out a new feature branch from the up-to-date protected branch using the pattern `sync/<yyyyMMddHHmm>-<short-desc>` (derive `<short-desc>` from the change intent if known, else `local-changes`). Report the exact branch name created.
	- Continue Steps 2-6 on this feature branch. Do not touch the protected branch's working state further.
	- After push (Step 5), do NOT attempt to open or merge a PR here — that is out of scope for this prompt by design. Report `next_action` naming the exact feature branch and target so the user (or agent) can immediately invoke the `Gitter: Pull Request Workflow` prompt to finish the job (PR create -> checks -> review -> merge).

2) Inspect working tree and index:
	- List unstaged, staged, and untracked files.
	- If there are merge conflicts, STOP and return failed status.
	- Do not discard or overwrite local changes.

3) Stage policy:
	- Stage only relevant user changes for synchronization.
	- Exclude temporary/generated artifacts unless explicitly requested.
	- Report exact files staged.

4) Commit policy:
	- If staged changes exist, create one commit using Conventional Commits:
	  <type>(<scope>): <summary>
	- Keep message specific and traceable to the change intent.
	- If no staged changes exist, do not create an empty commit.

5) Push policy:
	- If routing was applied in Step 1a, push the feature branch (never the protected branch itself) using non-destructive defaults.
	- Otherwise push current branch to origin using non-destructive defaults.
	- Do not force-push unless explicitly requested.

6) Verification policy:
	- Re-check ahead/behind status after push.
	- Report final sync state and last commit hash.

7) Return strict result payload:
	{
	  "status": "success | partial_success | skipped | failed | routed",
	  "branch": "string",
	  "upstream": "string|null",
	  "protected_branch": true,
	  "routed": {
		 "applied": true,
		 "from_branch": "string|null",
		 "feature_branch": "string|null"
	  },
	  "changes_detected": true,
	  "files_staged": ["..."],
	  "commit_created": true,
	  "commit": {
		 "hash": "string|null",
		 "message": "string|null"
	  },
	  "push": {
		 "attempted": true,
		 "succeeded": true
	  },
	  "sync_state": {
		 "ahead": 0,
		 "behind": 0
	  },
	  "failure_reason": "string|null",
	  "next_action": "string|null"
	}

DECISION RULES:
- If no local changes and branch is not behind remote, return status=skipped with "already in sync".
- If push succeeds but branch remains behind, return status=partial_success and recommend pull/rebase.
- If validation fails (no repo, no upstream, conflicts), return status=failed with explicit remediation.
- If current branch is protected and changes exist, apply Step 1a routing, and on successful push return status=routed with `routed.feature_branch` populated and next_action="Run: @Gitter, land my changes on <target-branch> using the Pull Request workflow (feature branch <feature_branch> already pushed)".
- If current branch is protected and the tree is clean, return status=skipped with "already in sync" (no routing needed) — never fabricate a feature branch when there is nothing to sync.
```

## Protected Branch Routing

This prompt never pushes directly to a protected branch (`main`, `master`, `release/*`, or any pattern in `GIT_PROTECTED_BRANCHES`). When changes exist on a protected branch, this prompt automatically routes them onto a new feature branch (Step 1a) — creating, committing, and pushing there — using the same naming/commit conventions as any other sync. It stops short of opening a Pull Request: that step belongs to the `Gitter: Pull Request Workflow` prompt, which takes the already-pushed feature branch, runs `gh pr create`, and gates the eventual merge on required checks and reviews. This division keeps local sync mechanics (this prompt) separate from GitHub-side PR lifecycle (the other prompt), per the reuse-first policy — no duplicated `gh` logic here.

The authoritative guardrail remains GitHub branch protection on the remote (required PR, required status checks, required reviews, no force-push); this prompt's routing is a safe-by-default courtesy that also produces the exact next command to run.

## Recommended Commit Type Guide

- feat: new behavior or capability
- fix: bug fix or behavior correction
- docs: documentation-only changes
- refactor: non-functional internal change
- test: test additions/updates
- chore: maintenance tasks

## Usage Example

```text
@Gitter, synchronize my local branch with remote using strict validation and reporting.
```

## Troubleshooting

1. Push rejected (non-fast-forward):
- Cause: remote has new commits.
- Action: fetch and rebase (or merge), resolve conflicts, then push.

2. No upstream branch configured:
- Cause: current branch does not track remote.
- Action: set upstream to origin/<branch> and retry.

3. Merge conflicts detected:
- Cause: unresolved conflict markers in working tree.
- Action: resolve conflicts first; do not auto-commit conflicted state.

4. No changes to commit:
- Cause: working tree clean or no relevant staged files.
- Action: return skipped with current sync status.

5. Current branch is protected (`main`/`master`/`release/*`) with local changes:
- Cause: policy forbids syncing changes directly onto a protected branch.
- Action: this prompt auto-routes onto a new feature branch (Step 1a), pushes it, and reports the exact feature branch name plus the follow-up command for the `Gitter: Pull Request Workflow` prompt. No manual branch creation needed.

6. Current branch is protected with a clean tree (nothing to sync):
- Cause: user ran this prompt on a protected branch just to check sync status.
- Action: report status=skipped with current ahead/behind state; no routing is performed since there is nothing to route.
