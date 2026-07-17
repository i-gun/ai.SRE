# New Relic -> ServiceNow Alert Orchestrator Usage

Script path:

`scripts\orchestration\newrelic_servicenow_alert_orchestrator.py`

## What it does

For each open unacknowledged New Relic alert in scoped account `1679802`:

1. Acknowledges the New Relic alert.
2. Searches ServiceNow incidents by:
   - short description substring match (`LIKE *<alert title>*` semantics)
   - incident creation time within the same requested window (for example `1 hour ago`, `3 hours ago`)
3. Branches:
   - Existing + assigned: no ServiceNow change (stop for that alert).
   - Existing + unassigned: assigns to configured user and updates fields per `servicenow-assign-unassigned-incidents.prompt.md`.
   - Existing + resolved: no ServiceNow change; report incident number, assignee, and resolution notes.
   - Not found: creates a new incident with required defaults, including:
     - Contact = `teams`
     - Channel = `Self-service`
4. Produces:
   - Per-alert report (`alert title -> ack status`, `incident number -> assignee`, `resolution notes`)
   - Summary counts:
     - Open New Relic alerts acknowledged
     - ServiceNow incidents raised (new)
     - ServiceNow incidents acknowledged only (already raised)

## Prerequisites

- `.env` populated with:
  - `NEWRELIC_API_KEY`
  - `NEWRELIC_ACCOUNT_IDS` (must include `1679802`)
  - `SERVICENOW_HOST`
  - `SERVICENOW_USERNAME`
  - `SERVICENOW_PASSWORD`
  - `SERVICENOW_ASSIGNMENT_GROUPS` (must include the assignment group used for new incidents)

## Basic run

```bash
python scripts\orchestration\newrelic_servicenow_alert_orchestrator.py
```

Default output is Markdown/plain text on screen.

## Run with explicit overrides

```bash
python scripts\orchestration\newrelic_servicenow_alert_orchestrator.py ^
  --policy-prefix "Digital Operations" ^
  --since "6 hours ago" ^
  --limit 100 ^
  --servicenow-user "sn_integration_user" ^
  --caller-id "sn_integration_user" ^
  --contact "teams" ^
  --channel "Self-service" ^
  --assignment-group "IT - Epam - Monitoring - ODP" ^
  --service-offering "Digital - New Relic Alerts - ODP" ^
  --configuration-item "Digital - New Relic Alerts - ODP"
```

## Output format

- Default: `--output-format markdown`
- Optional JSON: `--output-format json`

## Run from UI chat (no terminal)

Use these prompts directly in Copilot Chat:

```text
@Advisor, run the NewRelic->ServiceNow orchestrator with default settings and return the report in Markdown.
```

```text
@Advisor, run the NewRelic->ServiceNow orchestrator with since='6 hours ago', policy-prefix='Digital Operations', limit=100, assignment-group='IT - Epam - Monitoring - ODP', and return the report.
```

```text
@Advisor, run the orchestrator and save output to scripts\orchestration\last_run_report.json, then show me a summary.
```

## Example output shape

```json
{
  "report": [
    {
      "newrelic_alert_title": "Digital Operations - Checkout errors",
      "acknowledgement_status": "success",
      "servicenow_incident_number": "INC0012345",
      "servicenow_assignee": "sn_integration_user",
      "servicenow_resolution_notes": ""
    }
  ],
  "summary": {
    "open_newrelic_alerts_acknowledged": 1,
    "servicenow_incidents_raised_new": 0,
    "servicenow_incidents_acknowledged_only_already_raised": 1
  }
}
```
