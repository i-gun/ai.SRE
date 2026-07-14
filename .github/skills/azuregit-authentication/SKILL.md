---
name: 'azuregit-authentication'
description: 'Azure DevOps Git authentication and configuration validation skill using .env-based organization, scoped project list, and PAT for read-only API access.'
keywords: ['azure-devops', 'azuregit', 'authentication', 'env', 'pat', 'validation']
---

# AzureGit Authentication Skill

This skill validates and normalizes Azure DevOps Git credentials from `.env` before repository and code discovery operations are executed.

## Required Environment Variables

- `AZURE_ORG`
- `AZURE_PROJECT` (comma-separated list of allowed project names)
- `AZURE_PAT`

Optional:
- `AZURE_API_VERSION` (defaults to `7.1`)

## Responsibilities

1. Validate required credential fields exist
2. Parse and deduplicate configured project allowlist
3. Validate non-empty PAT and organization name
4. Normalize API version (default to `7.1` when omitted)
5. Provide a safe config object for downstream skills
6. Protect secrets from logs and user-facing messages

## Validation Failure Conditions

- Missing one or more required variables
- Empty or invalid project list after parsing
- Empty organization or PAT values
- Empty API version value when explicitly set

## Security Rules

- Never print plaintext PAT
- Never include credentials in stack traces shown to users
- Never write secrets to generated files

## Integration

Primary consumer:
- `azuregit-repository-operations`

Implementation file:
- `azuregit_env.py`
