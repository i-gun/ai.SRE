---
name: 'newrelic-log-operations'
description: 'New Relic log operations skill for NRQL-driven log search, alert search, trend analysis, multi-account dependency traversal, root cause analysis, and service degradation investigation using .env-based API key and account ID list.'
keywords: ['newrelic', 'nrql', 'logs', 'alerts', 'rca', 'dependencies', 'trends', 'accounts']
---

# New Relic Log Operations Skill

This skill provides New Relic NerdGraph/NRQL operations for log search, trend detection, cross-account dependency traversal, and root-cause analysis using `.env` credentials.

## Credential Requirements

The skill expects these variables in `.env`:
- `NEWRELIC_API_KEY` — User API Key (starts with `NRAK-`). Generate at: https://one.newrelic.com/api-keys
- `NEWRELIC_ACCOUNT_IDS` — Single account ID or comma-separated list (e.g. `1234567` or `1234567,2345678`)

Security rules:
- Do not log credential values
- Do not commit `.env`
- Use `.env.template` for structure and `.env.example` for sanitized examples

## Supported Operations

### 1. Search Logs
Query `Log` events across one or more accounts using text and filter conditions.

Validation:
- Limit must be greater than zero

Behavior:
- Filter by message content, severity level (`ERROR`, `CRITICAL`, etc.), and service name
- Scope to all configured accounts by default; accepts optional `account_ids` override
- Returns per-account log result lists

### 2. Analyze Log Trends
Return time-series log counts, optionally faceted, to surface anomaly windows.

Behavior:
- Configurable `timeseries` bucket size (default `10 minutes`)
- Optional `facet` dimension (e.g. `level`, `service.name`)
- Scope by message content and/or service name
- Returns per-account bucketed counts

### 3. Trace Service Dependencies
Discover upstream callers and downstream dependencies of a named service using `Span` data.

Behavior:
- Queries span data for `client`-kind spans (downstream) and `server`-kind spans (upstream)
- Detects database system calls (`db.system`)
- Aggregates across all configured accounts
- Returns `upstream_services`, `downstream_services`, `databases`, and a `dependency_graph` (nodes + edges)

### 4. Root Cause Analysis
Identify the most probable root cause of service degradation or error spikes.

Behavior:
1. Collect error-level logs for the target service in the specified window
2. Collect baseline error logs from the previous equivalent window for novelty scoring
3. Extract and normalize repetitive error message patterns
4. Query downstream dependency services for correlated errors
5. Score candidates by: error frequency × severity weight × novelty multiplier
6. Return ranked `rca_candidates`, `root_cause` summary, `recommendation`, and `escalation_points`

### 5. Run NRQL
Execute arbitrary NRQL queries against one or all configured accounts.

Validation:
- NRQL must be non-empty

Behavior:
- Single-account execution via `run_nrql(account_id=..., nrql=...)`
- Multi-account execution via `run_nrql_across_accounts(nrql=...)` — uses a single batched NerdGraph request with account aliases

### 6. Search Alerts
Search `NrAiIssue` alert events across configured accounts with policy name, priority, and mute-state filters.

Validation:
- Limit must be greater than zero

Behavior:
- Filter by `policy_name_contains` (substring match on `policyNames`), `priority` (e.g. `CRITICAL`), and time window
- **Fully-muted issues are excluded by default** (`exclude_muted=True`); pass `exclude_muted=False` to include them
- Scope to all configured accounts by default; accepts optional `account_ids` override
- Returns per-account result lists ordered by `lastModifiedTime DESC`

### 7. Generate Local Service Catalog
Generate local `data/` service catalog files required by repository/documentation mapping workflows.

Behavior:
- Preferred path is `@NewRelic` delegation
- Non-chat automation fallback is `python scripts/newrelic/generate_service_catalog.py`
- Produces:
	- `data/newrelic_apm_service_names_1679802.txt`
	- `data/newrelic_apm_service_names_1679802.csv`
	- `data/newrelic_apm_services_1679802.json`

## API Endpoints Used

- `POST https://api.newrelic.com/graphql` — NerdGraph for all NRQL and metadata queries

## Event Types Queried

| Event Type | Usage |
|---|---|
| `Log` | Log search, trend analysis, RCA error collection |
| `Span` | Service dependency traversal (upstream/downstream) |
| `NrAiIssue` | Alert search across policies with mute-state filtering |

## RCA Candidate Scoring

| Signal | Weight Contribution |
|---|---|
| Error count | Proportional (higher count = higher score) |
| Severity: CRITICAL/FATAL | ×4 multiplier |
| Severity: ERROR | ×2 multiplier |
| Novelty: new pattern (no baseline match) | ×2 multiplier |
| Novelty: count ≥ 2× baseline | ×1.5 multiplier |
| Dependency error (downstream service) | error_count × 1.5 |

## Validation Standards

- Do not perform operations when auth validation fails
- Do not send empty NRQL queries
- Do not resolve account IDs when none are configured or provided
- Do not infer high-confidence root causes without evidence

## Python Implementation

Use [newrelic_client.py](newrelic_client.py) for operational code.

Core methods:
- `run_nrql(*, account_id, nrql)`
- `run_nrql_across_accounts(*, nrql, account_ids=None)`
- `search_logs(*, message_contains, severity, service, since, limit, account_ids=None)`
- `search_alerts(*, policy_name_contains, priority, since, exclude_muted=True, limit, account_ids=None)`
- `analyze_log_trends(*, message_contains, service, since, timeseries, facet, account_ids=None)`
- `trace_service_dependencies(*, service, since, account_ids=None)`
- `root_cause_analysis(*, service, since, account_ids=None)`
