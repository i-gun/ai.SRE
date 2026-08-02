---
name: "RCA Similar Incident Comparison"
description: "Discover and differentially compare historical incidents against the target to assess recurrence risk, extract resolution patterns, and inform hypothesis scoring."
argument-hint: "Provide: incident number, service name, and error signatures from log forensics output."
agent: "RCA"
---

# RCA Similar Incident Comparison

Use this prompt to perform a targeted historical incident comparison, either as part of the main investigation or as a standalone lookup.

```text
@RCA, perform similar incident comparison for the following target:

Incident: <INCIDENT_NUMBER>
Service: <SERVICE_NAME>
Error signatures: <["sig1", "sig2", ...]>
Lookback: 90 days
Max candidates: 10

Execute via rca-incident-similarity:

1. Retrieve full details for <INCIDENT_NUMBER> from ServiceNow.
   - Extract: CI name, short_description, priority, opened_at, resolved_at, close_notes, cause, linked PRB

2. Search ServiceNow for historical incidents matching:
   - CI name or service name contains "<SERVICE_NAME>"
   - Short description or description contains any of: <ERROR_SIGNATURES>
   - Opened within last 90 days
   - Exclude <INCIDENT_NUMBER>

3. For each candidate, compute:
   - signal_overlap_score (0–100)
   - resolution_time_minutes
   - root_cause_match (yes / no / partial)
   - resolution_pattern (rollback / restart / config_change / code_deploy / vendor_action / workaround / unknown)
   - recurrence_gap_days (from prior occurrence)

4. Assess recurrence risk:
   - Count matches within 30/60/90-day rolling windows
   - Return recurrence_risk: high / medium / low / unknown

5. Extract top-3 resolution patterns with supporting incident count.

6. Produce differential comparison table in Markdown.

Output requirements:
- Return structured results with all fields above
- Report query parameters (ServiceNow filters used, date range)
- If fewer than 2 candidates found, mark recurrence_risk as "unknown" and note insufficient sample
- Do not infer resolution patterns with fewer than 2 candidates
```

## Execution Requirements

- Read credentials from `.env`
- All ServiceNow operations are read-only
- Return `query_parameters` block for reproducibility
- Differential table must include at least: `incident_number`, `opened_at`, `resolution_time_minutes`, `root_cause_match`, `resolution_pattern`, `signal_overlap_score`
