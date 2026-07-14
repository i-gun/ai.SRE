# Advisor Git Hooks - Documentation

## Overview

The Advisor agent uses two coordinated Git hooks to maintain project quality:

1. **pre-commit** — Runs before every commit
   - Detects file changes (added, modified, deleted)
   - Updates README.md with change summary
   - Auto-formats files based on type
   - Stages updated README.md and formatted files

2. **post-checkout** — Runs after checkout/clone operations
   - Automatically installs/reinstalls hooks
   - Ensures hooks persist across clones

## Installation

### Option 1: Automatic Installation (Recommended)

```bash
# From project root
bash git-hooks/install-hooks.sh
```

### Option 2: Manual Installation

```bash
# Copy hooks to Git hooks directory
cp git-hooks/pre-commit .git/hooks/
cp git-hooks/post-checkout .git/hooks/

# Make executable
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-checkout
```

### Option 3: For Team Collaboration

Add to project README or onboarding guide:

```bash
# After cloning repository
bash git-hooks/install-hooks.sh
```

## What Each Hook Does

### Pre-Commit Hook: Advisor Update & Format

**Trigger**: Before `git commit` finalizes

**Phase 1: Detect Changes**
- Identifies staged files (additions, modifications, deletions)
- Counts files in each category

**Phase 2: Update README.md**
- Creates README.md if missing
- Updates "Latest Changes" section with:
  - Timestamp of changes
  - File count by type
  - Individual file listings with descriptions
  - Line change counts for modified files
  - Deletion markers for removed files

**Phase 3: Auto-Format Files**
- Python files → `black` (if installed)
- JavaScript/JSON files → `prettier` (if installed)
- Markdown files → trailing space cleanup, extra line removal
- Stages formatted files automatically

**Phase 4: Final Checks**
- Validates README.md is staged
- Ensures all changes are committed

**Example Output**:
```
Advisor Pre-Commit Hook
==================================================
[PHASE 1] Detecting file changes...
✓ Changes detected:
  Added: 2 files
  Modified: 1 file
  Deleted: 0 files
  Total: 3 files

[PHASE 2] Updating README.md...
✓ README.md updated with change summary

[PHASE 3] Applying formatting rules...
Formatting Python files with black...
  ✓ Formatted: .github/skills/gitter-credentials/gitter_credentials.py

[PHASE 4] Final checks...
✓ README.md staged for commit

==================================================
✓ Pre-commit checks complete - Ready to commit
==================================================
```

### Post-Checkout Hook: Hook Reinstall

**Trigger**: After `git checkout`, `git clone`, or branch switch

**Actions**:
- Detects if in Git repository
- Copies hooks from `git-hooks/` to `.git/hooks/`
- Makes hooks executable
- Runs silently in background

**Why**: Ensures hooks are present after clone or checkout operations

## Hook Lifecycle

```
Developer makes changes
  ↓
git add .
  ↓
git commit -m "message"
  ↓
pre-commit hook TRIGGERS
  ├─ Detects changes
  ├─ Updates README.md
  ├─ Formats files
  ├─ Stages updates
  └─ Returns control
  ↓
Commit is finalized
  ↓
Developer pushes to remote
  ↓
git push origin main
  ↓
post-checkout hook ready (on next checkout/clone)
```

## README.md Auto-Update Format

The pre-commit hook updates README.md in this format:

```markdown
## File Changes Log

This section is automatically maintained by pre-commit hooks.

### Latest Changes

_Updated: 2026-07-09 14:30:45 by Advisor Hook_

#### Summary

**New Files Added** (2):
- `.github/skills/gitter-credentials/README.md` - Documentation
- `git-hooks/install-hooks.sh` - Installation script

**Files Modified** (1):
- `.github/agents/advisor.agent.md` - 45 line changes

**Files Removed** (0):
```

## File Type Detection

The hook auto-detects file types and applies appropriate formatting:

| Extension | Type | Formatter | Action |
|-----------|------|-----------|--------|
| `.py` | Python | `black` | Code formatting |
| `.js` | JavaScript | `prettier` | Code formatting |
| `.ts` | TypeScript | `prettier` | Code formatting |
| `.json` | JSON | `prettier` | Code formatting |
| `.md` | Markdown | Built-in | Trailing space cleanup |
| `.env*` | Environment | — | Auto-description |
| `.gitignore` | Git config | — | Auto-description |

## Formatting Tools (Optional but Recommended)

### Python Formatting

```bash
# Install black
pip install black

# What it does:
# - Consistent line length (88 chars)
# - Consistent quote style
# - Proper spacing around operators
```

### JavaScript/JSON Formatting

```bash
# Install prettier
npm install -g prettier

# What it does:
# - Consistent indentation (2 spaces)
# - Quote consistency
# - Trailing commas
# - Line breaking
```

### Markdown Linting

```bash
# Install markdownlint
npm install -g markdownlint

# What the hook does:
# - Remove trailing spaces
# - Clean multiple blank lines
# - Consistent line endings
```

## Skipping Hooks

If you need to bypass hooks on a specific commit:

```bash
# Skip pre-commit hook
git commit --no-verify -m "message"

# Not recommended except for emergency fixes!
```

## Troubleshooting

### Hooks Not Running

**Problem**: Pre-commit hook doesn't run

**Solution**:
```bash
# Check if hook is executable
ls -l .git/hooks/pre-commit

# Make executable
chmod +x .git/hooks/pre-commit

# Reinstall hooks
bash git-hooks/install-hooks.sh
```

### Hooks Not Formatting

**Problem**: Files not being formatted

**Cause**: Formatter tools not installed

**Solution**:
```bash
# Install optional formatters
pip install black
npm install -g prettier

# Re-run commit
git commit -m "message"
```

### README.md Not Updating

**Problem**: README.md not changed after commit

**Cause 1**: No staged files
**Solution**: `git add .` before committing

**Cause 2**: README.md is `.gitignore`'d
**Solution**: Remove from `.gitignore` if desired

**Cause 3**: Hook failing silently
**Solution**: Check hook for errors: `bash -x .git/hooks/pre-commit`

### Windows-Specific Issues

**Problem**: Hook doesn't execute on Windows

**Solution**:
```bash
# Git Bash required
# Or use Windows Subsystem for Linux (WSL)
# Or use Git for Windows with bash shell

# Ensure CRLF not interfering
git config core.safecrlf true
```

## Integration with Advisor Agent

### How Advisor Agent Uses Hooks

**User Request**: "Advisor, what changed in this project?"

**Advisor's Response**:
1. Reads README.md (updated by pre-commit hook)
2. Reviews "File Changes Log" section
3. Provides summary based on hook data
4. References specific file changes and types

### How Instructions Guide Hooks

From `advisor.agent.md`:

```markdown
## Tool Restrictions
- DO NOT manually edit README.md file change logs
- Trust automated hook updates
- Review hook changes in commits
```

### How Skills Enhance Hooks

Skills can extend hook functionality:
- Validate file changes against patterns
- Provide domain-specific descriptions
- Auto-generate API documentation
- Update test coverage reports

## Advanced: Customizing Hooks

### Add Custom Formatting

Edit `.git/hooks/pre-commit`, Phase 3 section:

```bash
# Format YAML files
if command -v yamllint &> /dev/null; then
  YAML_FILES=$(echo "$STAGED_FILES" | grep -E "\.ya?ml$" || true)
  # ... format logic ...
fi
```

### Add Custom README Sections

Edit `.git/hooks/pre-commit`, Phase 2 section:

```bash
# Add file count summary
CHANGE_SUMMARY="${CHANGE_SUMMARY}

**Statistics**:
- Total lines changed: $TOTAL_LINES
- Files affected: $TOTAL_CHANGES
- Average changes per file: $AVG_CHANGES
"
```

### Add Pre-Push Validation

Create `.git/hooks/pre-push`:

```bash
#!/bin/bash
# Validate before pushing to remote
# (similar structure to pre-commit)
```

## FAQ

**Q: Do I have to install hooks?**
A: No, they're optional. But recommended for maintaining README.md.

**Q: Can hooks break my commits?**
A: No, they only enhance commits with formatting and documentation.

**Q: What if hook fails?**
A: Commit is blocked. Fix the issue and retry. Use `--no-verify` only in emergencies.

**Q: Does README.md auto-update remove old info?**
A: Hook replaces "Latest Changes" section. Older changes should be in version control.

**Q: How do I share hooks with team?**
A: Commit `git-hooks/` directory and `.gitignore` to exclude `.git/hooks/`.
Team runs: `bash git-hooks/install-hooks.sh`

**Q: Can I disable README.md updates?**
A: Edit `.git/hooks/pre-commit` Phase 2 section, comment out update logic.

## Related Files

- [Advisor Agent Instructions](.github/agents/advisor.agent.md)
- [Project README](README.md)
- [Git Configuration](.gitignore)
