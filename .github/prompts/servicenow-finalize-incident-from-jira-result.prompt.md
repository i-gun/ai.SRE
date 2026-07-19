# ServiceNow Prompt: Finalize Incident From Issue Result

Use this prompt with the ServiceNow agent after issue creation is completed (ServiceNow PTASK preferred, Jira fallback).

```text
@ServiceNow, finalize incident <INC_NUMBER> using issue result and close workflow strictly.

INPUT CONTRACT:
- incident_number
- problem_number
- issue_source (servicenow_problem_task | jira_fallback)
- issue_number_or_key
- issue_url (optional for PTASK)
- issue_status

STRICT EXECUTION POLICY:

1) Validate required inputs:
   - incident_number, problem_number, issue_number_or_key are required
   - issue_status must be success or partial_success; if failed, do not resolve incident

2) Backpropagate issue:
   - Set incident field Vendor Ticket = <issue_number_or_key>

3) Add resolution notes:
   - If issue_source=servicenow_problem_task, state problem <problem_number> and PTASK <issue_number_or_key> were raised
   - If issue_source=jira_fallback, state problem <problem_number> and Jira issue <issue_number_or_key> were raised
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
