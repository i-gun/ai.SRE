---
name: 'newrelic-alert-operations'
description: 'New Relic alert acknowledgment operations skill for fetching open unacknowledged issues scoped by policy name and acknowledging them with configured username using .env-based API key and account ID list.'
keywords: ['newrelic', 'alerts', 'issues', 'acknowledge', 'digital-operations', 'nrql']
---

# New Relic Alert Operations Skill

This skill provides New Relic NerdGraph operations for querying and acknowledging open unacknowledged issues using `.env` credentials.

## Credential Requirements

The skill expects these variables in `.env`:
- `NEWRELIC_API_KEY` — User API Key (starts with `NRAK-`)
- `NEWRELIC_ACCOUNT_IDS` — Single account ID or comma-separated list
- `NEWRELIC_USERNAME` — Username used for acknowledgments

## Supported Operations

### 1. Fetch Open Unacknowledged Alerts
Query `NrAiIssue` events across configured accounts filtered by policy name.

Behavior:
- Filter by `policyNames LIKE '%policy_name%'`
- Always exclude muted alerts (`muted != 'fullyMuted'`)
- Restrict to open/unacknowledged issue events (`event = 'ACTIVATED'`)
- Fixed time window: `SINCE 1 hour ago UNTIL now`
- Ordered by `lastModifiedTime DESC`

Method:
- `fetch_open_alerts(*, policy_name_contains, priority=None, limit=100, account_ids=None)`

### 2. Acknowledge Issue
Acknowledge an issue by `issueId`.

Behavior:
- Uses configured `NEWRELIC_USERNAME` when `username` is not passed
- Returns per-issue success/failure status

Method:
- `acknowledge_issue(*, account_id, issue_id, username=None)`

### 3. Fetch and Acknowledge Alerts (End-to-End)
Fetch matching open unacknowledged alerts and acknowledge all of them.

Method:
- `fetch_and_acknowledge_open_alerts(*, policy_name_contains, priority=None, limit=100, account_ids=None)`

Returns summary:
- alerts found
- acknowledged count
- failed count
- acknowledged items
- failed items

## Python Implementation

Use [newrelic_alerts_client.py](newrelic_alerts_client.py).

Core methods:
- `fetch_open_alerts(*, policy_name_contains, priority=None, limit=100, account_ids=None)`
- `acknowledge_issue(*, account_id, issue_id, username=None)`
- `fetch_and_acknowledge_open_alerts(*, policy_name_contains, priority=None, limit=100, account_ids=None)`

## Field Mapping Reference

`NrAiIssue` filters:
- policy filter: `policyNames LIKE '%<value>%'`
- muted filter: `muted != 'fullyMuted'`
- state filter: `event = 'ACTIVATED'`
- time window: `SINCE 1 hour ago UNTIL now`

## Validation Standards

- Fail when required env vars are missing
- Reject empty policy-name filter
- Reject invalid account IDs
- Reject empty issue IDs
- Reject empty username when both explicit username and configured `NEWRELIC_USERNAME` are missing
