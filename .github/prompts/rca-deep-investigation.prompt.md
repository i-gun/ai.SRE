---
name: "RCA Deep Investigation"
description: "Execute the full parallel evidence acquisition and analysis phases for an approved RCA. Runs all five data collection streams concurrently, then executes pattern analysis, trend comparison, and causality graph drafting."
argument-hint: "Requires completed intake output and APPROVE_RUN_RCA confirmation."
agent: "RCA"
---

# RCA Deep Investigation

Use this prompt after `APPROVE_RUN_RCA` is issued. It launches all five evidence streams concurrently and runs analysis phases.

```text
@RCA, execute deep investigation for the approved incident.

Intake reference:
- Incident: <INCIDENT_NUMBER>
- Service: <SERVICE_NAME>
- Primary window: <START_UTC> to <END_UTC>
- Baseline window: <BASELINE_START_UTC> to <BASELINE_END_UTC>
- AzureGit status: <READY / deferred/unverified>

Execute Phase 1 — Concurrent Evidence Acquisition:

Stream A (New Relic — rca-log-forensics):
- Collect error logs for <SERVICE_NAME> in primary window, CTC Production 1679802 first
- Run error pattern clustering and burst detection
- Retrieve throughput and latency trend (primary + baseline)
- Check pod restarts and JWT/auth anomalies
- Scan downstream dependency errors

Stream B (ServiceNow — rca-servicenow-mining):
- Retrieve full incident record for <INCIDENT_NUMBER>
- Extract chronological work note and comment timeline
- Reconstruct assignment history with dwell times
- Fetch linked Problem and Task records
- Extract and classify resolution summary

Stream C (Jira — rca-jira-lifecycle):
- Search for related issues by service name and incident reference
- Extract lifecycle and transition history for each discovered issue
- Analyze comments for actionable signals
- Map component/label ownership
- Identify fix versions and blocker dependency chain

Stream D (Confluence — rca-confluence-context):
- Retrieve architecture documentation for <SERVICE_NAME>
- Fetch service ownership and on-call pages
- Locate applicable runbooks and known-error records
- Search for pages referencing <INCIDENT_NUMBER>
- Report knowledge gaps explicitly

Stream E (AzureGit — rca-azuregit-attribution):
- [Execute only if AzureGit status = READY]
- Discover candidate repositories for <SERVICE_NAME>
- Search for error signatures derived from Stream A output
- Trace endpoint paths and dependency client locations
- Produce attribution candidates with confidence scores
- If no evidence found, produce explicit no_match_report

After all streams complete, execute Phase 2 — Concurrent Analysis:
- Cluster error patterns and score by frequency, severity, novelty
- Identify trend inflection points and correlate with work note timeline
- Retrieve 3 most similar historical incidents via rca-incident-similarity
- Draft initial causality graph with evidence edge weights
- Propose attribution candidates from AzureGit output (or note deferred)

Report progress after each phase with:
- Streams completed
- Evidence quality (strong / moderate / weak / no data) per stream
- Blockers and data gaps
- Estimated time to synthesis
```

## Execution Requirements

- Do not start investigation without prior `APPROVE_RUN_RCA` confirmation
- All credentials from `.env` — no hardcoding
- Streams must run concurrently where technically feasible
- Each stream must report `stream_status: complete | partial | failed` before synthesis begins
- A failed stream is not a blocker — document the gap and continue with available evidence
- Maximum 500 log events, 200 code search matches, 20 Jira issues, 10 similar incidents
