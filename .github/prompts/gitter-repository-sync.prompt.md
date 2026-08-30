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
	- After push (Step 5) succeeds, automatically chain into the `Gitter: Pull Request Workflow` prompt for this feature branch, targeting the protected branch it was routed from — no manual re-invocation required. The chained run executes PR create -> checks polling -> review polling and STOPS at the existing human-confirmation gate before merge (Step 6 of that prompt is untouched: merge is never automatic). Populate `chained_pr_workflow` with the outcome of that run. If the chained invocation cannot start (e.g. `gh` missing, `GITHUB_PR_TOKEN` missing), do not fail the sync itself — the feature branch is already safely pushed — instead report the PR-workflow precondition failure inside `chained_pr_workflow` and set `next_action` to the manual fallback command.

1b) Existing PR Check (only when current branch is NOT protected, i.e. Step 1a did not trigger):
	- Run `gh pr view --json number,state,url,baseRefName` for the current branch (gh infers HEAD's branch; no argument needed). Treat a "no pull requests found" error, or `gh` being unavailable, as "no PR" — proceed straight to Step 2 as a normal pre-PR feature branch.
	- If a PR is found with state=OPEN: **reuse this branch — do not create a new branch or a second PR.** Continue directly to Steps 2-6 on the current branch; the push adds commits to the existing PR. Populate `existing_pr` in the result payload. This is the one-PR-in-flight rule: stacking a new branch on top of an unmerged PR would require rebase+force-push later, which is against policy.
	- If a PR is found with state=MERGED (landed outside this session, e.g. merged by a reviewer without Gitter's own post-merge cleanup running): perform cleanup before anything else —
		a. `git switch <baseRefName>` (the PR's base, typically `main`).
		b. `git pull origin <baseRefName>` to bring in the merged commit(s).
		c. `git branch -d <old-branch>` (safe delete only — never `-D`; refuses if unmerged, which should not happen since state=MERGED).
		d. If the remote branch still exists, `git push origin --delete <old-branch>` (skip with a note if it is already gone, e.g. removed by `gh pr merge --delete-branch`).
		Populate `post_pr_cleanup` in the result payload. If new changes are still pending after cleanup, re-apply Step 1a's routing (including its chained PR-workflow invocation) to create a fresh `sync/<yyyyMMddHHmm>-<short-desc>` branch from the now-updated base and continue there. If there is nothing new to sync, return status=skipped ("previous PR merged and cleaned up; nothing new to sync").
	- If a PR is found with state=CLOSED (and not merged): STOP — return status=blocked. Do not unilaterally decide whether to reuse or abandon this branch; report `next_action` asking the user to choose between reopening/reusing the branch or abandoning it and starting fresh from the base branch.

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
	  "status": "success | partial_success | skipped | failed | routed | blocked",
	  "branch": "string",
	  "upstream": "string|null",
	  "protected_branch": true,
	  "routed": {
		 "applied": true,
		 "from_branch": "string|null",
		 "feature_branch": "string|null"
	  },
	  "chained_pr_workflow": {
		 "invoked": false,
		 "target_branch": "string|null",
		 "status": "success | pending_checks | pending_review | blocked | failed | not_invoked | null",
		 "pr_number": null,
		 "pr_url": null
	  },
	  "existing_pr": {
		 "number": null,
		 "state": "OPEN|MERGED|CLOSED|null",
		 "url": null
	  },
	  "post_pr_cleanup": {
		 "applied": false,
		 "old_branch": null,
		 "base_branch": null,
		 "local_deleted": false,
		 "remote_deleted": false
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
- If current branch is protected and changes exist, apply Step 1a routing, and on successful push automatically chain into the Pull Request workflow for `routed.feature_branch` -> the protected branch it came from; return status=routed with `routed.feature_branch` and `chained_pr_workflow` populated. Only set `next_action` to the manual fallback command ("Run: @Gitter, land my changes on <target-branch> using the Pull Request workflow (feature branch <feature_branch> already pushed)") if the chained invocation itself could not start (`gh`/token unavailable); if it started, `next_action` should reflect whatever the chained PR workflow's own next_action is (e.g. "poll again", "request review", or nothing if it is now pending_review/pending_checks with no action needed from the user yet).
- If current branch is protected and the tree is clean, return status=skipped with "already in sync" (no routing needed) — never fabricate a feature branch when there is nothing to sync.
- If current branch is non-protected with an OPEN PR, reuse the branch (no new branch/PR); populate `existing_pr` and proceed with normal success/partial_success reporting.
- If current branch is non-protected with a MERGED PR, apply Step 1b cleanup, populate `post_pr_cleanup`, and return status=routed (if new changes were rerouted onto a fresh branch) or status=skipped (if nothing new to sync).
- If current branch is non-protected with a CLOSED (unmerged) PR, return status=blocked with failure_reason="branch has an unmerged closed PR; user decision required" and next_action="ask user: reopen/reuse this branch, or abandon it and start fresh from <base>".
```

## Protected Branch Routing

This prompt never pushes directly to a protected branch (`main`, `master`, `release/*`, or any pattern in `GIT_PROTECTED_BRANCHES`). When changes exist on a protected branch, this prompt automatically routes them onto a new feature branch (Step 1a) — creating, committing, and pushing there — using the same naming/commit conventions as any other sync. It then automatically chains into the `Gitter: Pull Request Workflow` prompt for that feature branch, which runs `gh pr create` and gates progress on required checks and reviews. Local sync mechanics and GitHub-side PR lifecycle remain implemented in separate prompts (no duplicated `gh` logic, per the reuse-first policy) — this prompt just invokes the other one as its final step instead of requiring a manual re-prompt.

**What is and isn't automatic**: PR creation, check polling, and review-status polling all happen without human intervention as part of this chained flow. The actual merge onto the protected branch is never automatic — `gitter-pull-request.prompt.md` Step 6 still requires an explicit human "yes" before `gh pr merge` runs, and that gate is untouched by this change. The authoritative guardrail remains GitHub branch protection on the remote (required PR, required status checks, required reviews, no force-push); chaining only removes the need to manually re-invoke the next prompt, not the human review/merge gate itself.

## One PR in Flight (Step 1b)

When the current branch is not protected, Step 1b checks whether it already has an associated PR before staging anything new:
- **OPEN PR** → reuse the same branch; new commits land on the existing PR. No second branch, no second PR (avoids the rebase/force-push cascade that stacked branches would require).
- **MERGED PR** (typically merged externally/behind the scenes, without this session running the `gitter-pull-request` prompt's own post-merge cleanup) → clean up this stale branch (switch to base, pull, delete local+remote), then reroute any pending new changes onto a fresh branch via Step 1a.
- **CLOSED, unmerged PR** → stop and ask the user; abandoning or reusing a closed-without-merge branch is a judgment call this prompt will not make automatically.

This is the same cleanup mechanism `gitter-pull-request.prompt.md` runs proactively right after a merge it performs itself; Step 1b is the fallback that catches merges Gitter didn't perform.

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
- Action: this prompt auto-routes onto a new feature branch (Step 1a), pushes it, and automatically chains into the `Gitter: Pull Request Workflow` prompt for that branch (PR create -> checks -> review). No manual branch creation or manual re-invocation needed; merge still requires explicit human confirmation in that prompt's Step 6.

5a. Chained PR workflow could not start (`gh` missing or `GITHUB_PR_TOKEN` unset):
- Cause: PR-workflow prerequisites are not met even though the feature branch pushed successfully.
- Action: sync itself still reports status=routed (the branch is safely pushed); `chained_pr_workflow.status` reports the precondition failure and `next_action` gives the manual command to run once prerequisites are fixed.

6. Current branch is protected with a clean tree (nothing to sync):
- Cause: user ran this prompt on a protected branch just to check sync status.
- Action: report status=skipped with current ahead/behind state; no routing is performed since there is nothing to route.

7. Current branch is non-protected and already has an open PR:
- Cause: an earlier sync/PR-workflow invocation already pushed this branch and opened a PR that is still under review.
- Action: this prompt reuses the same branch (Step 1b) — new commits are added to the existing PR. No new branch or PR is created.

8. Current branch is non-protected and its PR already shows MERGED:
- Cause: the PR was approved and merged (possibly by a reviewer, outside of a Gitter-run merge), so the local branch is now stale.
- Action: Step 1b automatically switches to the base branch, pulls the merged commit(s), deletes the local and remote copies of the stale branch, then reroutes any pending new changes onto a fresh branch.

9. Current branch is non-protected and its PR shows CLOSED (not merged):
- Cause: the PR was closed without merging (e.g. abandoned or superseded).
- Action: this prompt stops and reports status=blocked; it asks the user to decide whether to reopen/reuse the branch or abandon it and start fresh from the base branch — it will not choose automatically.
