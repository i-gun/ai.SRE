---
name: 'servicenow-incident-operations'
description: 'ServiceNow incident operations skill for scoped incident/problem/issue lifecycle flows including incident retrieval/creation, assignment/reassignment, work-note updates, matrix-based priority changes, incident-to-problem linkage, native ServiceNow->Jira capability detection, and controlled resolution with strict validation using .env-based username/password/host authentication. In INC→PRB→Issue flows, native ServiceNow->Jira is preferred when available; Jira delegation is used when native path is unavailable or unverified, without PTASK fallback artifact creation.'
keywords: ['servicenow', 'incident', 'itsm', 'work_notes', 'resolution', 'table-api']
---

# ServiceNow Incident Operations Skill

This skill provides operational capabilities for incident lifecycle management in ServiceNow using `.env` credentials.

## Credential Requirements

The skill expects these variables in `.env`:
- `SERVICENOW_HOST` (example: `https://your-instance.service-now.com`)
- `SERVICENOW_USERNAME`
- `SERVICENOW_PASSWORD`
- `SERVICENOW_ASSIGNMENT_GROUPS` (comma-separated list of designated assignment group names or sys_ids)

Security rules:
- Do not log credential values
- Do not commit `.env`
- Use `.env.template` for structure and `.env.example` for sanitized examples

## Supported Operations

### 1. Fetch Assigned Incidents
Retrieve incidents scoped to designated assignment groups from `SERVICENOW_ASSIGNMENT_GROUPS`, optionally filtered by:
- A specific user (`assigned_to`)
- A specific assignment group (`assignment_group`) that must be in the designated allowlist

Default behavior:
- Active incidents only
- Restricted to designated assignment groups
- Sorted by `sys_updated_on` descending
- Configurable `limit`

State handling guardrails:
- For prompts that require non-resolved incidents, apply both:
    - server-side filtering (`state!=6`), and
    - defensive client-side filtering using normalized state values
- Treat any of the following as resolved and exclude from processing:
    - `6`
    - `6 - Resolved`
    - `Resolved` (or display values containing `Resolved`)
- Never fetch/update records already in resolved state for non-resolved workflows

Optional retrieval mode:
- Unassigned incidents only (`unassigned_only=true`)

### 2. Create Incident From Scratch
Create incident records after collecting and validating required user inputs.

Required fields:
- `short_description`
- `description`
- `caller_id`

Optional fields:
- `assignment_group` (must be in designated groups; defaults to first designated group)
- `category`
- `subcategory`
- `impact`
- `urgency`
- `work_notes`

Validation:
- Missing required fields must be requested from user before create
- `impact` and `urgency` must be one of `1`, `2`, `3`
- `assignment_group` must remain in designated allowlist

### 3. Update Work Notes
Update incident with progress notes via `work_notes`.

Optional controlled field updates:
- `state`
- `assigned_to`
- `assignment_group` (must remain within designated groups)

Validation:
- Incident identifier required (`number` or `sys_id`)
- Work note cannot be empty
- Target incident must belong to a designated assignment group

### 4. Assign or Reassign Incident
Assign incident ownership with controlled reassignment behavior.

Supported behavior:
- Assign currently unassigned incidents
- Reassign incidents already owned by others when explicitly requested
- Optionally add assignment transition `work_notes`

Validation:
- Incident identifier required (`number` or `sys_id`)
- `assigned_to` required
- Reassign can be blocked by policy when `allow_reassign=false`

### 5. Resolve Incident with Validation
Performs validation prior to closure:
- Incident exists and is active
- Resolution note quality threshold is met
- `close_code` and `close_notes` provided

Update payload may include:
- `state` (resolved)
- `close_code`
- `close_notes`
- optional transition `work_notes`

### 6. Change Priority via Impact/Urgency Matrix
Adjust incident priority by updating `impact` and `urgency` fields according to matrix rules.

Priority Data Lookup Rules:

| Impact | Urgency | Priority |
| --- | --- | --- |
| 1 - High | 1 - High | 1 - Critical |
| 1 - High | 2 - Medium | 2 - High |
| 1 - High | 3 - Low | 3 - Moderate |
| 2 - Medium | 1 - High | 2 - High |
| 2 - Medium | 2 - Medium | 3 - Moderate |
| 2 - Medium | 3 - Low | 4 - Low |
| 3 - Low | 1 - High | 3 - Moderate |
| 3 - Low | 2 - Medium | 4 - Low |
| 3 - Low | 3 - Low | 5 - Planning |

Supported request formats:
- Numeric priority (`1` to `5`)
- Short form (`P1` to `P5`)
- Text form (`priority 1` to `priority 5`)

Behavior:
- Do not patch `priority` directly
- Compute deterministic default impact/urgency pair for target priority
- Update `impact` and `urgency`
- Optionally append `work_notes`
- Validate resulting priority when returned by ServiceNow response

Deterministic default pair by target priority:
- P1 -> impact=1, urgency=1
- P2 -> impact=1, urgency=2
- P3 -> impact=2, urgency=2
- P4 -> impact=2, urgency=3
- P5 -> impact=3, urgency=3

### 7. Raise Problem (PRB) From Incident And Link
Create a problem from an existing incident and link records.

Behavior:
- Resolve incident by `number` or `sys_id`
- Create `problem` record with required mapping:
    - `origin_task` <- incident `sys_id` (reference-safe write; displays incident `number` on Problem form)
    - `category` <- `Application`
    - `subcategory` <- `E-Commerce`
    - `problem_statement` <- incident `short_description`
    - `description` <- incident `description`
    - `service_offering` <- incident `cmdb_ci` (blank if empty)
    - `cmdb_ci` <- incident `cmdb_ci` (blank if empty)
- Patch incident `problem_id` with created problem `sys_id`
- Optionally append incident `work_notes` describing the linkage

Validation:
- Source incident must exist in designated scope
- Created problem must return `sys_id`
- Incident linkage update must succeed

### 8. Route Issue Creation From Problem (Native ServiceNow->Jira Preferred)
When explicitly requested, route issue creation from a problem.

Architecture policy:
- `/api/now/table/issue` does not exist on this instance.
- Native ServiceNow->Jira may be represented by integration fields/actions on
    Problem or Problem Task records.
- For INC→PRB→Issue flows:
    1) detect native capability first,
    2) execute native route only when available,
    3) otherwise delegate to `@Jira`.
- Do not create PTASK as fallback artifact in the unavailable branch.

Behavior:
- Resolve problem by `number` or `sys_id`
- Classify native capability (`available | conditionally_available | unavailable`)
- If `available`, execute native ServiceNow->Jira route and verify issue identifier
- If `conditionally_available` or `unavailable`, return Jira handoff payload for `@Jira`
- Enforce Jira issue type policy in handoff for DDL/ODPT routes: required type is `Problem`

Validation:
- Source problem must exist
- Routing project must be DDL or ODPT for standard flows
- Never silently downgrade required issue type from `Problem` to `Task`

## API Endpoints Used

- `GET /api/now/table/incident`
- `POST /api/now/table/incident`
- `PATCH /api/now/table/incident/{sys_id}`
- `GET /api/now/table/problem`
- `POST /api/now/table/problem`
- `GET /api/now/table/problem_task`
- `POST /api/now/table/problem_task`

> `/api/now/table/issue` does **not** exist on this instance and must not be used.

## Field Set for Listing

The default list projection:
- `sys_id`
- `number`
- `short_description`
- `state`
- `priority`
- `assigned_to`
- `assignment_group`
- `sys_updated_on`

## Assignment Group Scope Enforcement

- `list_incidents(...)` always applies designated assignment group filtering
- `list_incidents(assignment_group=...)` is allowed only when the value is in `SERVICENOW_ASSIGNMENT_GROUPS`
- Incident lookup by `number` or `sys_id` is rejected when the incident is outside designated groups

## Resolution Validation Standard

A valid resolution note should include:
1. Remediation action performed
2. Confirmation of service restoration
3. Follow-up recommendations if relevant

Reject low-quality notes such as:
- "fixed"
- "resolved"
- "done"

## Python Implementation

Use [servicenow_client.py](servicenow_client.py) for operational code.

Core methods:
- `list_incidents(...)`
- `list_incidents(..., exclude_resolved=True)` for unresolved-only workflows
- `create_incident(...)`
- `add_work_note(...)`
- `assign_incident(...)`
- `set_priority_by_matrix(...)`
- `create_problem_from_incident(...)` — returns `{problem, incident}`
- `create_issue_from_problem(...)` — optional native helper mode that creates PTASK
- `detect_native_jira_from_problem_capability(...)` — native capability classification
- `create_native_jira_issue_from_problem(...)` — native route execution when available
- `create_issue_from_problem_with_routing(...)` — native or Jira delegation routing API
- `resolve_incident(...)`

> **Credential loading:** `ServiceNowConfig.from_env()` uses `os.getenv()`.  When
> loading `.env` with `python-dotenv`, passwords containing a trailing `#` are
> silently truncated (dotenv treats unquoted `#` as a comment).  Always read `.env`
> directly (line-by-line split on `=`) or quote the value: `PASSWORD="value#"`.

## Usage Example

```python
from servicenow_client import ServiceNowClient

client = ServiceNowClient.from_env()

# List incidents for designated groups, additionally filtered by user
items = client.list_incidents(assigned_to="john.doe", limit=20)

# Create new incident from scratch
new_inc = client.create_incident(
    short_description="Payroll sync job failed in production",
    description="Nightly payroll import failed with API timeout and partial writes.",
    caller_id="john.doe",
    assignment_group="Service Desk",
    impact="2",
    urgency="2",
    work_note="[INTAKE] Created from support request and routed to designated team.",
)

# Add work note
client.add_work_note(
    incident_number="INC0012345",
    work_note="[INVESTIGATION] Restarted dependent middleware and validated service health.",
)

# Assign or reassign owner
client.assign_incident(
    incident_number="INC0012345",
    assigned_to="john.doe",
    allow_reassign=True,
    work_note="[ASSIGNMENT] Ownership moved to on-call engineer.",
)

# Change priority to P3 by matrix (updates impact/urgency)
client.set_priority_by_matrix(
    incident_number="INC0012345",
    target_priority="P3",
    work_note="[PRIORITY] Business impact reassessed; set to moderate.",
)

# Raise PRB from incident and link records
linked = client.create_problem_from_incident(
    incident_number="INC0012345",
    problem_short_description="Recurring payroll sync failures",
    problem_description="Multiple payroll incidents indicate a systemic integration issue.",
    work_note="[PRB] Linked incident to new problem for root-cause analysis.",
)

# PRB mapped fields are auto-populated from incident:
# origin_task, category/subcategory defaults, problem_statement,
# description, service_offering, and cmdb_ci.

# Raise issue from problem with fixed project selection
issue_linked = client.create_issue_from_problem(
    problem_number="PRB0012345",
    issue_short_description="Customer checkout outage follow-up",
    issue_description="Track delivery remediation tasks tied to PRB root cause.",
)
# select_project is always set to Digital Delivery.

# Resolve incident
client.resolve_incident(
    incident_number="INC0012345",
    close_code="Solved (Permanently)",
    close_notes=(
        "Applied configuration correction to queue consumer, restarted service, "
        "and confirmed normal processing for 30 minutes without recurrence."
    ),
    work_note="[RESOLUTION] Incident moved to resolved state after validation.",
)
```

## Error Handling Expectations

- Config errors: missing env vars or malformed host
- Auth errors: unauthorized or forbidden
- Data errors: incident not found or invalid update fields
- Workflow errors: invalid state transitions

Each error should return:
- clear category
- concise reason
- remediation guidance

## Extension Points

Future behavior enhancements can include:
- configurable state mappings by tenant
- custom mandatory fields per assignment group
- bulk incident update workflows
- SLA-aware prioritization support
