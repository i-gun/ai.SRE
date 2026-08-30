---
name: 'emailer-connection'
description: 'Outlook desktop COM connection validation skill for local mailbox automation using non-secret .env configuration (no OAuth/Basic Auth credentials required).'
keywords: ['outlook', 'com', 'pywin32', 'email', 'connection', 'validation']
---

# Emailer Connection Skill

This skill validates that the local Outlook desktop client is installed, running, and reachable via COM automation before any send/read operation executes. Unlike other integrations in this repository, **no authentication secrets are stored in `.env`** — the agent rides the already-authenticated Outlook session on the local machine.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Required Environment Variables (non-secret)

- `EMAILER_MAILBOX_ADDRESS` — optional; if set, validated against the mailbox Outlook is currently signed into
- `EMAILER_WATCHED_FOLDERS` — comma-separated folder paths, default `Inbox`
- `EMAILER_ALLOWED_RECIPIENT_DOMAINS` — comma-separated domain allowlist; empty means send is blocked (fail-closed)
- `EMAILER_SEND_MODE` — `draft_review` (default) or `auto_send`
- `EMAILER_REDACTION_RULESET_PATH` — default `scripts/emailer/redaction_rules.json`

## Responsibilities

1. Verify `pywin32` is importable; raise a clear, actionable error if missing
2. Instantiate `Outlook.Application` via COM and confirm a MAPI namespace is reachable
3. If `EMAILER_MAILBOX_ADDRESS` is set, cross-check it against the signed-in account's SMTP address and fail if mismatched
4. Normalize and return `EMAILER_WATCHED_FOLDERS` and `EMAILER_ALLOWED_RECIPIENT_DOMAINS` as lists
5. Validate `EMAILER_SEND_MODE` is one of the supported values
6. Confirm the redaction ruleset file exists and is parseable JSON

## Validation Failure Conditions

- `pywin32` not installed
- Outlook is not installed, not running, or COM automation is blocked (e.g., Object Model Guard/security software)
- `EMAILER_MAILBOX_ADDRESS` set but does not match the signed-in Outlook account
- `EMAILER_SEND_MODE` set to an unsupported value
- Redaction ruleset file missing or invalid JSON

## Architectural Constraint (must be surfaced to the user)

This connection is **local-desktop-only**: it requires Outlook to be installed, running, and signed in on the same Windows machine executing the agent. It cannot run unattended on a server, in CI, or on a machine without an interactive Outlook session.

## Security Rules

- Never attempt to read or store Outlook account passwords — none are needed
- Never bypass `EMAILER_ALLOWED_RECIPIENT_DOMAINS` fail-closed behavior when the allowlist is empty
- Never log full message bodies; log only counts/subjects/entry IDs

## Integration

Primary consumer:
- `emailer-mail-operations`

Implementation file:
- `outlook_env.py`
