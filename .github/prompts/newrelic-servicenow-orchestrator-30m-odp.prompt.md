---
name: "NewRelic -> ServiceNow Orchestrator (30m, Limit 5)"
description: "Run the New Relic to ServiceNow orchestrator for the last 30 minutes with Digital Operations policy prefix, limit 5, and the ODP monitoring assignment group, then return the report."
argument-hint: "Optional override: ask for JSON output or request saving the report to a file."
agent: "Advisor"
---

# NewRelic -> ServiceNow Orchestrator (30m, Limit 5)

Use this prompt to run the orchestrator with a narrow 30-minute window and return the report.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@Advisor, run the NewRelic->ServiceNow orchestrator with since='30 minutes ago', policy-prefix='Digital Operations', limit=5, assignment-group='IT - Epam - Monitoring - ODP', and return the report.
```

Execution requirements:
- Use `scripts\orchestration\newrelic_servicenow_alert_orchestrator.py`.
- Load credentials from the project `.env`.
- Return the final report in Markdown unless JSON is explicitly requested.
- Include per-alert results with:
  - New Relic alert title
  - Acknowledgement status
  - ServiceNow incident number
  - Assignee
  - Resolution notes
- Include summary counts for:
  - Open New Relic alerts acknowledged
  - ServiceNow incidents raised (new)
  - ServiceNow incidents acknowledged only (already raised)
- If execution fails, return the first concrete failure instead of a speculative summary.

Operational note:
- This workflow acknowledges matching New Relic alerts and may create or assign ServiceNow incidents.