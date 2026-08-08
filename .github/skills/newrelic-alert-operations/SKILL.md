---
name: 'newrelic-alert-operations'
description: 'New Relic alert acknowledgment operations skill for fetching open unacknowledged issues scoped to account 1679802 and policies starting with Digital Operations, then acknowledging them with platform-resolved username.'
keywords: ['newrelic', 'alerts', 'issues', 'acknowledge', 'digital-operations', 'nrql']
---

# New Relic Alert Operations Skill

This skill provides New Relic NerdGraph operations for querying and acknowledging open unacknowledged issues using `.env` credentials.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Credential Requirements

The skill expects these variables in `.env`:
- `NEWRELIC_API_KEY` — User API Key (starts with `NRAK-`)
- `NEWRELIC_ACCOUNT_IDS` — Single account ID or comma-separated list

Username is resolved from New Relic platform identity using `NEWRELIC_API_KEY`.

## Supported Operations

### 1. Fetch Open Unacknowledged Alerts
Query alert events across configured accounts filtered by policy name (`NrAiIssue` with `NrAiIncident` compatibility).

Behavior:
- Filter by `policyNames LIKE 'Digital Operations%'` by default
- Policy lookup uses **starts with** semantics (prefix match)
- Accommodates keyset-compatible names from `NrAiIncident` queries when needed:
  - `policyNames` / `policyName`
  - `conditionNames` / `conditionName`
  - `issueId` / `incidentId`
  - `issueLink` / `incidentLink`
- Restrict lookup scope to account `1679802` only
- Always exclude muted alerts (supports boolean/numeric/string muted representations)
- For `NrAiIncident`, open detection uses: `muted = false AND (closeTime IS NULL OR closeTime = 0)`
- For `NrAiIssue`, open-style detection uses event state (`ACTIVATED`/`OPEN`/`CREATED`)
- Default time window: `SINCE 3 hours ago UNTIL now`
- `since` is configurable per prompt/method call
- Ordered by `lastModifiedTime DESC`

Method:
- `fetch_open_alerts(*, policy_name_starts_with='Digital Operations', priority=None, since='3 hours ago', limit=100, account_ids=None)`

### 2. Acknowledge Issue
Acknowledge an issue by `issueId`.

Behavior:
- Uses NerdGraph mutation `aiIssuesAckIssue(accountId, issueId)`
- Resolves username from New Relic platform using `NEWRELIC_API_KEY` when `username` is not passed
- If `issueId` is missing but `incidentId` is present, resolves `issueId` via `NrAiIssue` lookup using `contains(incidentIds, '<incidentId>')`
- Does not acknowledge directly by `incidentId` with `aiIssuesAckIssue`
- Returns per-issue success/failure status

Method:
- `acknowledge_issue(*, account_id, issue_id, username=None)`

### 3. Fetch and Acknowledge Alerts (End-to-End)
Fetch matching open unacknowledged alerts and acknowledge all of them.

Method:
- `fetch_and_acknowledge_open_alerts(*, policy_name_starts_with='Digital Operations', priority=None, since='3 hours ago', limit=100, account_ids=None)`

Returns summary:
- alerts found
- acknowledged count
- failed count
- acknowledged items
- failed items

## Python Implementation

Use [newrelic_alerts_client.py](newrelic_alerts_client.py).

Core methods:
- `fetch_open_alerts(*, policy_name_starts_with='Digital Operations', priority=None, since='3 hours ago', limit=100, account_ids=None)`
- `acknowledge_issue(*, account_id, issue_id, username=None)`
- `fetch_and_acknowledge_open_alerts(*, policy_name_starts_with='Digital Operations', priority=None, since='3 hours ago', limit=100, account_ids=None)`

## Field Mapping Reference

`NrAiIssue` filters:
- policy filter: `(policyNames LIKE '<prefix>%' OR policyName LIKE '<prefix>%')`
- account scope: `1679802` only
- muted filter: keyset-safe muted exclusion across boolean/numeric/string variants
- state filter: open-style events (`ACTIVATED`/`OPEN`/`CREATED`)
- default time window: `SINCE 3 hours ago UNTIL now` (configurable via `since`)

`NrAiIncident` open filters:
- policy filter: `(policyName LIKE '<prefix>%' OR policyNames LIKE '<prefix>%')`
- muted filter: `muted = false`
- open filter: `(closeTime IS NULL OR closeTime = 0)`

## Validation Standards

- Fail when required env vars are missing
- Reject empty policy-name filter
- Reject invalid account IDs
- Reject account scope outside `1679802`
- Reject empty issue IDs
- Fail if platform username cannot be resolved from API key and no explicit username is provided
