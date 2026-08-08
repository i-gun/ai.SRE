---
name: 'rca-visualization'
description: 'RCA visualization and snapshot generation skill for producing structured chart data, error volume trend tables, latency overlays, incident timeline Mermaid diagrams, and causal relationship graphs from correlated evidence streams.'
keywords: ['rca', 'visualization', 'timeline', 'mermaid', 'trend-chart', 'causal-graph', 'latency-overlay']
---

# RCA Visualization Skill

This skill drives the **visualization stream** for RCA workflows. It transforms structured evidence into rendered diagrams, trend tables, and annotated charts suitable for inclusion in the final RCA report.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `latency_trend` | time-series object | yes | Per-bucket throughput, avg/P95 latency, error rate from `rca-log-forensics` |
| `error_patterns` | list | yes | Clustered error pattern list with counts from `rca-log-forensics` |
| `unified_timeline` | list | yes | Merged UTC event list from `rca-cross-system-correlation` |
| `root_cause` | object | yes | Root cause determination from `rca-cross-system-correlation` |
| `hypotheses` | list | yes | All hypotheses (accepted and rejected) |
| `contributing_factors` | list | no | Contributing factor list |

## Operations

### 1. Error Volume Trend Table
Generate a bucketed error volume trend table for embedding in the report.

Output format (Markdown table):

| Time Bucket (UTC) | Error Count | Error Rate (%) | Throughput (rpm) | Burst Flag |
|---|---|---|---|---|
| `HH:MM – HH:MM` | N | N.N% | N.N | `⚠ burst` or `` |

Caption: `Error volume and throughput across the incident window. Burst windows (>3× baseline) are flagged.`

### 2. Latency Overlay Table
Generate a latency and error-rate overlay table.

Output format (Markdown table):

| Time Bucket (UTC) | Avg Latency (ms) | P95 Latency (ms) | Error Rate (%) | Annotation |
|---|---|---|---|---|
| `HH:MM – HH:MM` | N | N | N.N% | e.g. `first degradation` |

Caption: `Latency and error-rate overlay. Key inflection points annotated.`

### 3. Incident Timeline Diagram
Render a Mermaid `gantt` or `timeline` diagram of the incident lifecycle.

Behavior:
- Include: first symptom, alert fire, incident open (ServiceNow), key work note milestones, mitigation action, resolution
- Use UTC timestamps
- Group by system: `New Relic`, `ServiceNow`, `Jira`, `Operator Actions`

Output: fenced Mermaid code block with caption.

Caption: `Incident lifecycle timeline across all systems. Timestamps in UTC.`

### 4. Causal Relationship Diagram
Render a Mermaid `graph TD` diagram showing causal relationships.

Behavior:
- Nodes: trigger event, amplifying factors, affected service, downstream dependencies, user-facing impact
- Edges: labeled with evidence strength (`strong`, `moderate`, `weak`)
- Rejected hypotheses are omitted
- Contributing factors shown as dashed-edge nodes

Caption: `Causal relationship graph. Solid edges = strong evidence. Dashed edges = contributing factors.`

### 5. Top Error Pattern Bar Chart (ASCII / Table)
Render top-10 error patterns as a ranked table with relative volume bars.

Output format (Markdown table):

| Rank | Error Pattern (normalized) | Count | Novelty | Volume Bar |
|---|---|---|---|---|
| 1 | `<pattern>` | N | new / recurring | `████████░░` |

Caption: `Top error patterns by frequency. Novelty flags patterns absent from baseline window.`

## Outputs

| Output | Description |
|---|---|
| `error_volume_table` | Markdown table with burst flags |
| `latency_overlay_table` | Markdown table with inflection annotations |
| `incident_timeline_diagram` | Mermaid diagram with caption |
| `causal_relationship_diagram` | Mermaid graph with caption |
| `error_pattern_table` | Ranked error pattern table with volume bars |

## Validation Standards

- Do not render diagrams with fabricated data points — use only values present in input objects
- Annotate inflection points only where `unified_timeline` provides a supporting event at that timestamp
- Mermaid diagrams must use valid syntax — test output structure before finalizing
- Truncate long error pattern strings to 80 characters in display cells
- All time values must be UTC-normalized before rendering
