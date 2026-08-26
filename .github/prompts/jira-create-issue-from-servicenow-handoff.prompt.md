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
- incident_sys_id
- incident_priority (final)
- incident_impact (final)
- incident_urgency (final)
- problem_number
- problem_url (optional)
- problem_sys_id (optional)
- incident_summary
- incident_description
- canonical_context (required object)
- canonical_short_description (required normalized string)
- canonical_description (required normalized string)
- context_fingerprint (required; internal correlation value for this handoff call only)
- flow_run_id (required; internal correlation value for this handoff call only)
- routing_project (DDL or ODPT)
- required_issue_type (must be `Problem` for DDL/ODPT unless explicit override is approved)
- issue_type_override (optional)
- issue_type_override_approved (boolean, required when override is provided)
- retry_mode (optional: first_attempt | retry)
- existing_issue_key (optional)
- affects_version (optional; latest release version resolved by ServiceNow via `ConfluenceClient.resolve_release_calendar()`)
- incident_attachments (optional; list of `{filename, content_base64, content_type}` support files from the source incident)

STRICT EXECUTION POLICY:

0) Validate canonical context contract:
   - `canonical_context`, `canonical_short_description`, `canonical_description`, `context_fingerprint`, and `flow_run_id` are mandatory.
   - If `canonical_description` is empty, fail with explicit reason (`MISSING_CANONICAL_DESCRIPTION`).
   - `canonical_short_description` and `canonical_description` MUST be the incident's raw `short_description`/`description`
     values (whitespace-trim only). Do not regenerate, paraphrase, summarize, or otherwise enrich these values —
     copy them into Jira fields as-is.
   - `context_fingerprint` and `flow_run_id` are internal orchestration bookkeeping only. Never write them, or
     any other internal flow-execution detail, into the issue `summary`, `description`, or comments. They are
     used only for this handoff call's own idempotency checks and returned in the result payload (Step 6).

1) Validate routing:
   - If routing_project=DDL, create in project DDL
   - If routing_project=ODPT, create in project ODPT
   - If routing_project is missing or invalid, fail with reason

1.1) Validate issue type policy:
   - For routing_project in {DDL, ODPT}, default required issue type is `Problem`
   - If issue_type_override is provided, require issue_type_override_approved=true
   - If approved override is absent, create as `Problem` only
   - If `Problem` issue type is unavailable in target project, STOP with failed status and diagnostics

1.2) Idempotency and retry handling:
    - If retry_mode=retry or existing_issue_key is provided:
       - Re-fetch existing issue when key is supplied.
       - Search for an existing issue in target project matching incident_number + problem_number via the
         `ServiceNow #` field and/or the required summary format; do not rely on any fingerprint/hash marker
         embedded in issue text (none is ever written there).
    - If matching issue exists, compare its stored summary/description directly against the current
      canonical_short_description/canonical_description; treat as parity-passing only on exact match
      (whitespace-trim tolerated).
    - If matching issue exists and passes parity, reuse it and skip create.
    - If matching issue exists but parity fails, return `failed` and require explicit operator recreate approval.
    - Never create duplicate issues for the same incident_number + problem_number in a single run.

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
   - Summary format (required): `<INC_NUMBER> | <PRB_NUMBER> | <canonical_short_description>`
   - Description must include all required blocks:
     1. Source Incident: number, sys_id, and reference
     2. Source Problem: number, sys_id/url when available
     3. Incident Description: full canonical_description, copied as-is (whitespace-trim only; no paraphrase/summary/enrichment)
     4. Final Priority/Impact/Urgency
     5. Service metadata from canonical_context (category/subcategory/service_offering/cmdb_ci)
   - Do NOT include flow_run_id, context_fingerprint, or any other internal flow-execution detail in the
     summary, description, or any comment added to the issue; those remain internal-only (Step 6 result payload).
   - If any block is missing before create, STOP with failed status and diagnostics.

3.1) Set Affects Version/s (DDL/ODPT routes only):
   - When `affects_version` is provided in the input contract, apply it to the created issue's system
     `Affects Version/s` field via `update_issue(issue_key, fields={"versions": [{"name": affects_version}]})`.
   - If `affects_version` is missing or the field update fails, record a diagnostics warning
     (`AFFECTS_VERSION_NOT_APPLIED`) and continue — this is supportive metadata, not a create-blocking field.

3.2) Propagate incident support files (optional, non-blocking):
   - When `incident_attachments` is provided, decode each entry and call
     `add_attachment(issue_key, filename=..., content=..., content_type=...)` for every file.
   - Record `attachments_uploaded` (count + filenames) and any per-file failures in diagnostics
     (`ATTACHMENT_UPLOAD_FAILED`); attachment failures never fail the overall create/handoff.

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
   - Verify summary matches required summary format
   - Verify description contains all mandatory blocks
   - Verify incident and problem identifiers in Jira match input contract exactly (structural reference
     match via Source Incident/Source Problem blocks and the `ServiceNow #` field; no fingerprint marker
     is ever written to or read from issue text)

5.1) Status policy for Team:
   - Return `success` only when Team mapping is required and Team is verified (id + name/title) after update.
   - Return `partial_success` only when Team UUID resolution/update is the only failed part.
   - Return `failed` when required issue type/routing/core field mappings fail.

5.2) Parity verification policy:
   - `parity_verified=true` only when summary, description blocks, and incident/problem identifiers all match.
   - If issue exists but parity verification fails, set status=`failed_parity_validation`.
   - Do not return `success` or `partial_success` when parity verification fails.

6) Return strict result payload:
   - issue_key
   - issue_url
   - project
   - issue_type_requested
   - issue_type_created
   - issue_type_verified
   - route_used (jira_agent_delegation)
   - flow_run_id (internal correlation only; never written to issue text)
   - context_fingerprint (internal correlation only; never written to issue text)
   - checkpoints: input_validated, route_validated, issue_created_or_reused, fields_mapped, parity_verified
   - issue_reused (true/false)
   - labels_before
   - labels_after
   - field_mapping_applied (list)
   - affects_version_applied (true/false)
   - attachments_uploaded (count + filenames)
   - parity_verified (true/false)
   - status: success | partial_success | failed | failed_parity_validation
   - failure_reason (if any)
   - diagnostics:
     - missing_blocks
     - mismatch_details
     - reason_code
```

Example:
`@Jira, create issue from ServiceNow handoff using strict field mapping and return a structured result.`
