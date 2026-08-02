---
name: 'rca-incident-similarity'
description: 'Incident similarity intelligence skill for discovering and differentially comparing historical ServiceNow incidents against a target incident using signal matching, symptom overlap, resolution pattern mining, and recurrence scoring.'
keywords: ['rca', 'servicenow', 'similarity', 'historical', 'recurrence', 'pattern-matching', 'differential']
---

# RCA Incident Similarity Skill

This skill powers the **historical incident comparison stream** for RCA workflows. It discovers similar past incidents, extracts resolution patterns, scores recurrence risk, and generates a differential comparison table.

## Credential Requirements

Delegates to `servicenow-authentication` and `servicenow-incident-operations` skills.
Required variables in `.env`:
- `SERVICENOW_HOST`
- `SERVICENOW_USERNAME`
- `SERVICENOW_PASSWORD`

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `incident_number` | string | yes | Target incident (e.g. `INC0084281`) |
| `service_name` | string | yes | Affected service or CI name |
| `error_signatures` | string list | no | Error patterns or keywords to match |
| `lookback_days` | integer | no | Historical search depth in days (default: 90) |
| `max_candidates` | integer | no | Maximum similar incidents to retrieve (default: 10) |

## Operations

### 1. Target Incident Enrichment
Retrieve full details of the target incident from ServiceNow.

Behavior:
- Fetch: `number`, `short_description`, `description`, `state`, `priority`, `impact`, `urgency`, `opened_at`, `resolved_at`, `assigned_to`, `assignment_group`, `close_notes`, `cause`, `cmdb_ci`, `linked_problem`, `work_notes`
- Parse structured error signatures from description and work notes

### 2. Similar Incident Discovery
Search for historical incidents matching on service/CI name, error signatures, and symptom overlap.

Behavior:
- Query ServiceNow with combined keyword filters: CI name, error keywords, short description similarity
- Apply `lookback_days` restriction
- Exclude the target incident from results
- Return up to `max_candidates` results

### 3. Differential Comparison
Compare target incident against each historical candidate across key dimensions.

Output columns per candidate:

| Dimension | Description |
|---|---|
| `incident_number` | Historical incident ID |
| `opened_at` | Date/time of occurrence |
| `resolved_at` | Date/time of resolution |
| `resolution_time_minutes` | Time to resolve |
| `root_cause_match` | Whether root cause matches current hypothesis |
| `resolution_pattern` | How it was resolved (summary) |
| `recurrence_gap_days` | Days since prior occurrence |
| `signal_overlap_score` | 0–100 matching score against target signals |

### 4. Recurrence Scoring
Assess whether the target incident represents a recurring pattern.

Behavior:
- Count matches within rolling 30/60/90-day windows
- Flag as `recurring` if 2 or more matches within 90 days
- Compute average recurrence gap
- Return `recurrence_risk`: `high`, `medium`, `low`

### 5. Resolution Pattern Mining
Extract common resolution actions from similar incidents.

Behavior:
- Aggregate `close_notes` and `work_notes` from candidates
- Identify common resolution verb patterns (rollback, restart, config change, code deploy, vendor escalation)
- Return top-3 resolution patterns with supporting incident count

## Outputs

| Output | Description |
|---|---|
| `target_incident` | Enriched target incident record |
| `similar_incidents` | List of historical candidates with differential data |
| `recurrence_risk` | `high` / `medium` / `low` with supporting count |
| `resolution_patterns` | Top-3 resolution patterns with incident counts |
| `differential_table` | Markdown comparison table |
| `query_parameters` | Reproducibility record: search filters, lookback window |

## Validation Standards

- Do not proceed if `incident_number` is missing or invalid
- Do not return more than `max_candidates` results
- Never infer resolution patterns from insufficient data (fewer than 2 candidates)
- Mark `recurrence_risk` as `unknown` when fewer than 2 historical matches found
