---
name: 'jira-authentication'
description: 'Jira Cloud authentication and configuration validation skill using .env-based host, username, and API token for secure REST API access.'
keywords: ['jira', 'authentication', 'env', 'token', 'validation']
---

# Jira Authentication Skill

This skill validates and normalizes Jira Cloud credentials from `.env` before operational project, dashboard, or issue actions are executed.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Required Environment Variables

- `JIRA_HOST`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`

## Responsibilities

1. Validate required credential fields exist
2. Validate host format (`http://` or `https://`)
3. Normalize host by removing trailing slash
4. Provide safe config object for downstream skills
5. Protect secrets from logs and user-facing messages

## Validation Failure Conditions

- Missing one or more required variables
- Invalid host format
- Empty username or API token

## Security Rules

- Never print plaintext API tokens
- Never include credentials in stack traces shown to users
- Never write secrets to generated files

## Integration

Primary consumer:
- `jira-issue-operations`

Implementation file:
- `jira_env.py`