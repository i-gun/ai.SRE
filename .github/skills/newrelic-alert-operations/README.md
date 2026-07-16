# New Relic Alert Operations Skill

Fetch and acknowledge open unacknowledged alerts in New Relic, scoped by policy name.

## Required Environment Variables

```bash
NEWRELIC_API_KEY=NRAK-...
NEWRELIC_ACCOUNT_IDS=1234567,2345678
NEWRELIC_USERNAME=you@company.com
```

## What This Skill Enforces

- Muted alerts are always excluded.
- Time range is fixed to `SINCE 1 hour ago UNTIL now`.
- Open/unacknowledged issue events are filtered with `event = 'ACTIVATED'`.
- Acknowledgment uses configured `NEWRELIC_USERNAME` by default.

## API Methods

### `fetch_open_alerts(...)`

```python
alerts_by_account = client.fetch_open_alerts(
    policy_name_contains="Digital operations",
    priority=None,
    limit=100,
)
```

Signature:
```python
fetch_open_alerts(*, policy_name_contains, priority=None, limit=100, account_ids=None)
```

### `acknowledge_issue(...)`

```python
result = client.acknowledge_issue(
    account_id=1234567,
    issue_id="<issueId>",
)
```

Signature:
```python
acknowledge_issue(*, account_id, issue_id, username=None)
```

If `username` is omitted, `NEWRELIC_USERNAME` is used.

### `fetch_and_acknowledge_open_alerts(...)`

```python
summary = client.fetch_and_acknowledge_open_alerts(
    policy_name_contains="Digital operations",
    priority=None,
    limit=100,
)
```

Signature:
```python
fetch_and_acknowledge_open_alerts(*, policy_name_contains, priority=None, limit=100, account_ids=None)
```

Returns summary with:
- `alerts_found`
- `acknowledged_count`
- `failed_count`
- `acknowledged`
- `failed`

## NRQL Applied

```nrql
SELECT issueId, title, policyNames, conditionNames, priority, activateTime, lastModifiedTime, issueLink, muted
FROM NrAiIssue
WHERE muted != 'fullyMuted'
  AND event = 'ACTIVATED'
  AND policyNames LIKE '%<policy_name_contains>%'
SINCE 1 hour ago UNTIL now
ORDER BY lastModifiedTime DESC
LIMIT <limit>
```

## Quick End-to-End Example

```python
from newrelic_alerts_client import NewRelicAlertsClient

client = NewRelicAlertsClient.from_env()
summary = client.fetch_and_acknowledge_open_alerts(
    policy_name_contains="Digital operations",
    limit=100,
)

print(summary["acknowledged_count"], summary["failed_count"])
```
