---
name: 'rca-servicenow-mining'
description: 'ServiceNow resolution mining skill for extracting structured timeline, assignee history, work notes, resolution notes, and linked problem/task records from a target incident to support RCA evidence assembly.'
keywords: ['rca', 'servicenow', 'resolution', 'work-notes', 'timeline', 'assignment-history', 'problem-record']
---

# RCA ServiceNow Mining Skill

This skill drives the **ServiceNow evidence-acquisition stream** for RCA workflows. It extracts the full operational narrative from an incident record — from open through resolution — and structures it for cross-system correlation.

## Credential Requirements

Delegates to `servicenow-authentication` and `servicenow-incident-operations` skills.
Required variables in `.env`:
- `SERVICENOW_HOST`
- `SERVICENOW_USERNAME`
- `SERVICENOW_PASSWORD`

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `incident_number` | string | yes | Target ServiceNow incident (e.g. `INC0084281`) |
| `include_linked_records` | boolean | no | Fetch linked Problem and Task records (default: true) |

## Operations

### 1. Full Incident Record Retrieval
Retrieve all structured fields from the target incident.

Behavior:
- Fetch: `number`, `sys_id`, `short_description`, `description`, `state`, `priority`, `impact`, `urgency`, `category`, `subcategory`, `cmdb_ci`, `opened_at`, `resolved_at`, `closed_at`, `close_code`, `close_notes`, `cause`, `assigned_to`, `assignment_group`, `caller_id`
- Return normalized record with UTC-adjusted timestamps

### 2. Work Note and Comment Timeline
Reconstruct the chronological activity timeline from work notes and journal entries.

Behavior:
- Retrieve all `work_notes` and `comments` journal entries
- Sort ascending by `sys_created_on`
- Annotate each entry with: `timestamp (UTC)`, `author`, `type` (`work_note` / `comment`), `content`
- Flag entries containing actionable signals: escalation, rollback, restart, deploy, mitigation, workaround, root cause mention

### 3. Assignee History
Reconstruct assignment changes over the incident lifecycle.

Behavior:
- Retrieve audit history for `assigned_to` and `assignment_group` fields
- Return ordered timeline: `timestamp`, `field`, `old_value`, `new_value`, `changed_by`
- Compute assignment dwell times (time each assignee/group held the incident)

### 4. Linked Problem and Task Records
Fetch records linked to the incident via ServiceNow relationships.

Behavior:
- Discover linked `problem` (PRB) records
- Discover linked `problem_task` (PTASK) records
- Fetch summary fields: `number`, `short_description`, `state`, `cause`, `fix_notes`, `assigned_to`
- Return as structured linked-records list

### 5. Resolution Summary Extraction
Extract and structure the resolution narrative.

Behavior:
- Parse `close_notes`, `cause`, and final work notes
- Identify: mitigation action, permanent fix action, root cause (operator-stated), prevention notes
- Classify resolution type: `rollback`, `restart`, `config_change`, `code_deploy`, `vendor_action`, `workaround`, `unknown`

## Outputs

| Output | Description |
|---|---|
| `incident_record` | Full normalized incident record |
| `activity_timeline` | Chronological work note and comment list |
| `assignment_timeline` | Assignee change history with dwell times |
| `linked_records` | Linked PRB and PTASK records |
| `resolution_summary` | Structured resolution narrative and classification |
| `flagged_entries` | Work note entries containing actionable signals |
| `query_parameters` | Reproducibility record: incident number, retrieved fields |

## Validation Standards

- Do not proceed if `SERVICENOW_HOST`, `SERVICENOW_USERNAME`, or `SERVICENOW_PASSWORD` are absent
- Do not modify any ServiceNow record — all operations are read-only
- Do not infer assignment intent from field values not present in the audit log
- Redact any credential-like strings found in work notes before returning output
