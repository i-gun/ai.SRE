---
name: "Incident to Problem to Issue Flow"
description: "Run a deterministic incident enrichment, fresh problem creation, native ServiceNow->Jira routing when available, Jira-agent delegation otherwise, and strict incident resolution."
agent: "ServiceNow"
---

# ServiceNow Prompt: Strict Incident to Problem to Issue Flow (Native ServiceNow->Jira Preferred)

Use this prompt with the ServiceNow agent to run deterministic incident enrichment, fresh problem creation, native ServiceNow->Jira routing when available, Jira-agent delegation otherwise, and strict incident resolution.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@ServiceNow, process incident <INC_NUMBER> with requested priority <TARGET_PRIORITY> and execute strict incident -> problem -> issue flow (native ServiceNow->Jira preferred, Jira-agent fallback).

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
   - Origin task = <Incident reference> (required; set via incident sys_id so the Problem form displays the correct Incident Number)
   - Category = <Incident_Category> (required)
   - Subcategory = <Incident_Subcategory> (required)
   - Service offering = <Incident_Service_offering> (required)
   - Configuration item = <Incident_Configuration_item> (required)
   - Assignment group = "IT - Epam - L2 - ODP" (required)
   - Problem statement = <Incident_Short_description> (required)
   - Description = <Incident_Description> (required)
   - Verify Origin task displays the expected incident number after create; fail the flow if it is blank or mismatched
   - Backpropagate problem number to incident field Problem

8) Preferred issue creation route = native ServiceNow->Jira from PRB (capability-gated):
    - Route by final incident priority:
       - P3 -> routing_project=DDL
       - P4 or P5 -> routing_project=ODPT
       - P1 or P2 -> ask explicit routing confirmation before project selection
    - Required issue type for DDL/ODPT routes = `Problem`
    - Run native capability detection from Problem context
    - If native capability is `available`:
       - execute native ServiceNow->Jira creation path from PRB
       - verify issue identifier (Jira key or equivalent) is returned
    - If native capability is `conditionally_available` or `unavailable`:
       - delegate to @Jira with strict handoff contract
       - do NOT create PTASK as a fallback artifact in this branch

9) After issue creation succeeds:
    - If native ServiceNow->Jira succeeded:
       - Set incident Vendor Ticket = <ISSUE_KEY_OR_IDENTIFIER>
       - Add resolution note that PRB <PRB_NUMBER> and Jira issue <ISSUE_KEY_OR_IDENTIFIER> were raised for RCA and mitigation, include issue URL when available
    - If Jira delegation succeeded:
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
       - route_used (servicenow_native_jira | jira_agent_delegation)
       - number_or_key
       - required_issue_type
       - issue_type_verified
       - project
       - url
       - status
   - overall_status: success | partial_success | skipped | failed
   - failure_reason (if not success)

11) Failure guardrails:
   - Never resolve incident if both issue routes fail (native ServiceNow + Jira delegation)
   - Never downgrade required issue type from `Problem` to `Task` silently for DDL/ODPT routes
   - Never silently skip required fields; fail with explicit step and reason
   - If custom/target fields are unavailable, return partial_success or failed with precise diagnostics

Do not use Confluence or any external knowledge source for this operation.
```

Example:
`@ServiceNow, process incident INC0044438 with requested priority P3 and execute strict incident -> problem -> issue flow (native ServiceNow->Jira preferred, Jira-agent fallback).`
