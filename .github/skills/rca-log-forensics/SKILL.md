---
name: 'rca-log-forensics'
description: 'Multi-account New Relic log forensics skill for deep error collection, burst detection, novelty scoring, pod restart analysis, JWT/auth anomaly detection, and pre/post-incident trend comparison scoped to CTC Production 1679802 as primary account.'
keywords: ['rca', 'newrelic', 'logs', 'forensics', 'trends', 'anomaly', 'multi-account', 'error-patterns']
---

# RCA Log Forensics Skill

This skill drives the **New Relic evidence-acquisition stream** for RCA workflows. It orchestrates deep log collection, error pattern extraction, trend comparison, and dependency correlation across configured New Relic accounts.

## Credential Requirements

Delegates to `newrelic-authentication` and `newrelic-log-operations` skills.
Required variables in `.env`:
- `NEWRELIC_API_KEY`
- `NEWRELIC_ACCOUNT_IDS` (CTC Production `1679802` must be included)

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `service_name` | string | yes | Target New Relic service/APM entity name |
| `incident_time` | ISO 8601 datetime | yes | Approximate incident start (UTC) |
| `primary_window_minutes` | integer | no | Evidence window in minutes before incident time (default: 360) |
| `baseline_window_minutes` | integer | no | Comparison baseline window (default: 1440, i.e. 24 h prior) |
| `account_ids_override` | string list | no | Override account scope; must be subset of configured IDs |
| `error_signatures` | string list | no | Known error keywords/patterns to prioritize |

## Operations

### 1. Error Log Collection
Collect `ERROR` and `CRITICAL` log events for the target service across all configured accounts within the primary window.

Behavior:
- Filter by `service_name` and severity
- Capture `timestamp`, `message`, `level`, `host`, `traceId`, `pod.name` where available
- Respect account prioritization: process `1679802` first

### 2. Baseline Comparison
Collect equivalent error logs from the baseline window to support novelty scoring.

Behavior:
- Identical query structure as error log collection, shifted to baseline period
- Used to compute `novelty_multiplier` per error pattern (see scoring below)

### 3. Error Pattern Clustering
Group error messages into normalized patterns to identify dominant failure modes.

Behavior:
- Strip variable tokens (UUIDs, IPs, timestamps, numeric IDs) from messages
- Cluster by normalized template
- Output: pattern, count, first/last seen, sample raw messages, affected hosts

### 4. Burst Detection
Identify time windows with error-count spikes relative to baseline.

Behavior:
- 10-minute time-series bucketing (configurable)
- Compare each bucket against baseline mean ± 2σ
- Flag buckets exceeding 3× baseline rate as burst windows

### 5. Throughput and Latency Trend
Retrieve transaction throughput (rpm) and latency (avg, P95) across the primary and baseline windows.

Behavior:
- Query `Transaction` event type with `TIMESERIES`
- Overlay error rate on the same time axis
- Output: per-bucket `rpm`, `avg_duration_ms`, `p95_duration_ms`, `error_rate_pct`

### 6. Pod Restart and Host Anomaly Detection
Detect pod restarts, host drops, and infrastructure churn correlated with the incident window.

Behavior:
- Delegate to `scripts/newrelic/check_pod_restart.py` and `scripts/newrelic/verify_pod_restart_status.py`
- Correlate restart timestamps with error burst windows

### 7. JWT / Auth Anomaly Detection
Surface auth-layer failures (401, 403, JWT decode errors) that may amplify or cause degradation.

Behavior:
- Delegate to `scripts/newrelic/check_jwt_errors_by_pod.py`
- Report pod-level auth error frequency and timing

### 8. Dependency Error Scan
Identify downstream service errors correlated with the primary service's degradation.

Behavior:
- Delegate to `newrelic-log-operations` → Trace Service Dependencies
- Collect errors from each discovered downstream service within the primary window
- Return upstream/downstream error counts with timestamps

## Outputs

| Output | Description |
|---|---|
| `error_log_sample` | Up to 200 representative error log events |
| `error_patterns` | Clustered pattern list with counts and novelty scores |
| `burst_windows` | Time buckets with spike flags |
| `latency_trend` | Per-bucket throughput, avg/P95 latency, error rate |
| `pod_restart_events` | Pod restart records with timestamps |
| `auth_anomalies` | JWT/auth error counts per pod |
| `dependency_errors` | Per-downstream-service error counts |
| `accounts_searched` | List of account IDs queried |
| `query_parameters` | Reproducibility record: NRQL snippets, time windows, filters |

## Scoring

Error candidates are scored using the `newrelic-log-operations` RCA scoring model:
- Error count (proportional)
- Severity multiplier: CRITICAL/FATAL ×4, ERROR ×2
- Novelty multiplier: new pattern ×2, count ≥ 2× baseline ×1.5
- Dependency contribution: downstream error count × 1.5

## Validation Standards

- Do not proceed if `NEWRELIC_API_KEY` or `NEWRELIC_ACCOUNT_IDS` are absent
- Do not return unbound log payloads — enforce per-query limits
- Do not include account IDs outside the configured allowlist
- Mark any stream that fails with `stream_status: failed` and include the error reason
