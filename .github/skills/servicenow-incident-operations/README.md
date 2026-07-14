# ServiceNow Incident Operations Skill

This skill enables secure ServiceNow incident operations from the local project using credentials from `.env`.

## Capabilities

- List incidents assigned to a user and/or assignment group
- Create incidents from scratch with required field validation
- Assign or reassign incidents
- Add work notes to incidents
- Change priority via impact/urgency matrix (do not patch priority directly)
- Raise problem (PRB) from incident and link records
- Raise issue from problem with fixed project selection
- Resolve incidents with validation gates
- Apply minimal controlled updates to operational fields

## Required Environment Variables

Set these in `.env`:

- `SERVICENOW_HOST`
- `SERVICENOW_USERNAME`
- `SERVICENOW_PASSWORD`
- `SERVICENOW_ASSIGNMENT_GROUPS` (comma-separated allowlist of assignment group names or sys_ids)

## Key Files

- `SKILL.md` - behavior and capability definition
- `servicenow_client.py` - implementation for ServiceNow incident operations

## Quick Examples

```python
from servicenow_client import ServiceNowClient

client = ServiceNowClient.from_env()

incidents = client.list_incidents(assigned_to="john.doe", limit=10)
print(f"Found {len(incidents)} incidents")

# Create new incident
created = client.create_incident(
	short_description="VPN authentication failures for remote users",
	description="Users report MFA loop and cannot establish VPN sessions.",
	caller_id="john.doe",
	assignment_group="Service Desk",
	impact="2",
	urgency="2",
	work_note="[INTAKE] Created via support channel and triaged.",
)

# Reassign incident ownership
client.assign_incident(
	incident_number="INC0038826",
	assigned_to="jane.doe",
	allow_reassign=True,
	work_note="[ASSIGNMENT] Reassigned based on support rota.",
)

# Raise priority to P3 by setting impact/urgency from matrix
client.set_priority_by_matrix(
	incident_number="INC0038826",
	target_priority="P3",
	work_note="[PRIORITY] Business impact reassessed; escalating to P3.",
)

# Raise PRB from incident and link
linked = client.create_problem_from_incident(
	incident_number="INC0038826",
	problem_short_description="Recurring VPN MFA failures",
	problem_description="Multiple incidents indicate a systemic issue in VPN identity flow.",
	work_note="[PRB] Incident linked to problem for root-cause analysis.",
)

# Raise issue from problem
issue_linked = client.create_issue_from_problem(
	problem_number="PRB0038826",
	issue_short_description="Digital delivery remediation stream",
	issue_description="Track delivery fixes and rollout tasks for the linked problem.",
)
```

Issue mapping rule applied during create_issue_from_problem(...):
- Select Project <- Digital Delivery

PRB mapping rules applied from source incident during create_problem_from_incident(...):
- Origin task <- incident number
- Category <- Application
- Subcategory <- E-Commerce
- Problem statement <- incident short description
- Description <- incident description
- Service offering <- incident cmdb_ci / Configuration item (blank if empty)
- Configuration item <- incident cmdb_ci (blank if empty)

All incident retrieval is automatically constrained to `SERVICENOW_ASSIGNMENT_GROUPS`.

Priority matrix default pairs used by `set_priority_by_matrix(...)`:
- P1 -> impact=1, urgency=1
- P2 -> impact=1, urgency=2
- P3 -> impact=2, urgency=2
- P4 -> impact=2, urgency=3
- P5 -> impact=3, urgency=3

## Safety Notes

- Never commit `.env`
- Never print passwords in logs
- Validate close notes before resolving incidents
- Prefer adding work notes before changing terminal states
