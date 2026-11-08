# Skill Pack: ServiceNow Incident Resolution

This skill pack links to reusable ServiceNow workflows for targeted incident classes with strict non-resolved filtering and standardized closure fields.

## Reuse-First Policy

- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

Skills:
- [servicenow-resolve-incident-strict](../skills/servicenow-resolve-incident-strict/SKILL.md)
  Resolve a single incident with required input gates (incident number, resolution code, resolution notes) and optional linkage fields.
- [servicenow-resolve-gigya-incidents](../skills/servicenow-resolve-gigya-incidents/SKILL.md)
  Resolve active non-resolved Gigya incidents in scoped assignment groups.
- [servicenow-resolve-rtcdp-incidents](../skills/servicenow-resolve-rtcdp-incidents/SKILL.md)
  Resolve active non-resolved RTCDP incidents in scoped assignment groups.
- [servicenow-resolve-sfsc-incidents](../skills/servicenow-resolve-sfsc-incidents/SKILL.md)
  Resolve active non-resolved SFSC incidents in scoped assignment groups.

## Invocation Examples

1. Gigya
@ServiceNow, fetch all active incidents not in state 'Resolved' in my scoped assignment groups where short description starts with "accounts.verifyEmail query result is >", assign to your configured user if unassigned, then resolve each incident.

2. Single Incident (strict gates)
@ServiceNow, resolve incident INC0054908 with resolution code label "No Action Taken" and resolution notes "Validated no customer impact; monitoring remains stable." Optional fields: parent incident INC0054000, problem PRB0040546, vendor ticket DDL-40001.

3. RTCDP
@ServiceNow, fetch all active incidents not in state 'Resolved' in my scoped assignment groups where short description starts with "Triggered : ", assign to your configured user if unassigned, then resolve each incident.

4. SFSC
@ServiceNow, fetch all active incidents not in state 'Resolved' in my scoped assignment groups where short description starts with "Triggered : ", assign to your configured user if unassigned, then resolve each incident.

## Shared Guardrails

- Exclude incidents already resolved using both query-time and client-side checks.
- Treat all of these as resolved: 6, 6 - Resolved, Resolved, and any display value containing Resolved.
- Assign unassigned incidents before applying closure updates.
- Use provided close notes as-is in each prompt; do not fetch from Confluence.
- For single-incident strict flow, require all gates before mutation: incident number, resolution code, resolution notes.
