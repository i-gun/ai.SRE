---
name: 'gitter-credentials'
description: 'Credential management skill for Gitter Git workflow agent. Reads and validates .env configuration for Git user identity, GitHub authentication, SSH keys, and GPG signing credentials across multiple environment profiles.'
keywords: ['git', 'credentials', 'github', 'ssh', 'gpg', 'environment', 'configuration']
---

# Gitter Credentials Skill

Enables the Gitter Git workflow agent to securely manage and load Git credentials, GitHub authentication tokens, SSH keys, and GPG signing configurations from environment-specific `.env` files.

## Purpose

This skill provides secure, profile-aware credential management for:
- **Git Identity**: Username and email for commits
- **GitHub Authentication**: Personal Access Tokens for HTTPS operations
- **SSH Configuration**: SSH key paths and passphrases for git protocol operations
- **GPG Signing**: GPG key IDs for commit signing and verification
- **Multi-Environment Support**: Profile-based configuration (dev/staging/prod)

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## When to Use This Skill

- User initializes a new repository and needs credential setup
- Gitter agent requires authentication for remote operations (push/pull/clone)
- Team members need to configure local Git identity and GitHub access
- Switching between different environment profiles or GitHub accounts
- Setting up GPG commit signing for verification workflows
- Validating credential configuration before executing Git operations

## When NOT to Use This Skill

- Querying system git configuration (use `git config --list`)
- Managing GitHub repository settings or permissions (use GitHub web interface)
- Troubleshooting git authentication failures (use `ssh -T git@github.com` diagnostic)
- General Git workflow questions (use Gitter agent core instructions)

## Configuration Setup

### Step 1: Create Environment File

Copy the provided `.env.template` to `.env` in your project root:

```bash
cp .env.template .env
```

**Important**: `.env` is excluded from version control via `.gitignore` and contains sensitive credentials. Never commit this file.

### Step 2: Configure Git Identity

Edit `.env` and set your Git user information:

```env
# Required: Git user identity for commits
GIT_USER_NAME=Your Full Name
GIT_USER_EMAIL=your.email@example.com
```

### Step 3: Configure GitHub Authentication

Choose ONE authentication method for GitHub operations:

#### Option A: HTTPS with Personal Access Token (Recommended for CI/Cloud)

```env
GITHUB_AUTH_METHOD=https
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

[Create a Personal Access Token](https://github.com/settings/tokens)
- Scopes required: `repo`, `read:user`, `user:email`
- Store securely; never commit to version control

#### Option B: SSH Authentication (Recommended for Local Development)

```env
GITHUB_AUTH_METHOD=ssh
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
GITHUB_SSH_PASSPHRASE=your-passphrase-here-or-leave-empty
```

SSH key setup:
```bash
ssh-keygen -t ed25519 -C "your.email@example.com"
# Add public key to GitHub: https://github.com/settings/keys
```

#### Option C: Hybrid (Both Methods Available)

```env
GITHUB_AUTH_METHOD=auto
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
GITHUB_SSH_PASSPHRASE=
```

### Step 4: Configure GPG Signing (Optional)

For commit signing verification:

```env
GPG_SIGNING_ENABLED=false
GPG_KEY_ID=your-gpg-key-id
GPG_SIGNING_KEY_PATH=~/.gnupg/private-keys-v1.d/your-key-id.key
```

Set to `true` to enable signing on all commits. Requires GPG installation and key setup:
```bash
gpg --list-secret-keys --keyid-format LONG
gpg --armor --export-secret-key KEY_ID  # Backup key
```

### Step 5: Configure Environment Profiles (Optional)

For multi-environment workflows:

```env
ENVIRONMENT_PROFILE=dev
```

Create profile-specific overrides:
- `.env.dev` — Development environment (default)
- `.env.staging` — Staging/pre-production environment
- `.env.prod` — Production environment (highly restricted)

Profile-specific files override base `.env` values. Example `.env.prod`:

```env
# Production profile - restricted operations
GIT_USER_NAME=Your Full Name
GIT_USER_EMAIL=your.email@example.com
GITHUB_AUTH_METHOD=https
GITHUB_TOKEN=ghp_prod_xxxxx
# Note: No SSH passphrase in production profiles
GPG_SIGNING_ENABLED=true
GPG_KEY_ID=prod-gpg-key-id
```

## Credential Validation

The Gitter agent will validate credentials before attempting remote operations:

### Validation Checklist
- ✓ `.env` file exists and is readable
- ✓ Required fields populated (GIT_USER_NAME, GIT_USER_EMAIL)
- ✓ GitHub authentication method specified and valid
- ✓ SSH key path exists and has correct permissions (600)
- ✓ GPG key ID matches installed GPG keys (if signing enabled)
- ✓ No hardcoded passwords in `.env` — only paths and tokens

### Automatic Fallbacks
If `.env` is not configured:
1. Gitter will attempt to use system git configuration (`git config user.name`, `git config user.email`)
2. GitHub authentication will fall back to SSH agent or system SSH configuration
3. GPG signing will use system default key

## Security Best Practices

### DO
- ✓ Use SSH keys instead of tokens for local development
- ✓ Use Personal Access Tokens for CI/automation environments
- ✓ Encrypt SSH keys with strong passphrases
- ✓ Rotate credentials regularly
- ✓ Use `.gitignore` to prevent `.env` from being committed
- ✓ Store `.env` backups in secure, encrypted storage
- ✓ Use read-only tokens where possible (scope appropriately)
- ✓ Enable two-factor authentication on GitHub account

### DON'T
- ✗ Commit `.env` files to version control
- ✗ Store credentials in shell history or environment variables (use `.env`)
- ✗ Use personal GitHub passwords (use tokens or SSH)
- ✗ Share `.env` files via email or chat
- ✗ Use the same token/key across multiple machines
- ✗ Hardcode credentials in scripts or configuration files
- ✗ Commit GPG private key files
- ✗ Enable GPG signing globally without understanding implications

## Environment Variables Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `GIT_USER_NAME` | Your full name for Git commits | `Jane Developer` |
| `GIT_USER_EMAIL` | Email associated with Git commits | `jane@example.com` |

### GitHub Authentication (Choose One Method)

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_AUTH_METHOD` | Authentication method: `https`, `ssh`, or `auto` | `ssh` |
| `GITHUB_TOKEN` | Personal Access Token (HTTPS method) | `ghp_xxxxxxxxxxxx` |
| `GITHUB_SSH_KEY_PATH` | Path to SSH private key (SSH method) | `~/.ssh/id_ed25519` |
| `GITHUB_SSH_PASSPHRASE` | SSH key passphrase (optional) | `(leave empty if key unencrypted)` |

### GPG Signing (Optional)

| Variable | Description | Example |
|----------|-------------|---------|
| `GPG_SIGNING_ENABLED` | Enable commit signing: `true` or `false` | `false` |
| `GPG_KEY_ID` | GPG key ID for signing | `3AA5C34371567BD2` |
| `GPG_SIGNING_KEY_PATH` | Path to GPG private key (optional) | `~/.gnupg/private-keys-v1.d/` |

### Environment Profiles (Optional)

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT_PROFILE` | Active profile: `dev`, `staging`, or `prod` | `dev` |

## Usage Examples

### Basic Setup (Single Profile, SSH)
```env
GIT_USER_NAME=John Developer
GIT_USER_EMAIL=john@company.com
GITHUB_AUTH_METHOD=ssh
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
GITHUB_SSH_PASSPHRASE=
```

### Team Setup (Multiple Profiles, Hybrid Auth)
```env
# Base configuration
GIT_USER_NAME=John Developer
GIT_USER_EMAIL=john@company.com
GITHUB_AUTH_METHOD=auto
GITHUB_TOKEN=ghp_xxxxxxxx
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
GITHUB_SSH_PASSPHRASE=

# Profile override
ENVIRONMENT_PROFILE=dev
GPG_SIGNING_ENABLED=false
```

### Enterprise Setup (GPG Signing, Production Profile)
```env
# .env (development)
GIT_USER_NAME=Corporate Contributor
GIT_USER_EMAIL=contributor@company.com
GITHUB_AUTH_METHOD=https
GITHUB_TOKEN=ghp_xxxxxxxx
ENVIRONMENT_PROFILE=prod
GPG_SIGNING_ENABLED=true
GPG_KEY_ID=123ABC456DEF789
```

## Troubleshooting

### "Credential validation failed"
- Verify `.env` file exists in project root
- Check that required variables are not empty
- Ensure SSH keys exist and have correct permissions (`ls -la ~/.ssh/`)
- Confirm GitHub token has not expired

### "SSH key permission denied"
- Verify SSH key permissions: `chmod 600 ~/.ssh/your-key`
- Confirm public key added to GitHub: `ssh -T git@github.com`
- Check SSH passphrase if key is encrypted

### "GitHub API rate limit exceeded"
- Using Personal Access Token? Verify it has not expired
- Check token scopes are sufficient: `https://github.com/settings/tokens`
- Consider using SSH authentication to avoid rate limits

### "GPG key not found"
- List available keys: `gpg --list-secret-keys --keyid-format LONG`
- Verify `GPG_KEY_ID` matches installed key
- Ensure GPG is installed: `which gpg`

## Integration with Gitter Agent

The Gitter agent will:
1. Load credentials from `.env` before executing operations
2. Validate credentials against requirements
3. Apply credentials to Git configuration temporarily for operations
4. Never expose credentials in logs or error messages
5. Support credential switching between profiles

### Example: Gitter Operation Flow

```
User: "Gitter, push my changes"
  ↓
Gitter: "Loading credentials from .env (profile: dev)"
  ↓
Gitter: "Validating GitHub SSH key at ~/.ssh/id_ed25519"
  ↓
Gitter: "Configuring Git identity: John Developer (john@example.com)"
  ↓
Gitter: "Executing git push using SSH authentication"
  ↓
Gitter: "✓ Successfully pushed 3 commits to origin/main"
```

## Maintenance

### Regular Tasks
- Monthly: Review GitHub Personal Access Token expiration date
- Quarterly: Rotate SSH keys if used across development machines
- Quarterly: Audit GPG keys and confirm signing status
- Annually: Review `.env` configuration for outdated patterns

### Credential Rotation
```bash
# Generate new SSH key
ssh-keygen -t ed25519 -C "your.email@example.com" -f ~/.ssh/id_ed25519_new

# Update .env
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519_new

# Test connectivity
ssh -T git@github.com

# Cleanup old key (after verification)
rm ~/.ssh/id_ed25519
```

### Profile Migration
To switch profiles in `.env`:
```env
ENVIRONMENT_PROFILE=staging
```

This will load overrides from `.env.staging`, falling back to base `.env` for unspecified variables.

## Related Resources

- [GitHub Personal Access Tokens](https://github.com/settings/tokens)
- [GitHub SSH Setup Guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GPG Commit Signing](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)
- [Git Configuration Documentation](https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup)
- [SSH Key Best Practices](https://wiki.archlinux.org/title/SSH_keys)
