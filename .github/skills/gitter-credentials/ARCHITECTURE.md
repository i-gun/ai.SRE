# Gitter Credentials Skill - Integration & Architecture Guide

## Overview

The **Gitter Credentials Skill** is a comprehensive credential management system designed specifically for the Gitter Git workflow agent. It provides secure, profile-aware loading and validation of Git credentials from environment-specific `.env` files.

## Architecture & Design

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────┐
│ Gitter Agent                                    │
│ (Request credential validation/loading)         │
└────────────────┬────────────────────────────────┘
                 │ Requests credentials
                 ↓
┌─────────────────────────────────────────────────┐
│ Gitter Credentials Skill                        │
│ (Load, validate, return credentials)            │
│ - Loaders (Python/JS)                           │
│ - Validators                                    │
│ - Profile managers                              │
└────────────────┬────────────────────────────────┘
                 │ Reads/parses
                 ↓
┌─────────────────────────────────────────────────┐
│ Environment Configuration Files                 │
│ - .env (base config)                            │
│ - .env.dev / .env.staging / .env.prod (overrides)│
│ (Both files excluded from Git via .gitignore)   │
└─────────────────────────────────────────────────┘
```

### Data Flow

```
User → Gitter Agent → Skill Loader
                         ↓
                  Load .env (base)
                         ↓
                  Load .env.{profile} (override)
                         ↓
                  Validate credentials
                         ↓
                  Return GitCredentials
                         ↓
                  Gitter applies to Git operations
```

## Skill File Organization

```
.github/
├── agents/
│   ├── advisor.agent.md          # Advisor agent definition
│   └── gitter.agent.md           # Gitter agent definition
└── skills/
    └── gitter-credentials/       # ← This skill
        ├── SKILL.md              # Skill definition & docs
        ├── SETUP.md              # Detailed setup guide
        ├── README.md             # Overview & usage
        ├── gitter_credentials.py # Python implementation
        └── gitter_credentials.js # JavaScript implementation

Root:
├── .env                          # User credentials (NOT committed)
├── .env.template                 # Template for setup
├── .env.example                  # Example configuration
├── .env.dev                      # Dev profile (optional, NOT committed)
├── .env.staging                  # Staging profile (optional, NOT committed)
├── .env.prod                     # Prod profile (optional, NOT committed)
└── .gitignore                    # Excludes .env files
```

## Credential Types Supported

### Git Identity (Required)
```
GIT_USER_NAME        → Git author name
GIT_USER_EMAIL       → Git author email
```

### GitHub Authentication (One Method Required)
```
GITHUB_AUTH_METHOD   → ssh | https | auto
GITHUB_TOKEN         → Personal Access Token (HTTPS method)
GITHUB_SSH_KEY_PATH  → SSH private key path (SSH method)
GITHUB_SSH_PASSPHRASE → SSH key passphrase (optional)
```

### GPG Signing (Optional)
```
GPG_SIGNING_ENABLED  → true | false
GPG_KEY_ID           → 16-char key ID
GPG_SIGNING_KEY_PATH → Path to GPG key (optional, auto-detected)
```

### Environment Management (Optional)
```
ENVIRONMENT_PROFILE  → dev | staging | prod
```

## Validation Logic

The skill performs multi-stage validation:

```
Stage 1: File Existence
  ✓ .env exists and is readable

Stage 2: Required Fields
  ✓ GIT_USER_NAME not empty
  ✓ GIT_USER_EMAIL valid format
  ✓ GITHUB_AUTH_METHOD specified

Stage 3: Authentication Method
  ✓ HTTPS: GITHUB_TOKEN provided
  ✓ SSH: GITHUB_SSH_KEY_PATH exists, readable, correct permissions
  ✓ AUTO: Either token or SSH key configured

Stage 4: GPG Configuration (if enabled)
  ✓ GPG_KEY_ID matches installed keys
  ✓ GPG tool available on system

Stage 5: Profile Configuration
  ✓ ENVIRONMENT_PROFILE in [dev, staging, prod]
  ✓ Profile override files readable (if specified)

Result: GitCredentials object or CredentialError exception
```

## Gitter Agent Integration Points

### 1. Agent Initialization
```
Gitter Agent Start
  ↓
Check for .env file
  ↓
Load credentials (use ENVIRONMENT_PROFILE)
  ↓
Validate credentials
  ↓
Store in agent context
```

### 2. Before Git Operations
```
User: "Gitter, push my changes"
  ↓
Gitter loads credentials from cache/reload
  ↓
Validate credentials are still valid
  ↓
Apply to git config (temporarily)
  ↓
Execute git push
  ↓
Clear sensitive data from context
```

### 3. Error Handling
```
Credential loading fails
  ↓
CredentialError with detailed message
  ↓
Gitter suggests corrective action
  ↓
Link to SETUP.md for guidance
```

## Implementation Guide for Gitter Agent

### Python Implementation

```python
from gitter_credentials import CredentialsLoader, CredentialError

class GitterAgent:
    def __init__(self):
        self.credentials_loader = CredentialsLoader()
        self.credentials = None
    
    def load_credentials(self, profile='dev'):
        """Load and cache credentials"""
        try:
            self.credentials = self.credentials_loader.load(profile)
            return True
        except CredentialError as e:
            print(f"Credential Error: {e}")
            return False
    
    def execute_git_command(self, command):
        """Execute git command with credentials"""
        if not self.credentials:
            if not self.load_credentials():
                raise Exception("Failed to load credentials")
        
        # Apply credentials
        git_env = self._prepare_git_environment()
        
        # Execute command
        # ... git execution ...
        
        # Clear sensitive data
        git_env.clear()
```

### JavaScript Implementation

```javascript
const { CredentialsLoader } = require('./gitter_credentials.js');

class GitterAgent {
    constructor() {
        this.credentialsLoader = new CredentialsLoader();
        this.credentials = null;
    }
    
    loadCredentials(profile = 'dev') {
        try {
            this.credentials = this.credentialsLoader.load(profile);
            return true;
        } catch (error) {
            console.error(`Credential Error: ${error.message}`);
            return false;
        }
    }
    
    async executeGitCommand(command) {
        if (!this.credentials) {
            if (!this.loadCredentials()) {
                throw new Error('Failed to load credentials');
            }
        }
        
        // Apply credentials
        const gitEnv = this.prepareGitEnvironment();
        
        // Execute command
        // ... git execution ...
        
        // Clear sensitive data
        gitEnv = null;
    }
}
```

## Security Considerations

### Credential Storage
- ✓ `.env` stored locally only (not in version control)
- ✓ `.env` permissions should be 600 (read/write owner only)
- ✓ SSH keys stored in `~/.ssh/` with 600 permissions
- ✓ GPG keys managed by GPG system

### Credential Handling
- ✓ Credentials loaded only when needed
- ✓ Credentials not logged or exposed in error messages
- ✓ Sensitive data redacted in output (marked as ***REDACTED***)
- ✓ Credentials cleared from memory after use

### Credential Validation
- ✓ SSH key permissions verified (must be 600)
- ✓ SSH key existence verified before use
- ✓ GitHub token format validated
- ✓ Email format validated
- ✓ GPG key ID validated against system keys

### Credential Rotation
- ✓ SSH keys rotatable annually
- ✓ GitHub tokens rotatable every 6 months
- ✓ Profile-based rotation support for multi-env setups

## Environment Profile Strategy

### Three-Tier Profile System

#### Development (`.env.dev`)
- Local machine operation
- SSH key authentication
- Less strict rules
- Developers use personal GitHub accounts
- GPG signing optional
- Example: `your.email+dev@example.com`

#### Staging (`.env.staging`)
- Pre-production testing
- May use different SSH key
- Service account or shared credentials
- GPG signing optional
- Example: `your.email+staging@example.com`

#### Production (`.env.prod`)
- Highly restricted operations
- May require HTTPS token instead of SSH
- Service account with minimal scopes
- GPG signing required for audit trail
- Example: `your.email+prod@example.com`

### Profile Selection Logic

```
1. Check ENVIRONMENT_PROFILE in .env
2. Load corresponding .env.{profile} file
3. Profile values override base .env values
4. Use final merged configuration
```

## Extension & Customization

### Adding New Auth Methods

1. Add to `AuthMethod` enum
2. Update validation logic
3. Update documentation
4. Update examples

### Adding New Credentials

1. Add to `.env.template`
2. Update `GitCredentials` dataclass
3. Update validation logic
4. Update loaders

### Custom Validation Rules

Override `_validateCredentials()` in `CredentialsLoader`:

```python
class CustomCredentialsLoader(CredentialsLoader):
    def _validateCredentials(self, config):
        # Call parent validation
        credentials = super()._validateCredentials(config)
        
        # Add custom validation
        if not self._check_team_policy(credentials):
            raise CredentialError("Violates team policy")
        
        return credentials
```

## Troubleshooting Guide

### Credential Loading Failures

| Error | Cause | Solution |
|-------|-------|----------|
| `.env` file not found | File missing | Create from template: `cp .env.template .env` |
| GIT_USER_NAME required | Missing value | Set in `.env` |
| SSH key not found | Wrong path | Verify path, expand `~` to home |
| SSH permissions too open | Key readable by others | `chmod 600 ~/.ssh/id_ed25519` |
| Invalid email format | Bad email | Update GIT_USER_EMAIL with valid format |
| GPG key not found | Key ID doesn't exist | List keys: `gpg --list-secret-keys --keyid-format LONG` |

### Agent Integration Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Agent can't load skill | Skill not registered | Check `.github/agents/gitter.agent.md` |
| Credentials not applied | Load failed silently | Check .env validation |
| Git commands fail with auth | Wrong credentials | Validate with loader: `python gitter_credentials.py` |
| Token expired | Token reached expiry | Generate new token, update `.env` |

## Testing & Validation

### Manual Testing

```bash
# Python testing
python gitter_credentials.py
python gitter_credentials.py dev
python gitter_credentials.py staging

# JavaScript testing
node gitter_credentials.js
node gitter_credentials.js prod

# Git connectivity testing
ssh -T git@github.com
git clone https://github.com/test/repo.git
```

### Automated Testing

Create `test_credentials.py`:
```python
from gitter_credentials import CredentialsLoader

def test_load_dev_profile():
    loader = CredentialsLoader()
    creds = loader.load('dev')
    assert creds.git_user_name
    assert creds.git_user_email

def test_ssh_key_exists():
    loader = CredentialsLoader()
    creds = loader.load()
    if creds.auth_method.value == 'ssh':
        assert Path(creds.ssh_key_path).exists()
```

## Maintenance Tasks

### Monthly
- Review GitHub Personal Access Token expiration date
- Verify SSH key accessibility

### Quarterly
- Rotate SSH keys if used across multiple machines
- Audit active profile usage
- Review .env configuration for outdated patterns

### Annually
- Full credential rotation (SSH keys, tokens)
- Security audit of permission levels
- Update documentation

## Related Documentation

- [SKILL.md](./SKILL.md) — Comprehensive skill definition
- [SETUP.md](./SETUP.md) — Detailed setup guide
- [README.md](./README.md) — Usage overview
- [Gitter Agent](../gitter.agent.md) — Main Gitter agent definition
- [Advisor Agent](../advisor.agent.md) — Strategic advisor agent

## Migration & Adoption

### Phase 1: Setup (Day 1)
1. Copy `.env.template` to `.env`
2. Configure credentials
3. Verify `.gitignore` includes `.env`

### Phase 2: Testing (Day 2)
1. Test credential loader
2. Test Git operations (clone, push, pull)
3. Test profile switching

### Phase 3: Team Adoption (Week 1)
1. Document team conventions
2. Share setup guide with team
3. Answer setup questions
4. Create team-specific profiles

### Phase 4: Integration (Week 2)
1. Integrate Gitter agent with skill
2. Test with real workflows
3. Document lessons learned
4. Iterate on improvements

## License & Attribution

This skill was designed to support the Gitter Git workflow agent within VS Code development environments. It follows GitHub's official security best practices for credential management.

## Version History

- **v1.0.0** (2024-01-XX)
  - Initial release
  - Python and JavaScript loaders
  - Multi-profile support
  - SSH, HTTPS, and hybrid auth
  - GPG signing support
  - Comprehensive validation
