---
name: 'confluence-authentication'
description: 'Confluence Cloud authentication and configuration validation skill using Jira .env credentials plus one or more Confluence space keys for scoped knowledge operations.'
keywords: ['confluence', 'authentication', 'env', 'space', 'validation']
---

# Confluence Authentication Skill

This skill validates and normalizes Confluence access configuration from `.env` before Confluence knowledge operations are executed.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Required Environment Variables

- `JIRA_HOST`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`
- `CONFLUENCE_SPACE_KEY` — single key or comma-separated list (e.g. `PLATFORM,DEV,OPS`)

## Responsibilities

1. Validate required credential fields exist
2. Validate host format (`http://` or `https://`)
3. Normalize host by removing trailing slash
4. Parse `CONFLUENCE_SPACE_KEY` as a comma-separated list and normalize each key to uppercase
5. Validate that at least one non-empty space key is present
6. Provide safe config object for downstream skills
7. Protect secrets from logs and user-facing messages

## Validation Failure Conditions

- Missing one or more required variables
- Invalid host format
- Empty username, API token, or space key list

## Security Rules

- Never print plaintext API tokens
- Never include credentials in stack traces shown to users
- Never write secrets to generated files

## Integration

Primary consumer:
- `confluence-knowledge-operations`

Implementation file:
- `confluence_env.py`
