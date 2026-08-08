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
	- Push current branch to origin using non-destructive defaults.
	- Do not force-push unless explicitly requested.

6) Verification policy:
	- Re-check ahead/behind status after push.
	- Report final sync state and last commit hash.

7) Return strict result payload:
	{
	  "status": "success | partial_success | skipped | failed",
	  "branch": "string",
	  "upstream": "string|null",
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
```

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
