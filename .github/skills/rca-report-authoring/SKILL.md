---
name: 'rca-report-authoring'
description: 'Final RCA report authoring skill for assembling a complete, structured markdown RCA document from correlated evidence streams, including executive summary, technical timeline, evidence matrix, code attribution pack, corrective actions, and validation plan.'
keywords: ['rca', 'report', 'authoring', 'executive-summary', 'technical-narrative', 'corrective-actions', 'attribution-ledger']
---

# RCA Report Authoring Skill

This skill drives the **report assembly stream** for RCA workflows. It accepts all upstream stream outputs and assembles the final, defensible RCA document in structured markdown.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `correlation_output` | object | yes | Full output from `rca-cross-system-correlation` |
| `visualization_output` | object | yes | Full output from `rca-visualization` |
| `azuregit_attribution_output` | object | yes | Full output from `rca-azuregit-attribution` |
| `incident_similarity_output` | object | no | Output from `rca-incident-similarity` |
| `servicenow_mining_output` | object | yes | Output from `rca-servicenow-mining` |
| `jira_lifecycle_output` | object | yes | Output from `rca-jira-lifecycle` |
| `confluence_context_output` | object | yes | Output from `rca-confluence-context` |
| `intake_metadata` | object | yes | Service name, incident ID, analysis window, prepared-by |

## Report Structure

The assembled report must follow this section order:

---

### 1. Document Control
- Service name
- Incident number (ServiceNow)
- Analysis window (UTC start – end)
- Severity and impact classification
- Analysis date
- Prepared by
- Confidence level (from root cause determination)

### 2. Executive Summary
- 3–5 sentence narrative: what failed, why it failed, what the user impact was, and what was done to resolve it
- Root cause category badge: `CODE DEFECT` / `CONFIG DRIFT` / `DEPENDENCY FAILURE` / `OPERATIONAL/PROCESS`
- Key metrics: MTTD, MTTR, peak error rate, throughput drop

### 3. Impact Assessment
- User-facing behavior (qualitative)
- Measured metrics table: avg latency, P95 latency, throughput, error rate, blast radius

### 4. Scope and Method
- Systems investigated
- Time windows used
- Account IDs queried
- AzureGit project scope
- Data sources and query reproducibility note

### 5. Technical Timeline
- UTC-normalized event table from `unified_timeline`
- Columns: `Time (UTC)`, `System`, `Event`, `Significance`, `Evidence Reference`

### 6. Visual Assets
Embed in order:
1. Error volume trend table (from `rca-visualization`)
2. Latency overlay table
3. Incident timeline diagram (Mermaid)
4. Causal relationship diagram (Mermaid)
5. Top error pattern table

Each visual asset must include its caption.

### 7. Evidence Matrix
Full cross-system evidence table from `rca-cross-system-correlation`.

### 8. Similar Incident Comparison
- Recurrence risk badge: `HIGH` / `MEDIUM` / `LOW` / `UNKNOWN`
- Differential comparison table from `rca-incident-similarity`
- Resolution pattern summary

Omit this section if `incident_similarity_output` is not available; note the gap.

### 9. Root Cause and Contributing Factors

#### 9.1 Root Cause
- One-paragraph root cause narrative
- Trigger identification
- Confidence level and justification
- Root cause category

#### 9.2 Competing Hypotheses Considered
Table of all hypotheses with outcome:

| Hypothesis | Outcome | Rejection Reason (if rejected) |
|---|---|---|
| `<statement>` | Accepted / Rejected | `<rationale>` |

#### 9.3 Contributing Factors
Numbered list of contributing factors with evidence references.

#### 9.4 Amplifiers and Detection Gaps
- Factors that worsened impact
- Monitoring and alerting blind spots

### 10. Code Attribution Pack

#### 10.1 Attribution Summary
Table of attribution candidates:

| Project | Repository | File | Line | Confidence | Evidence Type |
|---|---|---|---|---|---|
| `<project>` | `<repo>` | `<path>` | `<line or N/A>` | High/Medium/Low/Not verified | observed/inferred/unknown |

#### 10.2 Attribution Confidence Ledger
- **High confidence**: direct cross-system evidence (signature match + call-path trace)
- **Medium confidence**: partial mapping with supporting signals
- **Low confidence**: plausible but single-system evidence only
- **Not verified**: no matching repository/file found in configured scope

If no attribution evidence was found, include the `no_match_report` verbatim.

### 11. Corrective and Preventive Actions

Minimum 3 items. Table format:

| # | Action | Type | Owner Hint | Priority | Evidence Basis |
|---|---|---|---|---|---|
| 1 | `<action>` | `Corrective` / `Preventive` / `Observability` | `<team or component>` | `P1/P2/P3` | `<evidence ref>` |

Action type definitions:
- **Corrective** — fixes the identified root cause or defect
- **Preventive** — reduces likelihood of recurrence
- **Observability** — addresses a detection gap

### 12. Validation Plan
- How to confirm the fix resolved the root cause
- Success criteria (metrics, alert conditions)
- Rollback criteria

### 13. Open Questions and Unknowns
Numbered list of unresolved ambiguities, insufficient evidence areas, and items requiring follow-up.

### 14. Appendix
- A: Data sources and query scope
- B: NRQL queries used
- C: ServiceNow and Jira search parameters
- D: AzureGit search queries and project scope
- E: Assumptions log

---

## Quality Gate Checklist

Before finalizing the report, verify:
- [ ] Every major claim in sections 9 and 10 has at least one evidence reference
- [ ] Root cause has alternatives considered and explicitly rejected with rationale
- [ ] Confidence score is stated and justified
- [ ] Minimum 3 corrective/preventive actions included
- [ ] Executive and technical sections both present
- [ ] Open questions section populated (not empty, even if only noting gaps)
- [ ] Code attribution without direct evidence is labelled `Not verified` — not omitted silently
- [ ] If AzureGit configuration was missing, section 10 states the gap explicitly
- [ ] All timestamps in report body are UTC-normalized

## Validation Standards

- Do not include fabricated data in any section
- Do not omit the Code Attribution Pack section — even a `no_evidence` outcome must be documented
- Do not present a rejected hypothesis as an accepted root cause
- Do not assert tool names, script names, or file paths that were not returned by upstream streams
