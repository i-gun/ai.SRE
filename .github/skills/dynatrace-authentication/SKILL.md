---
name: 'dynatrace-authentication'
description: 'Dynatrace authentication and configuration validation skill using .env-based environment URL and API token for secure Grail/DQL and Problems v2 access.'
keywords: ['dynatrace', 'authentication', 'env', 'api-token', 'environment', 'validation']
---

# Dynatrace Authentication Skill

This skill validates and normalizes Dynatrace credentials from `.env` before log search, trend analysis, dependency traversal, problem search, and root-cause analysis operations are executed.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Required Environment Variables

- `DYNATRACE_ENVIRONMENT_URL` — Environment base URL, no trailing slash
  (e.g. `https://abc12345.live.dynatrace.com` for SaaS, or the Managed cluster equivalent).
  Generate a token at: `{DYNATRACE_ENVIRONMENT_URL}/ui/apps/dynatrace.classic.tokens`
- `DYNATRACE_API_TOKEN` — API Token (Settings > Access Tokens). Required scopes:
  `storage:logs:read`, `storage:events:read`, `storage:entities:read`, `problems.read`,
  `problems.write` (comments only)
- `DYNATRACE_USERNAME` — Username recorded when posting audit-trail comments on problems

## Responsibilities

1. Validate required credential fields exist
2. Validate `DYNATRACE_ENVIRONMENT_URL` uses `https://` and has a non-empty host
3. Validate `DYNATRACE_API_TOKEN` is non-empty (warn, do not fail, if it doesn't start
   with `dt0c01.` since Managed tenants may use a different token format)
4. Validate `DYNATRACE_USERNAME` is non-empty
5. Provide a safe config object for downstream skills
6. Protect the API token from logs and user-facing messages

## Validation Failure Conditions

- Missing `DYNATRACE_ENVIRONMENT_URL`, `DYNATRACE_API_TOKEN`, or `DYNATRACE_USERNAME`
- `DYNATRACE_ENVIRONMENT_URL` missing `https://` scheme or host
- Empty API token string

## Security Rules

- Never print the plaintext API token
- Never include credentials in stack traces shown to users
- Never write secrets to generated files

## Integration

Primary consumers:
- `dynatrace-monitoring-operations`
- `dynatrace-problem-operations`

Implementation file:
- `dynatrace_env.py`
