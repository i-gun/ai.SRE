# Gitter Credentials Skill

A comprehensive credentials management skill for the Gitter Git workflow agent, enabling secure and flexible management of Git identity, GitHub authentication, SSH keys, and GPG commit signing.

## Overview

This skill provides:

- **Secure Credential Loading**: Read Git credentials from environment-specific `.env` files
- **Multi-Profile Support**: Manage credentials for dev, staging, and production environments
- **Multiple Auth Methods**: Support SSH keys, GitHub Personal Access Tokens, or hybrid authentication
- **GPG Signing**: Optional commit signing for authenticity and verification
- **Validation**: Automatic credential validation with detailed error reporting
- **Security First**: `.env` files excluded from version control, no credential leakage

## Quick Start

### 1. Copy Environment Template
```bash
cp .env.template .env
```

### 2. Configure Credentials
Edit `.env` with your Git identity and GitHub authentication method:

```env
GIT_USER_NAME=Your Name
GIT_USER_EMAIL=your@email.com
GITHUB_AUTH_METHOD=ssh
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
```

### 3. Verify Gitignore
Confirm `.gitignore` includes `.env`:
```bash
grep "^\.env" .gitignore
```

### 4. Start Using Gitter
The agent will automatically load credentials before Git operations.

## File Structure

```
.github/skills/gitter-credentials/
├── SKILL.md                      # Skill definition and comprehensive documentation
├── SETUP.md                      # Detailed setup guide for different auth methods
├── gitter_credentials.py         # Python credential loader
├── gitter_credentials.js         # JavaScript credential loader
└── README.md                     # This file

Root folder:
├── .env                          # Your credentials (NOT committed)
├── .env.template                 # Template for creating .env
├── .env.example                  # Example with non-sensitive values
├── .env.dev                      # Profile-specific overrides (optional)
├── .env.staging                  # Profile-specific overrides (optional)
├── .env.prod                     # Profile-specific overrides (optional)
└── .gitignore                    # Excludes .env files from Git
```

## Authentication Methods

### SSH Keys (Recommended for Local Development)
```env
GITHUB_AUTH_METHOD=ssh
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
GITHUB_SSH_PASSPHRASE=            # optional
```

**Pros:**
- More secure than tokens
- No expiration dates
- Works with git protocol
- Better for offline operations

**Setup:**
```bash
ssh-keygen -t ed25519 -C "your@email.com"
# Add public key to https://github.com/settings/keys
ssh -T git@github.com  # Test
```

### Personal Access Token (HTTPS, For CI/Automation)
```env
GITHUB_AUTH_METHOD=https
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
```

**Pros:**
- Easier for CI/cloud environments
- Easier to rotate and revoke
- Works everywhere

**Setup:**
- Create token at: https://github.com/settings/tokens
- Scopes: `repo`, `read:user`, `user:email`

### Hybrid (Both Methods Available)
```env
GITHUB_AUTH_METHOD=auto
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
```

## Environment Profiles

Manage credentials across multiple environments (dev/staging/prod):

### Base Configuration `.env`
```env
GIT_USER_NAME=Your Name
GIT_USER_EMAIL=your@email.com
GITHUB_AUTH_METHOD=ssh
GITHUB_SSH_KEY_PATH=~/.ssh/id_ed25519
ENVIRONMENT_PROFILE=dev
```

### Profile Overrides `.env.{profile}`

**`.env.dev`** — Development overrides
```env
ENVIRONMENT_PROFILE=dev
GPG_SIGNING_ENABLED=false
```

**`.env.staging`** — Staging overrides
```env
ENVIRONMENT_PROFILE=staging
GIT_USER_EMAIL=your+staging@email.com
GPG_SIGNING_ENABLED=false
```

**`.env.prod`** — Production overrides
```env
ENVIRONMENT_PROFILE=prod
GIT_USER_EMAIL=your+prod@email.com
GPG_SIGNING_ENABLED=true
GPG_KEY_ID=3AA5C34371567BD2
```

### Switch Profiles
Edit `.env` to change active profile:
```env
ENVIRONMENT_PROFILE=staging
```

Gitter will automatically load overrides from `.env.staging`.

## GPG Commit Signing (Optional)

Prove authorship and prevent tampering by signing commits:

```env
GPG_SIGNING_ENABLED=true
GPG_KEY_ID=3AA5C34371567BD2
```

### Setup GPG Signing

1. **Generate GPG key** (if needed)
```bash
gpg --gen-key
# Follow prompts (RSA/RSA, 4096-bit, name/email)
```

2. **List your keys**
```bash
gpg --list-secret-keys --keyid-format LONG
# Copy the 16-character ID: 3AA5C34371567BD2
```

3. **Add to GitHub**
```bash
gpg --armor --export 3AA5C34371567BD2 | pbcopy
# GitHub Settings → SSH and GPG Keys → New GPG Key → Paste
```

4. **Enable in `.env`**
```env
GPG_SIGNING_ENABLED=true
GPG_KEY_ID=3AA5C34371567BD2
```

5. **Configure Git**
```bash
git config user.signingkey 3AA5C34371567BD2
git config commit.gpgsign true
```

## Usage: Python Loader

Load credentials in Python code:

```python
from gitter_credentials import CredentialsLoader, CredentialError

try:
    loader = CredentialsLoader()
    
    # Load credentials
    creds = loader.load(profile='dev')
    
    # Access properties
    print(f"User: {creds.git_user_name}")
    print(f"Email: {creds.git_user_email}")
    print(f"Auth: {creds.auth_method.value}")
    
    # Get summary
    print(loader.get_summary(profile='dev'))
    
except CredentialError as e:
    print(f"Error: {e}")
```

### CLI Usage (Python)
```bash
python gitter_credentials.py
python gitter_credentials.py dev
python gitter_credentials.py staging
```

## Usage: JavaScript Loader

Load credentials in JavaScript/Node.js:

```javascript
const { CredentialsLoader } = require('./gitter_credentials.js');

try {
    const loader = new CredentialsLoader();
    
    // Load credentials
    const creds = loader.load('dev');
    
    // Access properties
    console.log(`User: ${creds.git_user_name}`);
    console.log(`Email: ${creds.git_user_email}`);
    console.log(`Auth: ${creds.auth_method}`);
    
    // Get summary
    console.log(loader.getSummary('dev'));
    
} catch (error) {
    console.error(`Error: ${error.message}`);
}
```

### CLI Usage (JavaScript)
```bash
node gitter_credentials.js
node gitter_credentials.js dev
node gitter_credentials.js staging
```

## Gitter Agent Integration

The Gitter Git workflow agent will:

1. Load credentials from `.env` before executing operations
2. Validate credentials against requirements
3. Apply credentials temporarily for Git operations
4. Never expose credentials in logs or error messages
5. Support credential switching between profiles

### Example Agent Usage

```
User: "Gitter, push my changes"

Gitter: "Loading credentials from .env (profile: dev)..."
Gitter: "✓ Git credentials validated"
Gitter: "✓ SSH key verified: ~/.ssh/id_ed25519"
Gitter: "Pushing 5 commits to origin/main..."
Gitter: "✓ Successfully pushed!"
```

## Security Best Practices

### DO ✓
- Use SSH keys for local development
- Use tokens for CI/automation
- Encrypt SSH keys with strong passphrases
- Rotate credentials regularly
- Keep `.env` in `.gitignore`
- Store `.env` backups in secure, encrypted storage
- Use minimal token scopes
- Enable two-factor authentication on GitHub

### DON'T ✗
- Commit `.env` files to version control
- Share `.env` via email or chat
- Use personal GitHub passwords (use tokens)
- Hardcode credentials in scripts
- Use the same token across multiple machines
- Enable GPG signing globally without understanding implications
- Expose credentials in terminal history or logs

## Troubleshooting

### SSH Connection Failed
```bash
# Verify SSH key exists
ls -la ~/.ssh/id_ed25519

# Test SSH connection
ssh -T git@github.com

# Add key to SSH agent
ssh-add ~/.ssh/id_ed25519
```

### Credentials Validation Failed
```bash
# Verify .env exists
ls -la .env

# Check required fields
grep "GIT_USER_NAME" .env
grep "GIT_USER_EMAIL" .env

# Test loading (Python)
python gitter_credentials.py

# Test loading (JavaScript)
node gitter_credentials.js
```

### GitHub Token Expired
```bash
# Generate new token at https://github.com/settings/tokens
# Update .env with new token
GITHUB_TOKEN=ghp_new_token_here
```

### GPG Key Not Found
```bash
# List available keys
gpg --list-secret-keys --keyid-format LONG

# Verify GPG_KEY_ID matches
grep "GPG_KEY_ID" .env
```

### SSH Permissions Too Open
```bash
# SSH keys must be readable only by you
chmod 600 ~/.ssh/id_ed25519
```

## Maintenance

### Regular Tasks
- **Monthly**: Review GitHub Personal Access Token expiration
- **Quarterly**: Rotate SSH keys if used across multiple machines
- **Quarterly**: Audit GPG keys and signing status
- **Annually**: Review `.env` configuration for outdated patterns

### Credential Rotation

**Update SSH Key:**
```bash
ssh-keygen -t ed25519 -C "your@email.com" -f ~/.ssh/id_ed25519_new
# Update .env with new path
# Add public key to GitHub
# Test and cleanup old key
```

**Update GitHub Token:**
```bash
# Generate new token at https://github.com/settings/tokens
# Update .env: GITHUB_TOKEN=ghp_new_token_here
# Revoke old token in GitHub settings
```

## Files Reference

| File | Purpose | Sensitive | Commit |
|------|---------|-----------|--------|
| `.env` | Your credentials | YES | NO (in .gitignore) |
| `.env.template` | Template for setup | NO | YES |
| `.env.example` | Example config | NO | YES |
| `.env.dev` | Dev overrides | MAYBE | NO (in .gitignore) |
| `.env.staging` | Staging overrides | YES | NO (in .gitignore) |
| `.env.prod` | Prod overrides | YES | NO (in .gitignore) |
| `.gitignore` | Git exclusions | NO | YES |
| `SKILL.md` | Skill documentation | NO | YES |
| `SETUP.md` | Setup guide | NO | YES |
| `gitter_credentials.py` | Python loader | NO | YES |
| `gitter_credentials.js` | JS loader | NO | YES |

## Related Resources

- [GitHub SSH Setup Guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GitHub Personal Access Tokens](https://github.com/settings/tokens)
- [GitHub GPG Commit Signing](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)
- [SSH Best Practices](https://wiki.archlinux.org/title/SSH_keys)
- [Git Configuration Reference](https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup)
- [Gitter Agent Documentation](./../gitter.agent.md)
- [Advisor Agent Documentation](./../advisor.agent.md)

## Support & Issues

1. Check `.env` exists in project root
2. Verify `.env` is in `.gitignore`
3. Run credential loader to validate: `python gitter_credentials.py`
4. Review detailed setup guide: [SETUP.md](./SETUP.md)
5. Check Gitter agent logs for specific error messages
6. Review troubleshooting section above
