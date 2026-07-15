# ServiceNow Prompt: Finalize Incident From Jira Result

Use this prompt with the ServiceNow agent after Jira issue creation is completed.

```text
@ServiceNow, finalize incident <INC_NUMBER> using Jira result and close workflow strictly.

INPUT CONTRACT:
- incident_number
- problem_number
- issue_key
- issue_url
- jira_status

STRICT EXECUTION POLICY:

1) Validate required inputs:
   - incident_number, problem_number, issue_key are required
   - jira_status must be success or partial_success; if failed, do not resolve incident

2) Backpropagate Jira issue:
   - Set incident field Vendor Ticket = <issue_key>

3) Add resolution notes:
   - State that problem <problem_number> and issue <issue_key> were raised for RCA and mitigation
   - Include issue URL
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
`@ServiceNow, finalize incident INC0044438 using Jira result and close workflow strictly.`
