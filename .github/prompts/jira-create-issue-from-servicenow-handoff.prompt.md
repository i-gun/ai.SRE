# Jira Prompt: Create Issue From ServiceNow Handoff (Strict)

Use this prompt with the Jira agent after ServiceNow confirms incident and problem context.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@Jira, create issue from ServiceNow handoff using strict field mapping and return a structured result.

INPUT CONTRACT (from ServiceNow):
- incident_number
- incident_priority (final)
- problem_number
- problem_url (optional)
- incident_summary
- incident_description
- routing_project (DDL or ODPT)
- required_issue_type (must be `Problem` for DDL/ODPT unless explicit override is approved)
- issue_type_override (optional)
- issue_type_override_approved (boolean, required when override is provided)

STRICT EXECUTION POLICY:

1) Validate routing:
   - If routing_project=DDL, create in project DDL
   - If routing_project=ODPT, create in project ODPT
   - If routing_project is missing or invalid, fail with reason

1.1) Validate issue type policy:
   - For routing_project in {DDL, ODPT}, default required issue type is `Problem`
   - If issue_type_override is provided, require issue_type_override_approved=true
   - If approved override is absent, create as `Problem` only
   - If `Problem` issue type is unavailable in target project, STOP with failed status and diagnostics

2) Resolve custom fields by name before create/update:
   - Banner
   - Team
   - ServiceNow Priority
   - ServiceNow #
   - Team field is schema type `team` and may not return `allowedValues`; resolve Team by UUID using live issue history/project context when needed
   - For Team, prefer update payload shape: `customfield_11002: <team_uuid_string>`
   - Do not require Team `allowedValues` for acceptance; Team must be treated as UUID-based mapping
   - If any required field for selected route is unavailable, STOP with failed status and diagnostics

3) Create issue summary/description from incident and problem context:
   - Include incident number and problem number
   - Include incident priority and summary
   - Include concise remediation ownership statement

4) Apply mapping by route:
   - DDL route:
     - Labels: L2toL3, ODP, SRE
     - Banner: CanadianTire
     - Priority: Major
     - Team: Site Reliability Engineering
     - ServiceNow Priority: <Incident_Priority>
     - ServiceNow #: <Problem_Number>, <Incident_Number>

   - ODPT route:
     - Labels: L2toL3, ODP
     - Banner: CanadianTire
     - Priority: Minor
     - ServiceNow Priority: <Incident_Priority>
     - ServiceNow #: <Problem_Number>, <Incident_Number>

4.1) Team mapping execution strategy (required for DDL route):
   - Use a two-phase write for Team:
     - Phase A: create issue with non-Team fields.
     - Phase B: update Team using `customfield_11002` with resolved team UUID.
   - Team UUID resolution order:
     - First: trusted configured UUID (if provided by policy/runtime context).
     - Second: derive from live project issue history where Team is populated and name matches.
   - If Team UUID cannot be resolved, return `partial_success` only if issue creation and all other strict mappings are verified.

5) Verify create/update:
   - Re-fetch issue and verify labels and mapped fields
   - Verify Team by both id and display name/title when Team mapping is required
   - Verify actual Jira issue type equals requested/required issue type

5.1) Status policy for Team:
   - Return `success` only when Team mapping is required and Team is verified (id + name/title) after update.
   - Return `partial_success` only when Team UUID resolution/update is the only failed part.
   - Return `failed` when required issue type/routing/core field mappings fail.

6) Return strict result payload:
   - issue_key
   - issue_url
   - project
   - issue_type_requested
   - issue_type_created
   - issue_type_verified
   - labels_before
   - labels_after
   - field_mapping_applied (list)
   - status: success | partial_success | failed
   - failure_reason (if any)
```

Example:
`@Jira, create issue from ServiceNow handoff using strict field mapping and return a structured result.`
