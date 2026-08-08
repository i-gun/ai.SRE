---
name: "RCA Intake"
description: "Parse and lock the scope for an incoming incident RCA request. Validates required inputs, confirms primary account, defines analysis windows, and checks AzureGit configuration before proceeding."
argument-hint: "Provide: incident identifier, service name, incident time (UTC), and severity."
agent: "RCA"
---

# RCA Intake

Use this prompt to initiate an RCA investigation. It performs scope lock and configuration validation before any data collection begins.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@RCA, perform intake for the following incident and prepare for investigation:

Incident: <INCIDENT_NUMBER>
Service: <SERVICE_NAME>
Incident time (UTC): <YYYY-MM-DDTHH:MM:SSZ>
Severity: <P1 / P2 / P3>
Blast radius: <brief description of user-facing impact>
Region: <region or "unknown">
Additional context: <optional known symptoms or prior actions>

Validate:
1. Primary New Relic account is CTC Production 1679802. Confirm it is present in NEWRELIC_ACCOUNT_IDS.
2. Define primary analysis window: 6 hours ending at incident_time, plus 2-hour post-incident tail.
3. Define baseline window: equivalent 6-hour window 24 hours prior.
4. Confirm ServiceNow credentials are available for incident retrieval.
5. Confirm Jira credentials are available for issue discovery.
6. Confirm Confluence space keys are configured for knowledge search.
7. Validate AzureGit organization, project scope, and PAT availability.
   - If AzureGit configuration is missing or incomplete, set code-attribution track to "deferred/unverified" and proceed.
8. Report configuration status for each stream: READY / DEGRADED / UNAVAILABLE.
9. List any streams that must be skipped due to missing credentials.
10. Do NOT begin evidence collection yet — await APPROVE_RUN_RCA.
```

## Execution Requirements

- Read all credentials from `.env` in the project root
- Do not print credential values — report only availability status
- Output a structured intake summary:
  - Incident metadata
  - Analysis windows (UTC)
  - Per-stream configuration status
  - AzureGit scope (project list or `Not configured`)
  - Blockers and configuration gaps
- End the intake summary with the prompt: `Ready to execute. Issue APPROVE_RUN_RCA to begin.`
