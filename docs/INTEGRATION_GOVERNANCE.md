---
title: Integration Governance & Best Practices
description: Guidelines for using agents, skills, credentials, and script placement in ai.SRE project
---

# Integration Governance & Best Practices

This document establishes governance rules for working with agents, skills, integrations, and script placement in the ai.SRE project.

## Core Principles

### 1. Agent/Skill Delegation First
**When an agent or skill exists for an operation, use it directly rather than creating workarounds.**

**Examples:**
- ✅ Use `@ServiceNow` agent for incident operations → automatically handles credential loading, API calls, and error handling
- ✅ Use `@Jira` agent for issue operations → built-in validation and lifecycle management
- ❌ DO NOT create custom Python scripts as replacements when the skill provides the functionality

**Benefits:**
- Credentials handled securely by skill loader (more robust than custom parsing)
- Agent automatically respects scope constraints and governance rules
- Error handling and retry logic already implemented
- Audit trail maintained by agent/skill layer

### 2. Environment Credentials (`.env` File)
**All integrations MUST read credentials from `.env` in the project root. Never hardcode or request manual input.**

**Configuration:**
```bash
# Required variables for ServiceNow integration
SERVICENOW_HOST=https://your-instance.service-now.com
SERVICENOW_USERNAME=integration_user
SERVICENOW_PASSWORD=secure_password_with_special_chars_preserved
SERVICENOW_ASSIGNMENT_GROUPS=Group1,Group2

# Required variables for Jira integration
JIRA_HOST=https://your-domain.atlassian.net
JIRA_USERNAME=automation@example.com
JIRA_API_TOKEN=api_token_value

# Required variables for New Relic
NEWRELIC_API_KEY=key_value
NEWRELIC_ACCOUNT_IDS=id1,id2
```

**Security Rules:**
- `.env` is in `.gitignore` — NEVER commit credentials to version control
- Use `.env.example` (sanitized) and `.env.template` for documentation
- `.env` file read by skill/agent loaders automatically
- Special characters in passwords are preserved when using agent delegation
- Store `.env` in secure location accessible only to intended users

**Credential Loading:**
- Skills use environment variable parsing that respects context (comments, quotes, special chars)
- Do NOT use `python-dotenv` directly in ad-hoc scripts (limited parsing)
- Always delegate to agent/skill for credential loading

### 3. Script Placement Hierarchy

**A. Temporary/Diagnostic Scripts → `artifacts/`**

Use for one-time exploration, debugging, or proof-of-concept work.

```
artifacts/
├── test_connection_diagnostic.py          # Temporary connectivity test
├── debug_incident_fields.ps1             # Ad-hoc field inspection
└── explore_incident_pattern.py           # Quick analysis script
```

**Rules:**
- Remove immediately after use/troubleshooting is complete
- Never commit temporary scripts to repository
- Do NOT use for production operations
- Clearly name to indicate temporary nature (e.g., `debug_`, `test_`, `tmp_`)

**Example workflow:**
```bash
# Create temporary diagnostic
artifacts/test_connection.py       # Create for debugging
# Run diagnostic
python artifacts/test_connection.py
# Remove after issue resolved
rm artifacts/test_connection.py
```

**B. Reusable Scripts → `scripts/<service>/<operation>.py`**

Use for scripts that support multiple workflows or are part of operational procedures.

```
scripts/
├── servicenow/
│   ├── batch_resolve_triggered_incidents.py
│   ├── create_issue_from_problem.py
│   └── common.py                           # Shared helpers
├── jira/
│   ├── search_issues.py
│   ├── create_issues_from_problems.py
│   └── common.py
├── newrelic/
│   ├── analyze_trends.py
│   ├── root_cause_analysis.py
│   ├── search_logs.py
│   ├── trace_dependencies.py
│   └── common.py
└── orchestration/
    └── newrelic_servicenow_alert_orchestrator.py
```

**Rules:**
- Scripts here are production-ready and documented
- Must include credential loading from `.env` (via skill bootstrap)
- Should follow service-oriented organization
- Include `common.py` for shared bootstrap and helper functions
- Document expected `.env` variables at top of script
- Mutating scripts must default to read-only mode and require an explicit execution flag
- Batch mutation scripts must enforce a reviewed incident-count gate before applying writes
- Add to repository with version control

**Example structure (servicenow/common.py):**
```python
#!/usr/bin/env python3
"""Shared bootstrap helpers for ServiceNow operational scripts."""

from pathlib import Path
from dotenv import load_dotenv
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INCIDENT_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-incident-operations"

def bootstrap(*, include_auth: bool = False):
    """Load .env and register skill import paths."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    skill_paths = [INCIDENT_SKILL_PATH]
    for path in skill_paths:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    return PROJECT_ROOT
```

### 4. Agent/Skill Adherence

**Respect the scope and description of each agent/skill. Do NOT create workarounds.**

**Service Integration Matrix:**

| Operation | Recommended | Why |
|-----------|------------|-----|
| Fetch ServiceNow incidents | `@ServiceNow` agent | Automatic scope enforcement, credential handling |
| Resolve ServiceNow incidents | `@ServiceNow` agent | Full lifecycle management, validation |
| Create Jira issues | `@Jira` agent | Project validation, field mapping |
| Search Confluence | `@Confluence` agent | CQL support, space scoping |
| Parse/load credentials | Agent/Skill | Robust `.env` handling, context awareness |
| Custom script if needed | Only after skill assessment | Script goes to `scripts/` or `artifacts/` per rules |

**Escalation:**
- If no agent/skill exists for needed operation, create reusable script in `scripts/<service>/` 
- Document why agent delegation was insufficient
- Add script to version control if permanent

### 5. Documentation Standards

**Every integration should document:**

1. **Credential requirements** — List all `.env` variables needed
2. **Security model** — How credentials are stored/loaded
3. **Scope constraints** — What operations are in/out of scope
4. **Usage examples** — How to invoke via agent or script
5. **Error handling** — What errors to expect and how to resolve
6. **Audit trail** — How operations are logged/tracked

**Example (for new skill):**
```markdown
# ServiceNow XYZ Operation Skill

## Credential Requirements
Requires in `.env`:
- SERVICENOW_HOST
- SERVICENOW_USERNAME
- SERVICENOW_PASSWORD
- SERVICENOW_ASSIGNMENT_GROUPS

## Security
- Credentials never logged
- Skill loader validates before API calls
- `.env` in `.gitignore`

## Scope
- Incidents in designated groups only
- Active incidents only (excludes Resolved)
- Read-only unless explicitly authorized

## Usage
Use `@ServiceNow` agent: "@ServiceNow, [operation description]"

## Scripts
Permanent scripts at: `scripts/servicenow/operation_name.py`
```

## Workflow Examples

### Example 0: AzureGit Project/Repository Mapping Refresh

**Problem:** Need latest Azure DevOps project/repository mapping for scoped analysis.

**Correct Approach:**
```bash
python scripts/azuregit/fetch_repo_map.py --force-refresh
```

**Why:**
- Uses AzureGit skill bootstrap and `.env` credentials
- Writes normalized artifact to `artifacts/azuregit_repo_map.json`
- Avoids stale mapping during repository discovery and reporting
- Supports cache-based refresh via `--max-age-hours` when fresh fetch is not required

### Example 1: Batch Incident Resolution

**Problem:** Resolve 182 "Triggered : " incidents with specific fields.

**✅ Correct Approach:**
```bash
# Use @ServiceNow agent with prepared prompt
@ServiceNow, fetch all active incidents...
```

**Why:**
- Agent handles credential loading from `.env` securely
- API calls, validation, and error handling built-in
- 182 incidents resolved with 100% success
- No custom scripts needed

**❌ Incorrect Approach (what was attempted):**
```bash
# Create custom Python script using python-dotenv
python batch_resolve_triggered_incidents.py
# Result: Credentials parsed incorrectly (# treated as comment)
# Problem: Reinvented the wheel when @ServiceNow skill exists
```

**Key Learning:** Always delegate to agent first; only create scripts if skill doesn't exist.

### Example 2: Diagnostic/Troubleshooting

**Problem:** API connection returning 401, need to debug credentials.

**✅ Correct Approach:**
```bash
# Create temporary diagnostic script in artifacts/
artifacts/test_sn_connection.py    # Create for debugging
python artifacts/test_sn_connection.py  # Run diagnostic
# [Identify that password # was being truncated]
rm artifacts/test_sn_connection.py     # Remove after resolved
```

**Why:**
- Temporary scripts go to `artifacts/`
- Cleaned up after diagnostic use
- Not committed to repository

**Permanent Alternative (if needed repeatedly):**
```bash
# Keep in artifacts/ unless adopted as a long-term operational command
artifacts/servicenow/archive/test_connection.py
```

## Archive Retention Policy

- `artifacts/servicenow/archive/` is for historical diagnostics and one-off operational scripts kept temporarily for traceability.
- Review archived scripts during adjacent cleanup work and remove entries that are no longer referenced by docs, tickets, or active runbooks.
- Do not promote archived scripts back into `scripts/` without parameterization, documentation, and explicit execution gates.

### Example 3: Creating Reusable Operational Script

**Problem:** Need permanent script to search ServiceNow incidents with custom filter.

**✅ Correct Approach:**
```bash
# Place in scripts/servicenow/ per hierarchy
scripts/servicenow/search_incidents_by_pattern.py

# At top of script:
"""
Dependencies:
- Requires SERVICENOW_HOST, SERVICENOW_USERNAME, SERVICENOW_PASSWORD in .env
- Loads credentials via skill bootstrap
"""

# Use common.py for credential loading
from common import bootstrap
bootstrap()
from servicenow_client import ServiceNowClient
```

**Why:**
- Organized per service (servicenow/)
- Uses bootstrap pattern to load `.env` credentials securely
- Reusable and versioned

## Validation Checklist

Before creating a new script or integration:

- [ ] Does an agent/skill already exist for this operation?
  - YES → Use `@AgentName` delegation
  - NO → Continue to next check
- [ ] Is this a temporary diagnostic/test?
  - YES → Place in `artifacts/` and plan removal
  - NO → Continue to next check
- [ ] Is this reusable across multiple workflows?
  - YES → Place in `scripts/<service>/` 
  - NO → Still place in `scripts/<service>/` if part of operational library
- [ ] Does the script read credentials?
  - YES → Use `.env` via common.py bootstrap
  - NO → Document why credentials not needed
- [ ] Is this documented?
  - YES → Include in version control
  - NO → Add documentation before commit
- [ ] Will this be maintained long-term?
  - YES → Add to scripts library and document
  - NO → Use `artifacts/` for temporary work

## Security Audit Checklist

For all integrations:

- [ ] Credentials sourced from `.env` only
- [ ] `.env` in `.gitignore` (never committed)
- [ ] No hardcoded API keys, passwords, or tokens
- [ ] `.env.example` or `.env.template` provided (sanitized)
- [ ] Scripts/skills do not log credential values
- [ ] API calls use Basic Auth or OAuth as appropriate
- [ ] Request/response logging masks sensitive fields

## Related Documentation

- [Git Hooks Implementation](GIT_HOOKS_IMPLEMENTATION.md) — Automated commit processing
- [Gitter Credentials Skill](GITTER_CREDENTIALS_SKILL_SUMMARY.md) — Git credential management
- [New Relic ServiceNow Orchestrator](NEWRELIC_SERVICENOW_ORCHESTRATOR_USAGE.md) — Multi-service workflows
- [Agent Descriptions](.github/agents/) — Detailed scope per agent
- [Skill Descriptions](.github/skills/) — Integration details and requirements

## Summary

| Scenario | Action | Location |
|----------|--------|----------|
| Incident resolution needed | Use `@ServiceNow` agent | Direct delegation |
| One-time connectivity test | Create script | `artifacts/` (temp) |
| Recurring incident search | Create script | `scripts/servicenow/` |
| Batch multi-service workflow | Use orchestrator | `scripts/orchestration/` |
| Diagnostic debugging | Create script | `artifacts/` (remove after) |
| Integration unavailable | Create reusable script | `scripts/<service>/` |

**Default: Always try agent/skill first. Create scripts only if no suitable agent exists.**
