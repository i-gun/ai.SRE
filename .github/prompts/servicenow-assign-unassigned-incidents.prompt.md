# ServiceNow Prompt: Assign Active Unassigned Incidents

Use this prompt with the ServiceNow agent to fetch active unassigned incidents in scoped groups and assign them to your configured user.

```text
@ServiceNow, fetch all active unassigned incidents in my scoped assignment groups, then assign each incident to my configured ServiceNow user.

Requirements:
1) List matching incidents first (number, short description, priority, assignment group, sys_id).
2) Confirm total count.
3) Assign each incident to my configured ServiceNow user (assigned_to from my environment/config).
4) For each matched incident, update:
   - Category = 'Application'
   - Subcategory = 'E-Commerce'
   - Service offering = existing incident Configuration item value (cmdb_ci) if present; otherwise leave empty
5) Add a work note to each reassigned incident: "Auto-assigned for triage by configured ServiceNow user."
6) Return a final summary with:
   - Successfully assigned incidents
   - Any skipped/failed incidents with reason
   - Remaining active unassigned incidents (if any)
```
