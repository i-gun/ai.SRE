---
name: 'azuregit-authentication'
description: 'Azure DevOps Git authentication and configuration validation skill using .env-based organization, scoped project list, and PAT for read-only API access.'
keywords: ['azure-devops', 'azuregit', 'authentication', 'env', 'pat', 'validation']
---

# AzureGit Authentication Skill

This skill validates and normalizes Azure DevOps Git credentials from `.env` before repository and code discovery operations are executed.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

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
