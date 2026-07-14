# ServiceNow Prompt: Resolve Active Non-Resolved Gigya Incidents

Use this prompt with the ServiceNow agent to find active, non-resolved Gigya incidents in scoped groups and resolve them with standardized closure fields.

```text
@ServiceNow, fetch all active incidents not in state 'Resolved' in my scoped assignment groups where short description starts with "accounts.verifyEmail query result is >", assign to your configured user if unassigned, then resolve each incident.

Requirements:
1) List matching incidents first (number, short description, priority, assignment group, sys_id, state).
2) Confirm total count.
3) For unassigned incidents, assign to your configured ServiceNow user (assigned_to from my environment/config).
4) For each matched incident, update:
   - Category = 'Application'
   - Subcategory = 'E-Commerce'
   - Service offering = 'Gigya'
   - Vendor Ticket = 'DDL-31876'
   - Close notes = 'RCA and remediation implementation is under scope of Jira ticket https://canadian-tire.atlassian.net/browse/DDL-31876.'
   - State = 'Resolved'
   - Resolution code = 'Fixed'
5) Return a final summary with:
   - Successfully resolved incidents
   - Any skipped/failed incidents with reason
   - Remaining active incidents matching filter (if any)

DO NOT:
- Use @Confluence skill for this prompt; close notes are already provided and must be used as-is.
- Fetch or update incidents already in state 'Resolved'.
```