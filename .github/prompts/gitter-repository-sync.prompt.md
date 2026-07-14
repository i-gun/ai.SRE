# Gitter Prompt: Local Repository Synchronization

Use this prompt with the Gitter agent to synchronize local changes with the remote repository.

```text
@Gitter, synchronize my local branch with remote.
1) Check for unstaged/uncommitted changes and list them.
2) If changes exist, stage all relevant files.
3) Create a commit with a clear conventional commit message: <type>(<scope>): <summary>.
4) Push current branch to origin.
5) Verify sync status (ahead/behind) and report final result.
If no local changes exist, just confirm repository is already in sync.
```
