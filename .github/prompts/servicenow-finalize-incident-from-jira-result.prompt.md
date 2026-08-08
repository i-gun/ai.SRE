# ServiceNow Prompt: Finalize Incident From Issue Result

Use this prompt with the ServiceNow agent after issue creation is completed (native ServiceNow->Jira preferred, Jira-agent delegation fallback).

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@ServiceNow, finalize incident <INC_NUMBER> using issue result and close workflow strictly.

INPUT CONTRACT:
- incident_number
- problem_number
- issue_source (servicenow_native_jira | jira_agent_delegation)
- issue_number_or_key
- issue_url (optional)
- issue_status

STRICT EXECUTION POLICY:

1) Validate required inputs:
   - incident_number, problem_number, issue_number_or_key are required
   - issue_status must be success or partial_success; if failed, do not resolve incident

2) Backpropagate issue:
   - Set incident field Vendor Ticket = <issue_number_or_key>

3) Add resolution notes:
   - If issue_source=servicenow_native_jira, state problem <problem_number> and Jira issue <issue_number_or_key> were raised via native ServiceNow integration
   - If issue_source=jira_agent_delegation, state problem <problem_number> and Jira issue <issue_number_or_key> were raised via Jira agent delegation
   - Include issue URL when available
   - Include that downstream remediation ownership has been transferred to proper teams

4) Resolve incident:
   - State = Resolved
   - Resolution code = Fixed

5) Verify and return strict result:
   - incident_number
   - vendor_ticket
   - state
   - resolution_code
   - status: success | partial_success | failed
   - failure_reason (if any)
```

Example:
`@ServiceNow, finalize incident INC0044438 using issue result and close workflow strictly.`
