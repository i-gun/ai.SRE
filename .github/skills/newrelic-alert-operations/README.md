# New Relic Alert Operations Skill

Fetch and acknowledge open unacknowledged alerts in New Relic, scoped by policy name.

## Required Environment Variables

```bash
NEWRELIC_API_KEY=NRAK-...
NEWRELIC_ACCOUNT_IDS=1234567,2345678
```

## What This Skill Enforces

- Alert lookup is restricted to account `1679802`.
- Policy lookup uses starts-with and defaults to `Digital Operations%`.
- Query builder uses standard `NrAiIncident` NRQL keyset fields.
- Muted alerts are always excluded.
- Default time range is `SINCE 3 hours ago UNTIL now`.
- `since` is configurable from prompt/method call.
- Open/unacknowledged issue events are filtered with `event = 'ACTIVATED'`.
- Acknowledgment uses username resolved from New Relic platform via `NEWRELIC_API_KEY` by default.
- Acknowledgment mutation is `aiIssuesAckIssue(accountId, issueId)`.

## API Methods

### `fetch_open_alerts(...)`

```python
alerts_by_account = client.fetch_open_alerts(
    policy_name_starts_with="Digital Operations",
    priority=None,
    since="3 hours ago",
    limit=100,
)
```

Signature:
```python
fetch_open_alerts(*, policy_name_starts_with="Digital Operations", priority=None, since="3 hours ago", limit=100, account_ids=None)
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

If `username` is omitted, identity is resolved from New Relic platform using the API key.
If `issueId` is unavailable but `incidentId` exists, the client first resolves `issueId` from `NrAiIssue` via `contains(incidentIds, '<incidentId>')`, then acknowledges by `issueId`.

### `fetch_and_acknowledge_open_alerts(...)`

```python
summary = client.fetch_and_acknowledge_open_alerts(
    policy_name_starts_with="Digital Operations",
    priority=None,
    since="3 hours ago",
    limit=100,
)
```

Signature:
```python
fetch_and_acknowledge_open_alerts(*, policy_name_starts_with="Digital Operations", priority=None, since="3 hours ago", limit=100, account_ids=None)
```

Returns summary with:
- `alerts_found`
- `acknowledged_count`
- `failed_count`
- `acknowledged`
- `failed`

## NRQL Applied

```nrql
SELECT issueId, incidentId, title, description, interpolatedTitleTemplate, policyNames, policyName, conditionNames, conditionName, priority, event, issueLink, incidentLink, muted, activateTime, openTime, lastModifiedTime, timestamp
FROM <NrAiIssue or NrAiIncident>
WHERE <event-type-specific open filters>
SINCE <since> UNTIL now
ORDER BY <event-type-specific timestamp field> DESC
LIMIT <limit>
```

For `NrAiIncident`, open incidents use:

```nrql
FROM NrAiIncident
SELECT uniqueCount(incidentId)
WHERE policyName LIKE 'Digital%'
  AND muted = false
  AND (closeTime IS NULL OR closeTime = 0)
SINCE 3 hours ago
```

## Quick End-to-End Example

```python
from newrelic_alerts_client import NewRelicAlertsClient

client = NewRelicAlertsClient.from_env()
summary = client.fetch_and_acknowledge_open_alerts(
    policy_name_starts_with="Digital Operations",
    since="6 hours ago",  # configurable override
    limit=100,
)

print(summary["acknowledged_count"], summary["failed_count"])
```
