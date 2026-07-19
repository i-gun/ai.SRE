# ServiceNow Prompt: Strict Incident to Problem to Issue Flow (ServiceNow-First)

Use this prompt with the ServiceNow agent to run a deterministic incident enrichment, fresh problem creation, ServiceNow-first issue creation, optional Jira fallback, and incident resolution flow.

```text
@ServiceNow, process incident <INC_NUMBER> with requested priority <TARGET_PRIORITY> and execute strict incident -> problem -> issue flow (ServiceNow-first, Jira fallback).

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

6) Always create a NEW PRB from incident:
   - Do NOT reuse incident.problem_id
   - Do NOT search by origin_task
   - Always create a fresh problem record from current incident state and notes/comments
   - Link incident.problem_id to the newly created PRB sys_id

7) Problem field requirements (on create):
   - Origin task = <Incident_Number> (required)
   - Category = <Incident_Category> (required)
   - Subcategory = <Incident_Subcategory> (required)
   - Service offering = <Incident_Service_offering> (required)
   - Configuration item = <Incident_Configuration_item> (required)
   - Assignment group = "IT - Epam - L2 - ODP" (required)
   - Problem statement = <Incident_Short_description> (required)
   - Description = <Incident_Description> (required)
   - Backpropagate problem number to incident field Problem

8) Preferred issue creation route = ServiceNow "Create Issue" behavior:
   - First, create a `problem_task` (PTASK) from the created PRB via ServiceNow (`/api/now/table/problem_task`)
   - Route by final incident priority:
     - P3 -> set `u_jira_project` to DDL (Digital Delivery)
     - P4 or P5 -> set `u_jira_project` to ODPT (One Digital Platform)
     - P1 or P2 -> ask explicit routing confirmation before setting `u_jira_project`
   - Verify PTASK creation returns number and sys_id
   - Only if PTASK creation is blocked/fails (capability, ACL, validation, or platform error), fallback to @Jira using handoff contract prompt

9) After issue creation succeeds:
   - If ServiceNow PTASK succeeded:
     - Set incident Vendor Ticket = <PTASK_NUMBER>
     - Add resolution note that PRB <PRB_NUMBER> and PTASK <PTASK_NUMBER> were raised for RCA and mitigation
   - If Jira fallback succeeded:
     - Set incident Vendor Ticket = <ISSUE_KEY>
     - Add resolution note that PRB <PRB_NUMBER> and Jira issue <ISSUE_KEY> were raised for RCA and mitigation, include issue URL
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
     - number, created_mode, status
   - issue:
     - route_used (servicenow_problem_task | jira_fallback)
     - number_or_key
     - project
     - url
     - status
   - overall_status: success | partial_success | skipped | failed
   - failure_reason (if not success)

11) Failure guardrails:
   - Never resolve incident if both issue routes fail (ServiceNow PTASK + Jira fallback)
   - Never silently skip required fields; fail with explicit step and reason
   - If custom/target fields are unavailable, return partial_success or failed with precise diagnostics

Do not use Confluence or any external knowledge source for this operation.
```

Example:
`@ServiceNow, process incident INC0044438 with requested priority P3 and execute strict incident -> problem -> issue flow (ServiceNow-first, Jira fallback).`
