---
name: 'servicenow-authentication'
description: 'ServiceNow authentication and configuration validation skill using .env-based host, username, and password for secure API access.'
keywords: ['servicenow', 'authentication', 'env', 'credentials', 'validation']
---

# ServiceNow Authentication Skill

This skill validates and normalizes ServiceNow credentials from `.env` before operational incident actions are executed.

## Required Environment Variables

- `SERVICENOW_HOST`
- `SERVICENOW_USERNAME`
- `SERVICENOW_PASSWORD`
- `SERVICENOW_ASSIGNMENT_GROUPS` (comma-separated list of allowed assignment group names or sys_ids)

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
- Empty username or password
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
