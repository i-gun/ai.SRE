---
name: 'rca-cross-system-correlation'
description: 'Cross-system evidence correlation skill for building a unified causal timeline, scoring competing hypotheses, rejecting weak candidates, and producing a root cause determination with contributing factors from New Relic, ServiceNow, Jira, Confluence, and AzureGit evidence streams.'
keywords: ['rca', 'correlation', 'causality', 'hypothesis', 'evidence-synthesis', 'timeline', 'confidence-scoring']
---

# RCA Cross-System Correlation Skill

This skill drives the **synthesis stream** for RCA workflows. It receives evidence packets from all upstream streams, constructs a unified causal timeline, scores competing hypotheses, performs contradiction checking, and produces the final root cause determination.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `log_forensics_output` | object | yes | Output from `rca-log-forensics` |
| `servicenow_mining_output` | object | yes | Output from `rca-servicenow-mining` |
| `jira_lifecycle_output` | object | yes | Output from `rca-jira-lifecycle` |
| `confluence_context_output` | object | yes | Output from `rca-confluence-context` |
| `azuregit_attribution_output` | object | yes | Output from `rca-azuregit-attribution` |
| `incident_similarity_output` | object | no | Output from `rca-incident-similarity` |

Streams with `required: yes` that are missing or failed must be flagged as `stream_gap` before synthesis proceeds.

## Operations

### 1. Unified Timeline Construction
Merge all timestamped events from every evidence stream into a single chronological narrative.

Behavior:
- Normalize all timestamps to UTC
- Merge: error burst windows, latency trend inflection points, pod restart events, ServiceNow work note timestamps, Jira transition timestamps, Confluence page modification dates (if relevant)
- Annotate each event with: `source_system`, `event_type`, `significance` (`high`/`medium`/`low`), `raw_reference`
- Identify: first symptom timestamp, blast-radius expansion timestamps, mitigation action timestamp, resolution timestamp

### 2. Evidence Matrix Assembly
Construct a cross-system evidence matrix linking each observed symptom to its data sources.

Output table columns:
| Column | Description |
|---|---|
| `symptom` | Observed symptom or signal |
| `source` | System(s) providing the evidence |
| `evidence_strength` | `strong` / `moderate` / `weak` |
| `cross_validated` | `yes` / `no` (evidence seen in ≥ 2 systems) |
| `evidence_reference` | Source record identifiers |

### 3. Hypothesis Generation
Enumerate competing root cause hypotheses based on assembled evidence.

Behavior:
- Generate one hypothesis per distinct causal pattern identified in the evidence
- For each hypothesis, document:
  - `hypothesis_id`
  - `statement` (one-sentence causal claim)
  - `supporting_evidence` (list of evidence references)
  - `contradicting_evidence` (list of evidence references)
  - `confidence` (`high` / `medium` / `low`)
  - `root_cause_category` (`code_defect` / `config_drift` / `dependency_failure` / `operational_process`)

### 4. Hypothesis Stress-Testing and Rejection
Challenge each hypothesis by testing it against the full evidence set.

Rejection criteria:
- Contradicting evidence is stronger than supporting evidence
- Hypothesis does not explain the timing of first symptom
- Hypothesis requires assuming facts not present in evidence
- Confidence score below threshold (< 0.3 normalized)

For each rejected hypothesis:
- Record `rejection_reason`
- Move to `rejected_hypotheses` list

### 5. Root Cause Determination
Select the most likely root cause from surviving hypotheses.

Behavior:
- Rank surviving hypotheses by confidence score
- Select top-ranked as primary root cause
- If top two are within 0.1 confidence of each other, flag as `ambiguous` and present both
- Identify: `trigger` (proximate cause), `amplifiers` (factors that worsened impact), `detection_gaps` (monitoring blind spots)

### 6. Contributing Factor Analysis
Document secondary factors that did not cause the incident but contributed to severity or duration.

Return per factor:
- `factor_description`
- `impact_on_severity` / `impact_on_duration`
- `evidence_reference`

## Outputs

| Output | Description |
|---|---|
| `unified_timeline` | Merged UTC-normalized event list with annotations |
| `evidence_matrix` | Cross-system evidence table |
| `hypotheses` | All generated hypotheses with evidence and confidence |
| `rejected_hypotheses` | Rejected candidates with rejection rationale |
| `root_cause` | Primary root cause determination with confidence and category |
| `contributing_factors` | Secondary factor list |
| `trigger` | Proximate causal event |
| `amplifiers` | Factors that worsened impact |
| `detection_gaps` | Monitoring and alerting blind spots identified |
| `stream_gaps` | Any missing or failed input streams |

## Validation Standards

- Do not synthesize if fewer than 2 streams have returned valid evidence
- Do not mark root cause as `high` confidence if it relies on a single stream's data
- Do not present a rejected hypothesis in the final root cause section
- Flag all assumptions made during synthesis under `assumptions_log`
- Every root cause claim must be traceable to at least one evidence reference
