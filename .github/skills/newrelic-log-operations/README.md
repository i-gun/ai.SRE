# New Relic Log Operations

This skill package provides New Relic NerdGraph/NRQL log search, trend analysis, dependency traversal, and root-cause analysis helpers backed by `.env` credentials.

## Required Variables

- `NEWRELIC_API_KEY` — User API Key (starts with `NRAK-`). Generate at: https://one.newrelic.com/api-keys
- `NEWRELIC_ACCOUNT_IDS` — Single or comma-separated list of New Relic account IDs (e.g. `1234567` or `1234567,2345678,3456789`)

## Included Files

- `SKILL.md` — behavior contract for log search, trends, dependency traversal, and RCA
- `newrelic_client.py` — implementation for NerdGraph/NRQL operations, pattern extraction, and RCA scoring

## Helper Scripts

The repository includes execution helpers under `scripts/newrelic/`:

- `common.py` — shared bootstrap (`.env` loading + skill import path setup)
- `search_logs.py` — search Log events across configured accounts
- `analyze_trends.py` — generate time-series log count trends
- `trace_dependencies.py` — discover upstream/downstream service dependencies
- `root_cause_analysis.py` — run automated RCA for a named service

Example CLI usage:

```bash
python scripts/newrelic/search_logs.py --message "timeout" --severity ERROR --since "2 hours ago"
python scripts/newrelic/analyze_trends.py --service payment-service --since "24 hours ago" --facet level
python scripts/newrelic/trace_dependencies.py --service checkout-service --since "1 hour ago"
python scripts/newrelic/root_cause_analysis.py --service order-service --since "30 minutes ago"
```

## Supported Workflows

- Search logs across one or more New Relic accounts with message, severity, and service filters
- Search alert events (`NrAiIssue`) by policy name and priority, excluding fully-muted issues by default
- Analyze time-series log trends to identify anomaly windows
- Discover upstream callers and downstream service dependencies
- Run automated root cause analysis with evidence-backed findings and escalation guidance
- Execute arbitrary NRQL against single or multiple accounts in one NerdGraph request

## Usage Examples

```python
from newrelic_client import NewRelicClient

client = NewRelicClient.from_env()

# Search error logs for a service
logs = client.search_logs(
    message_contains="timeout",
    severity="ERROR",
    service="payment-service",
    since="2 hours ago",
    limit=100,
)

# Analyze log volume trends with 5-minute buckets, split by severity
trends = client.analyze_log_trends(
    service="checkout-service",
    since="12 hours ago",
    timeseries="5 minutes",
    facet="level",
)

# Discover what payment-service calls and who calls it
deps = client.trace_service_dependencies(
    service="payment-service",
    since="1 hour ago",
)
print(deps["upstream_services"])   # callers
print(deps["downstream_services"]) # dependencies
print(deps["databases"])           # DB systems accessed

# Run root cause analysis
rca = client.root_cause_analysis(
    service="order-service",
    since="30 minutes ago",
)
print(rca["root_cause"])
print(rca["recommendation"])
print(rca["escalation_points"])
print(rca["rca_candidates"])  # ranked list with confidence scores

# Run arbitrary NRQL across all configured accounts
results = client.run_nrql_across_accounts(
    nrql="SELECT count(*) FROM Log WHERE level = 'ERROR' SINCE 1 hour ago",
)
for account_id, rows in results.items():
    print(account_id, rows)

# Search active, non-muted alerts under a named policy group (default: muted excluded)
alerts = client.search_alerts(
    policy_name_contains="Digital Operations",
    priority="CRITICAL",
    since="1 hour ago",
)
for account_id, issues in alerts.items():
    for issue in issues:
        print(issue["title"], issue["policyNames"], issue["issueLink"])

# Include muted alerts explicitly
all_alerts = client.search_alerts(
    policy_name_contains="Digital Operations",
    since="1 hour ago",
    exclude_muted=False,
)
```

## Output Shape

### `root_cause_analysis` returns:

```python
{
    "service": str,
    "since": str,
    "accounts_queried": List[int],
    "error_summary": {
        "total_errors": int,
        "error_rate_per_minute": float,
        "top_error_messages": [{"message": str, "count": int}],
        "severity_breakdown": {"ERROR": int, "CRITICAL": int, ...},
    },
    "dependency_issues": [
        {"service": str, "error_count": int, "accounts": List[int]}
    ],
    "rca_candidates": [
        {
            "category": "service_error" | "dependency_failure",
            "description": str,
            "evidence": List[str],
            "confidence": float,   # 0.0 – 1.0
            "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
        }
    ],
    "root_cause": str,
    "recommendation": str,
    "escalation_points": List[str],
}
```

### `trace_service_dependencies` returns:

```python
{
    "service": str,
    "since": str,
    "accounts_queried": List[int],
    "upstream_services": List[str],
    "downstream_services": List[str],
    "databases": List[str],
    "dependency_graph": {
        "nodes": List[str],
        "edges": [{"from": str, "to": str}],
    },
}
```

## Notes

- All API calls use New Relic NerdGraph (`POST https://api.newrelic.com/graphql`)
- Multi-account NRQL uses a single batched request with GraphQL field aliases (`a<account_id>`)
- RCA error baseline is derived from the equivalent previous time window (e.g. "1 hour ago" → prior hour)
- Service dependency traversal requires Distributed Tracing to be enabled and `Span` data to be present
- Log search relies on `service.name` or `entity.name` attributes in log records
- Alert search targets the `NrAiIssue` event type; fully-muted issues (`muted = 'fullyMuted'`) are excluded by default — pass `exclude_muted=False` to override

## Tests

Run unit tests for NRQL building, scoring, and config parsing:

```bash
python -m unittest tests/test_newrelic_client.py -v
```
