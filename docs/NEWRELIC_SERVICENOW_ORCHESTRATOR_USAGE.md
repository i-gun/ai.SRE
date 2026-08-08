# New Relic -> ServiceNow Alert Orchestrator Usage

Script path:

`scripts\orchestration\newrelic_servicenow_alert_orchestrator.py`

## Reuse-First Policy

- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

## What it does

For each open unacknowledged New Relic alert in scoped account `1679802`:

1. Acknowledges the New Relic alert.
2. Searches ServiceNow incidents by:
   - short description substring match using a quote-stripped alert title (`LIKE *<alert title without quotes>*` semantics)
   - incident creation time within the same requested window (for example `1 hour ago`, `3 hours ago`)
   - normalized title comparison that tolerates quote, punctuation, and separator differences between New Relic and ServiceNow text
3. Branches:
   - Existing + assigned: no ServiceNow change (stop for that alert).
   - Existing + unassigned: assigns to configured user and updates fields per `servicenow-assign-unassigned-incidents.prompt.md`.
   - Existing + resolved: no ServiceNow change; report incident number, assignee, and resolution notes.
   - Not found: creates a new incident with required defaults, including:
     - Short description = New Relic alert title with quotes removed
     - Contact = `teams` via ServiceNow field `u_contact`
     - Channel = `Self-service` via ServiceNow field `contact_type`
4. Produces:
   - Per-alert report (`alert title -> ack status`, `incident number -> assignee`, `resolution notes`)
   - Summary counts:
     - Open New Relic alerts acknowledged
     - ServiceNow incidents raised (new)
     - ServiceNow incidents acknowledged only (already raised)
  - Planned ServiceNow assignments/creations when running in read-only mode

## Safety model

- Default mode is read-only.
- Use `--execute` to acknowledge alerts and mutate ServiceNow.
- Execute runs are blocked when matched alerts exceed the threshold from `--max-alerts` unless `--force-large-batch` is provided.

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

Local data bootstrap (single command, non-chat automation fallback): `python scripts/newrelic/generate_service_catalog.py --account-id 1679802 --since "30 days ago" --pretty-json`

Default output is Markdown/plain text on screen in read-only mode.

## Run with explicit overrides

```bash
python scripts\orchestration\newrelic_servicenow_alert_orchestrator.py ^
  --execute ^
  --policy-prefix "Digital Operations" ^
  --since "6 hours ago" ^
  --limit 100 ^
  --max-alerts 25 ^
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
- Optional file output: `--output-file artifacts\orchestration\last_run_report.json`

## Run from UI chat (no terminal)

Use these prompts directly in Copilot Chat:

```text
@Advisor, run the NewRelic->ServiceNow orchestrator with default settings and return the report in Markdown.
```

```text
@Advisor, run the NewRelic->ServiceNow orchestrator with since='6 hours ago', policy-prefix='Digital Operations', limit=100, assignment-group='IT - Epam - Monitoring - ODP', and return the report.
```

```text
@Advisor, run the orchestrator and save output to artifacts\orchestration\last_run_report.json, then show me a summary.
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
