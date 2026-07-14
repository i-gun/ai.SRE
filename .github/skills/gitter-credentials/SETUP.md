# Gitter Credentials Skill Setup Guide

## Overview

The **Gitter Credentials Skill** enables the Gitter Git workflow agent to securely manage Git credentials and GitHub authentication tokens. This guide walks through complete setup for first-time users.

## Quick Start (5 minutes)

### 1. Copy Environment Template
```bash
cp .env.template .env
```

### 2. Edit `.env` with Your Details
```bash
# Open .env in editor
GIT_USER_NAME=Your Name
GIT_USER_EMAIL=your@email.com
GITHUB_AUTH_METHOD=ssh
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
```

### 3. Verify Gitignore
Confirm `.gitignore` includes `.env`:
```bash
grep -E "^\.env" .gitignore
# Output should show: .env
```

### 4. Test Git Configuration
```bash
git config user.name "Your Name"
git config user.email "your@email.com"
git config --list | grep user
```

Done! Gitter agent can now use your credentials.

---

## Detailed Setup by Authentication Method

### SSH Authentication (Recommended for Local Development)

**Why SSH?**
- More secure than tokens
- No expiration dates
- Works with git protocol
- Better for offline operations

**Setup Steps:**

1. **Generate SSH Key (if you don't have one)**
```bash
ssh-keygen -t ed25519 -C "your.email@example.com"
# Press Enter twice (uses default path ~/.ssh/id_ed25519)
# Optional: set passphrase for additional security
```

2. **Add Public Key to GitHub**
```bash
# Copy public key to clipboard
cat ~/.ssh/id_ed25519.pub | pbcopy  # macOS
cat ~/.ssh/id_ed25519.pub | xclip   # Linux
type %USERPROFILE%\.ssh\id_ed25519.pub | clip  # Windows

# Go to GitHub Settings → SSH Keys → New SSH Key
# Paste and save
```

3. **Test SSH Connection**
```bash
ssh -T git@github.com
# Should output: Hi {username}! You've successfully authenticated...
```

4. **Configure `.env`**
```env
GITHUB_AUTH_METHOD=ssh
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
GITHUB_SSH_PASSPHRASE=
```

### HTTPS Authentication with Personal Access Token

**Why HTTPS with Token?**
- Easier for CI/automation
- No SSH agent required
- Good for restricted networks
- Tokens can be scoped and revoked easily

**Setup Steps:**

1. **Create Personal Access Token**
   - Go to https://github.com/settings/tokens
   - Click "Generate new token"
   - Select scopes:
     - ✓ `repo` (full control of private repositories)
     - ✓ `read:user` (read user profile data)
     - ✓ `user:email` (access email addresses)
   - Copy token immediately (you won't see it again)

2. **Configure `.env`**
```env
GITHUB_AUTH_METHOD=https
GITHUB_TOKEN=ghp_your_token_here
```

3. **Test Authentication**
```bash
git clone https://github.com/your-username/your-repo.git
# Should work without prompting for password
```

### Hybrid Authentication (Both Methods)

**Why Hybrid?**
- SSH for local development (better security)
- Token for CI/automation (easier management)
- Maximum flexibility

**Configure `.env`**
```env
GITHUB_AUTH_METHOD=auto
GITHUB_TOKEN=ghp_your_token_here
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
GITHUB_SSH_PASSPHRASE=
```

---

## GPG Commit Signing (Optional)

GPG signing proves you wrote the commit and hasn't been tampered with.

### Setup Steps:

1. **Generate GPG Key (if you don't have one)**
```bash
gpg --gen-key
# Follow prompts:
# - Kind: RSA and RSA (option 1)
# - Key size: 4096
# - Validity: 0 (no expiration recommended for dev)
# - Name: Your Name
# - Email: your@email.com
```

2. **List Your Keys**
```bash
gpg --list-secret-keys --keyid-format LONG
# Output: sec   rsa4096/3AA5C34371567BD2 2024-01-15
#         uid   Your Name <your@email.com>
# Copy the ID: 3AA5C34371567BD2
```

3. **Add to GitHub**
```bash
# Export public key
gpg --armor --export 3AA5C34371567BD2 | pbcopy

# GitHub Settings → SSH and GPG keys → New GPG Key
# Paste and save
```

4. **Configure `.env`**
```env
GPG_SIGNING_ENABLED=true
GPG_KEY_ID=3AA5C34371567BD2
```

5. **Enable Git Signing**
```bash
git config user.signingkey 3AA5C34371567BD2
git config commit.gpgsign true  # Sign all commits by default
```

### Verify Signing
```bash
git log --show-signature
# Should show: gpg: Good signature from "Your Name <your@email.com>"
```

---

## Environment Profiles Setup

For teams with multiple workflows (dev/staging/production):

### Create Profile-Specific Files

**`.env` (base, always loaded)**
```env
GIT_USER_NAME=Your Name
GIT_USER_EMAIL=your.email@example.com
GITHUB_AUTH_METHOD=ssh
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
ENVIRONMENT_PROFILE=dev
GPG_SIGNING_ENABLED=false
```

**`.env.dev` (development profile overrides)**
```env
ENVIRONMENT_PROFILE=dev
GIT_USER_EMAIL=your.email+dev@example.com
GPG_SIGNING_ENABLED=false
```

**`.env.staging` (staging profile overrides)**
```env
ENVIRONMENT_PROFILE=staging
GIT_USER_EMAIL=your.email+staging@example.com
GPG_SIGNING_ENABLED=true
```

**`.env.prod` (production profile overrides)**
```env
ENVIRONMENT_PROFILE=prod
GIT_USER_EMAIL=your.email+prod@example.com
GPG_SIGNING_ENABLED=true
GPG_KEY_ID=3AA5C34371567BD2
GITHUB_AUTH_METHOD=https
GITHUB_TOKEN=ghp_prod_token_here
```

### Switch Between Profiles

Edit `.env` to change active profile:
```env
ENVIRONMENT_PROFILE=staging
```

Gitter agent will automatically load overrides from `.env.staging`.

---

## Security Checklist

Before committing `.env` to any operations, verify:

- [ ] `.gitignore` includes `.env` and `.env.*.local`
- [ ] `.env` is in root project directory
- [ ] Never committed `.env` to Git
- [ ] SSH keys have correct permissions: `chmod 600 ~/.ssh/id_*`
- [ ] GitHub token has appropriate scopes (not `admin` or `delete_repo`)
- [ ] GPG keys are backed up in secure location
- [ ] Credentials are not logged or exposed in terminal history
- [ ] SSH agent is running (for passphrase management)

---

## Troubleshooting

### "Permission denied (publickey)"
```bash
# SSH key not accessible
ssh-add ~/.ssh/id_ed25519
ssh -T git@github.com
```

### "fatal: could not read Username"
```bash
# SSH key path incorrect in .env
# Verify key exists: ls -la ~/.ssh/id_ed25519
# Test SSH: ssh -T git@github.com -i ~/.ssh/id_ed25519
```

### "Credentials validation failed"
```bash
# Check .env format
cat .env | grep -v "^#"  # Show non-comment lines

# Verify required fields
grep "GIT_USER_NAME" .env
grep "GIT_USER_EMAIL" .env
grep "GITHUB_AUTH_METHOD" .env
```

### "GPG key not found"
```bash
# List available keys
gpg --list-secret-keys --keyid-format LONG

# Ensure GPG_KEY_ID matches output
# Verify GPG_SIGNING_ENABLED=true in .env
```

### Git not finding credentials
```bash
# Use SSH agent for SSH keys
eval $(ssh-agent -s)
ssh-add ~/.ssh/id_ed25519

# For HTTPS tokens, use git credential helper
git config credential.helper store
# Then git will cache token after first use
```

---

## Credentials Rotation

### Update SSH Keys (Annually or if Compromised)

```bash
# Generate new key
ssh-keygen -t ed25519 -C "your@email.com" -f ~/.ssh/id_ed25519_new

# Update .env
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519_new

# Update GitHub public key
cat ~/.ssh/id_ed25519_new.pub | pbcopy
# GitHub Settings → SSH Keys → Remove old → Add new

# Test
ssh -T git@github.com

# Cleanup
rm ~/.ssh/id_ed25519
```

### Update GitHub Token (Every 6 months or if Leaked)

```bash
# Generate new token at https://github.com/settings/tokens
# Copy new token

# Update .env
GITHUB_TOKEN=ghp_new_token_here

# Revoke old token at GitHub Settings
```

---

## Integration with Gitter Agent

Once credentials are configured, Gitter agent will:

1. Load `.env` on startup
2. Validate credentials before operations
3. Apply credentials temporarily for Git operations
4. Never expose credentials in output or logs
5. Support switching profiles mid-session

### Example Usage

```
User: "Gitter, push my changes"

Gitter: "Loading credentials from .env (profile: dev)..."
Gitter: "✓ Credentials valid"
Gitter: "✓ SSH key verified: ~/.ssh/id_ed25519"
Gitter: "✓ Git user: Your Name <your@email.com>"
Gitter: "Pushing 5 commits to origin/main..."
Gitter: "✓ Successfully pushed!"
```

---

## Best Practices Summary

| Practice | Why | How |
|----------|-----|-----|
| Use SSH for local dev | More secure, no expiration | Store key passphrase in SSH agent |
| Use tokens for CI/cloud | Easier management, easier revocation | Create scoped tokens, rotate every 6 months |
| Enable GPG signing | Verify author, prevent tampering | Set `GPG_SIGNING_ENABLED=true` |
| Use environment profiles | Different workflows for diff environments | Create `.env.{profile}` files |
| Rotate credentials | Prevent compromise escalation | SSH keys annually, tokens every 6 months |
| Keep .env in .gitignore | Prevent credential leaks | Verify `.gitignore` includes `.env` |

---

## Resources

- [GitHub SSH Setup](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GitHub Personal Access Tokens](https://github.com/settings/tokens)
- [GitHub GPG Signing](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)
- [SSH Best Practices](https://wiki.archlinux.org/title/SSH_keys)
- [Git Signing Documentation](https://git-scm.com/book/en/v2/Git-Tools-Signing-Your-Work)

---

## Support

For issues:
1. Check `.env` is in `.gitignore`
2. Verify `.env` values match credentials
3. Test connectivity: `ssh -T git@github.com` or `git clone https://...`
4. Check Gitter agent logs for specific error messages
5. Review troubleshooting section above
