---
name: "ServiceNow Resolve RTCDP Incidents"
description: "Resolve active non-resolved RTCDP incidents in scoped assignment groups with standardized closure fields and strict resolved-state filtering."
argument-hint: "Optional override: change Jira ticket/vendor ticket or refine short-description prefix before running."
agent: "ServiceNow"
---

# ServiceNow Prompt: Resolve Active Non-Resolved RTCDP Incidents

Use this prompt with the ServiceNow agent to find active, non-resolved RTCDP incidents in scoped groups and resolve them with standardized closure fields.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@ServiceNow, fetch all active incidents not in state 'Resolved' in my scoped assignment groups where short description starts with "Triggered : ", assign to your configured user if unassigned, then resolve each incident.

Requirements:
1) List matching incidents first (number, short description, priority, assignment group, sys_id, state).
2) Confirm total count.
3) For unassigned incidents, assign to your configured ServiceNow user (assigned_to from my environment/config).
4) For each matched incident, update:
   - Category = 'Application'
   - Subcategory = 'E-Commerce'
   - Service offering = 'Adobe RTCDP - CTC'
   - Vendor Ticket = 'DDL-29601'
   - Close notes = 'Implemented remediation based on Jira analysis ticket https://canadian-tire.atlassian.net/browse/DDL-29601, validated service behavior post-change, and completed operational handoff with traceability to DDL-29601 for follow-up monitoring and audit continuity.'
   - State = 'Resolved'
   - Resolution code = 'Fixed'
5) Return a final summary with:
   - Successfully resolved incidents
   - Any skipped/failed incidents with reason
   - Remaining active incidents matching filter (if any)

DO NOT:
- Use @Confluence skill for this prompt; close notes are already provided and must be used as-is.
- Fetch or update incidents already in state 'Resolved'.
- Treat all of these as resolved and exclude them: `6`, `6 - Resolved`, `Resolved` (or any display value containing `Resolved`).
- Use both query-time and client-side state checks before assignment or resolution actions.
```