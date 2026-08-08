---
name: "RCA Final Report Assembly"
description: "Assemble the complete, structured RCA markdown document from all stream outputs, enforcing all quality gates before marking the report as final."
argument-hint: "Provide: all stream outputs from deep investigation, correlation, visualization, and attribution."
agent: "RCA"
---

# RCA Final Report Assembly

Use this prompt during Phase 4 (Reporting and Outputs) to assemble the final deliverable from all completed stream outputs.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@RCA, assemble the final RCA report using rca-report-authoring.

Inputs available:
- Incident: <INCIDENT_NUMBER>
- Service: <SERVICE_NAME>
- Analysis window: <START_UTC> to <END_UTC>
- Correlation output: <available / stream_gaps: [...]>
- Visualization output: <available>
- AzureGit attribution output: <available / deferred / no_evidence>
- Similar incident output: <available / not available>
- ServiceNow mining output: <available>
- Jira lifecycle output: <available>
- Confluence context output: <available>

Assemble the report following the rca-report-authoring section order:

1. Document Control
2. Executive Summary (3–5 sentences, root cause category badge, MTTD/MTTR/key metrics)
3. Impact Assessment (user-facing behavior + measured metrics table)
4. Scope and Method (systems, windows, accounts, AzureGit scope, reproducibility note)
5. Technical Timeline (UTC-normalized event table)
6. Visual Assets (embed all five outputs from rca-visualization with captions)
7. Evidence Matrix (cross-system table)
8. Similar Incident Comparison (if available; note gap if not)
9. Root Cause and Contributing Factors:
   9.1 Root Cause narrative with confidence and category
   9.2 Competing Hypotheses Considered table (all — accepted and rejected)
   9.3 Contributing Factors
   9.4 Amplifiers and Detection Gaps
10. Code Attribution Pack:
    10.1 Attribution Summary table
    10.2 Attribution Confidence Ledger
    (If no_evidence: include no_match_report verbatim)
11. Corrective and Preventive Actions (minimum 3, table format with type/priority/owner hint/evidence basis)
12. Validation Plan
13. Open Questions and Unknowns
14. Appendix (data sources, NRQL queries, ServiceNow/Jira parameters, AzureGit queries, assumptions log)

Before marking complete, validate all quality gates:
- Every major claim has at least one evidence reference
- Root cause alternatives are considered and rejected with rationale
- Confidence score is explicit and justified
- Minimum 3 corrective/preventive actions included
- Both executive and technical sections present
- Open questions populated
- Code attribution without direct evidence is labelled "Not verified"
- AzureGit configuration gap explicitly stated in section 10 if applicable
- All timestamps UTC-normalized

Return the report as a single Markdown document.
Save output to: artifacts/<SERVICE_NAME>.RCA.<YYYY-MM-DD>.md
```

## Execution Requirements

- Do not omit any of the 14 sections — use explicit gap notes for unavailable data
- Do not present fabricated evidence or hallucinated file paths
- Do not mark the report complete until all quality gates pass
- File output path convention: `artifacts/<service_name>.RCA.<YYYY-MM-DD>.md`
- After saving, confirm the file path and list which quality gates passed and which had gaps
