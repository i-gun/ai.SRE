---
name: 'servicenow-authentication'
description: 'ServiceNow authentication and configuration validation using environment-selected Basic or OAuth client credentials for service-account API access.'
keywords: ['servicenow', 'authentication', 'env', 'credentials', 'validation']
---

# ServiceNow Authentication Skill

This skill validates and normalizes ServiceNow credentials from `.env` before operational incident actions are executed.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Required Environment Variables

- `SERVICENOW_HOST`
- `SERVICENOW_AUTH_MODE`: `basic` (default) or `oauth_client_credentials`
- Basic only: `SERVICENOW_USERNAME`, `SERVICENOW_PASSWORD`
- OAuth only: `SERVICENOW_CLIENT_ID`, `SERVICENOW_CLIENT_SECRET`
- Optional OAuth: `SERVICENOW_TOKEN_URL`, `SERVICENOW_OAUTH_SCOPE`,
  `SERVICENOW_OAUTH_CLIENT_AUTH_METHOD`
- `SERVICENOW_ASSIGNMENT_GROUPS` (comma-separated list of allowed assignment group names or sys_ids)

See `docs/SERVICENOW_AUTHENTICATION.md`. OAuth requires HTTPS. Username may remain
as a workflow identity; its password is not required or sent in OAuth mode.

## Responsibilities

1. Validate required credential fields exist
2. Validate host format (`http://` or `https://`)
3. Normalize host by removing trailing slash
4. Provide safe config object for downstream skills
5. Protect secrets from logs and user-facing messages
6. Parse and validate designated assignment groups allowlist

## Validation Failure Conditions

- Missing one or more required variables
- Invalid host format
- Empty username or password in Basic mode
- Invalid mode, missing OAuth credentials, or unsafe OAuth token URL
- Missing or empty assignment group allowlist

## Security Rules

- Never print plaintext password
- Never include credentials in stack traces shown to users
- Never write secrets to generated files

## Integration

Primary consumer:
- `servicenow-incident-operations`

Implementation file:
- `servicenow_env.py`
