---
name: 'newrelic-authentication'
description: 'New Relic authentication and configuration validation skill using .env-based API key and comma-separated account ID list for secure NerdGraph and NRQL access.'
keywords: ['newrelic', 'authentication', 'env', 'api-key', 'account', 'validation']
---

# New Relic Authentication Skill

This skill validates and normalizes New Relic credentials from `.env` before log search, trend analysis, dependency traversal, and root-cause analysis operations are executed.

## Required Environment Variables

- `NEWRELIC_API_KEY` — User API Key (starts with `NRAK-`). Generate at: https://one.newrelic.com/api-keys
- `NEWRELIC_ACCOUNT_IDS` — Single account ID or comma-separated list (e.g. `1234567` or `1234567,2345678,3456789`)

## Responsibilities

1. Validate required credential fields exist
2. Validate API key is non-empty
3. Parse `NEWRELIC_ACCOUNT_IDS` as a comma-separated list of integers
4. Validate that each account ID is a positive integer
5. Validate that at least one account ID is present
6. Provide a safe config object for downstream skills
7. Protect the API key from logs and user-facing messages

## Validation Failure Conditions

- Missing `NEWRELIC_API_KEY` or `NEWRELIC_ACCOUNT_IDS`
- Empty API key string
- Non-integer value in the account ID list
- Empty account ID list after parsing

## Security Rules

- Never print the plaintext API key
- Never include credentials in stack traces shown to users
- Never write secrets to generated files

## Integration

Primary consumer:
- `newrelic-log-operations`

Implementation file:
- `newrelic_env.py`
