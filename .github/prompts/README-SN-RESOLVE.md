# Prompt Pack: ServiceNow Incident Resolution

This prompt pack contains reusable ServiceNow resolution prompts for targeted incident classes with strict non-resolved filtering and standardized closure fields.

Files:
- [.github/prompts/servicenow-resolve-gigya-incidents.prompt.md](.github/prompts/servicenow-resolve-gigya-incidents.prompt.md)
  Resolve active non-resolved Gigya incidents in scoped assignment groups.
- [.github/prompts/servicenow-resolve-rtcdp-incidents.prompt.md](.github/prompts/servicenow-resolve-rtcdp-incidents.prompt.md)
  Resolve active non-resolved RTCDP incidents in scoped assignment groups.
- [.github/prompts/servicenow-resolve-sfsc-incidents.prompt.md](.github/prompts/servicenow-resolve-sfsc-incidents.prompt.md)
  Resolve active non-resolved SFSC incidents in scoped assignment groups.

## Invocation Examples

1. Gigya
@ServiceNow, fetch all active incidents not in state 'Resolved' in my scoped assignment groups where short description starts with "accounts.verifyEmail query result is >", assign to your configured user if unassigned, then resolve each incident.

2. RTCDP
@ServiceNow, fetch all active incidents not in state 'Resolved' in my scoped assignment groups where short description starts with "Triggered : ", assign to your configured user if unassigned, then resolve each incident.

3. SFSC
@ServiceNow, fetch all active incidents not in state 'Resolved' in my scoped assignment groups where short description starts with "Triggered : ", assign to your configured user if unassigned, then resolve each incident.

## Shared Guardrails

- Exclude incidents already resolved using both query-time and client-side checks.
- Treat all of these as resolved: 6, 6 - Resolved, Resolved, and any display value containing Resolved.
- Assign unassigned incidents before applying closure updates.
- Use provided close notes as-is in each prompt; do not fetch from Confluence.
