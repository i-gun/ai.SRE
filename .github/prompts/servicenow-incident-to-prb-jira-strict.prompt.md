# ServiceNow Prompt: Strict Incident to Problem to Jira Flow

Use this prompt with the ServiceNow agent to run a deterministic incident enrichment, problem creation, Jira delegation, and incident resolution flow.

```text
@ServiceNow, process incident <INC_NUMBER> with requested priority <TARGET_PRIORITY> and execute strict incident -> problem -> Jira flow.

STRICT EXECUTION POLICY (must follow in order):

1) Validate input:
   - INC_NUMBER is required (e.g., INC1234)
   - TARGET_PRIORITY is required and must be one of: 1..5, P1..P5, or "priority 1".."priority 5"
   - Normalize TARGET_PRIORITY to P1..P5

2) Fetch incident first (authoritative baseline):
   - number, sys_id, state, active
   - priority, impact, urgency
   - category, subcategory
   - service_offering, cmdb_ci
   - assignment_group (name/sys_id)
   - assigned_to (identifier/display value)
   - short_description, description
   - problem_id, vendor_ticket

3) Mandatory confirmation gate on priority action:
   - Before any priority update or PRB creation, ask explicit confirmation including:
     - incident number
     - current priority
     - requested priority
     - note that matrix update uses impact/urgency only (no direct priority patch)
   - If confirmation is not explicitly given, STOP with status=skipped.

4) Incident enrichment (apply before PRB):
   - Category = "Application"
   - Subcategory = "E-Commerce"
   - Service offering = incident configuration item if present, else "Digital - New Relic Alerts - ODP"
   - Configuration item = as-is if present, else "Digital - New Relic Alerts - ODP"
   - Assignment group = as-is if present, else first allowed value from SERVICENOW_ASSIGNMENT_GROUPS
   - Assigned to = as-is if present, else currently configured ServiceNow user

5) Priority logic:
   - If normalized requested priority is P3:
     - update impact and urgency by matrix (do NOT patch priority directly)
   - Re-fetch incident and store final incident priority for downstream routing

6) Ensure one PRB only (idempotency):
   - If incident already has problem_id, reuse linked problem
   - Else search problem where origin_task == incident number
   - If found, reuse latest matching problem
   - Else create one problem only
   - Never create multiple PRBs for same incident in a single run

7) Problem field requirements (on create or reconcile):
   - Origin task = <Incident_Number> (required)
   - Category = <Incident_Category> (required)
   - Subcategory = <Incident_Subcategory> (required)
   - Service offering = <Incident_Service_offering> (required)
   - Configuration item = <Incident_Configuration_item> (required)
   - Assignment group = "IT - Epam - L2 - ODP" (required)
   - Problem statement = <Incident_Short_description> (required)
   - Description = <Incident_Description> (required)
   - Backpropagate problem number to incident field Problem

8) Delegate issue creation to @Jira:
   - Route by final incident priority:
     - P3 -> DDL (Digital Delivery)
     - P4 or P5 -> ODPT (One Digital Platform)
     - P1 or P2 -> ask explicit routing confirmation before delegation
   - Send incident and problem context to Jira using handoff contract prompt

9) After Jira result returns (issue key + url):
   - Set incident Vendor Ticket = <ISSUE_KEY>
   - Add resolution note that PRB <PRB_NUMBER> and issue <ISSUE_KEY> were raised for RCA and mitigation, include issue URL
   - Set State = Resolved
   - Set Resolution code = Fixed
   - Resolve incident

10) Return strict result payload:
   - confirmation:
     - required (true/false)
     - user_response
   - incident:
     - number, final_priority, state, vendor_ticket, status
   - problem:
     - number, reused_or_created, status
   - issue:
     - key, project, url, status
   - overall_status: success | partial_success | skipped | failed
   - failure_reason (if not success)

11) Failure guardrails:
   - Never resolve incident if Jira issue creation failed
   - Never silently skip required fields; fail with explicit step and reason
   - If custom/target fields are unavailable, return partial_success or failed with precise diagnostics

Do not use Confluence or any external knowledge source for this operation.
```

Example:
`@ServiceNow, process incident INC0044438 with requested priority P3 and execute strict incident -> problem -> Jira flow.`
