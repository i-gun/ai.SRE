# Project Overview

This project contains GitHub Copilot AI tools agents and skills for advanced development workflows.

## Project Structure

```
├── .github/
│   ├── agents/              # AI agent definitions
│   │   ├── advisor.agent.md
│   │   ├── azuregit.agent.md
│   │   ├── confluence.agent.md
│   │   ├── gitter.agent.md
│   │   ├── jira.agent.md
│   │   └── servicenow.agent.md
│   └── skills/              # Domain-specific skill implementations
│       └── gitter-credentials/
│           ├── SKILL.md
│           ├── SETUP.md
│           ├── README.md
│           ├── ARCHITECTURE.md
│           ├── gitter_credentials.py
│           └── gitter_credentials.js
│       └── servicenow-authentication/
│           ├── SKILL.md
│           └── servicenow_env.py
│       └── servicenow-incident-operations/
│           ├── SKILL.md
│           ├── README.md
│           └── servicenow_client.py
│       └── jira-authentication/
│           ├── SKILL.md
│           └── jira_env.py
│       └── jira-issue-operations/
│           ├── SKILL.md
│           ├── README.md
│           └── jira_client.py
│       └── confluence-authentication/
│           ├── SKILL.md
│           └── confluence_env.py
│       └── confluence-knowledge-operations/
│           ├── SKILL.md
│           ├── README.md
│           └── confluence_client.py
│       └── azuregit-authentication/
│           ├── SKILL.md
│           └── azuregit_env.py
│       └── azuregit-repository-operations/
│           ├── SKILL.md
│           ├── README.md
│           └── azuregit_client.py
├── docs/                    # Project and implementation documentation
│   ├── GIT_HOOKS_IMPLEMENTATION.md
│   └── GITTER_CREDENTIALS_SKILL_SUMMARY.md
├── scripts/                 # Operational and diagnostic scripts
│   └── confluence/
│       ├── common.py
│       ├── search_space_pages.py
│       ├── search_content.py
│       └── build_service_flow_graph.py
│   └── servicenow/
│       ├── common.py
│       ├── create_issue_from_problem.py
│       ├── diagnose_issue_table.py
│       ├── execute_incident_operations.py
│       ├── resolve_incident_script.py
│       ├── search_final_resolved_incidents.py
│       ├── search_resolved_incidents.py
│       └── test_query_variations.py
├── tests/
│   └── test_confluence_client.py
├── git-hooks/               # Hook sources tracked in repo
├── .env.template            # Environment configuration template
├── .env.example             # Example configuration
├── .gitignore               # Git security excludes
└── README.md                # This file
```

## Agents

### Advisor Agent
Senior advisor specializing in GitHub Copilot AI tools architecture and enterprise adoption strategies.

### Gitter Agent
Expert Git workflow strategist for repository optimization and team collaboration.

### ServiceNow Agent
Incident lifecycle operations agent for secure ServiceNow communication using `.env` credentials, including incident creation, assignment/reassignment, priority changes, and incident-to-problem linkage.

### Jira Agent
Jira Cloud operations agent for project lookup, dashboard discovery, issue search, fetch, create, update, comment, and issue linking using `.env` credentials.

### Confluence Agent
Confluence knowledge operations agent for scoped page browsing, CQL search, content retrieval, cross-page service relationship discovery, and service-flow graph generation.

### AzureGit Agent
Azure DevOps Git read-only operations agent for scoped multi-project repository lookup, code search, and lightweight codebase analysis using `.env` credentials.

## Skills

### Gitter Credentials Skill
Secure credential management for Git operations with support for SSH keys, tokens, and GPG signing.

### ServiceNow Authentication Skill
Credential validation and normalization for ServiceNow host, username, and password loaded from `.env`.

### ServiceNow Incident Operations Skill
ServiceNow Incident, Problem, and Issue Table API operations for scoped incident retrieval/creation, assignment/reassignment, work-note updates, matrix-based priority changes, incident-to-problem linkage, issue-from-problem creation, and validated resolution workflows.

### Jira Authentication Skill
Credential validation and normalization for Jira Cloud host, username, and API token loaded from `.env`.

### Jira Issue Operations Skill
Jira Cloud Project, Dashboard, and Issue API operations for search, fetch, create, update, comment, and issue-link workflows.

### Confluence Authentication Skill
Credential validation and normalization for Confluence access using Jira Cloud host, username, API token, and a dedicated Confluence space key from `.env`.

### Confluence Knowledge Operations Skill
Confluence Cloud content operations for space browsing, CQL search, page retrieval, schema/service signal extraction, relationship linking, and service-flow graph construction.

### AzureGit Authentication Skill
Credential validation and normalization for Azure DevOps organization, scoped project allowlist, PAT, and optional API version loaded from `.env`.

### AzureGit Repository Operations Skill
Read-only Azure DevOps Git operations for repository discovery, file listing, content search, and lightweight repository structure analysis across scoped projects.

### Confluence Scripts & Tests
- Helper scripts in `scripts/confluence/` support page browsing, CQL search, and service-flow graph generation.
- Unit tests in `tests/test_confluence_client.py` validate graph extraction and CQL space-scoping behavior.

## File Changes Log

This section is automatically maintained by pre-commit hooks.

