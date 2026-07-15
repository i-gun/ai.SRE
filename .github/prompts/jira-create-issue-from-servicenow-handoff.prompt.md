# Jira Prompt: Create Issue From ServiceNow Handoff (Strict)

Use this prompt with the Jira agent after ServiceNow confirms incident and problem context.

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

STRICT EXECUTION POLICY:

1) Validate routing:
   - If routing_project=DDL, create in project DDL
   - If routing_project=ODPT, create in project ODPT
   - If routing_project is missing or invalid, fail with reason

2) Resolve custom fields by name before create/update:
   - Banner
   - Team
   - ServiceNow Priority
   - ServiceNow #
   - If any required field for selected route is unavailable, STOP with failed status and diagnostics

3) Create issue summary/description from incident and problem context:
   - Include incident number and problem number
   - Include incident priority and summary
   - Include concise remediation ownership statement

4) Apply mapping by route:
   DDL route:
   - Labels: L2toL3, ODP, SRE
   - Banner: CanadianTire
   - Priority: Major
   - Team: Site Reliability Engineering
   - ServiceNow Priority: <Incident_Priority>
   - ServiceNow #: <Problem_Number>, <Incident_Number>

   ODPT route:
   - Labels: L2toL3, ODP
   - Banner: CanadianTire
   - Priority: Minor
   - ServiceNow Priority: <Incident_Priority>
   - ServiceNow #: <Problem_Number>, <Incident_Number>

5) Verify create/update:
   - Re-fetch issue and verify labels and mapped fields

6) Return strict result payload:
   - issue_key
   - issue_url
   - project
   - labels_before
   - labels_after
   - field_mapping_applied (list)
   - status: success | partial_success | failed
   - failure_reason (if any)
```

Example:
`@Jira, create issue from ServiceNow handoff using strict field mapping and return a structured result.`
