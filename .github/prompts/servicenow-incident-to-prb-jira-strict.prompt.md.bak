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

2A) Build canonical context payload (single source of truth):
    - Construct `canonical_context` immediately after incident fetch with fields:
       - incident_number, incident_sys_id
       - short_description_raw, description_raw
       - category, subcategory, service_offering, cmdb_ci
       - assignment_group, assigned_to
    - `description_raw` MUST be copied byte-identical from the incident `description` field into
      every downstream artifact (Problem, Jira). Only trailing/leading whitespace-trim is permitted;
      paraphrasing, summarizing, restructuring, or adding synthesized content is prohibited.
    - `short_description_raw` follows the same as-is rule for the incident `short_description` field;
      only single-line whitespace normalization is permitted (required because it is a single-line
      ServiceNow/Jira field), never rewording.
    - If `description_raw` is empty:
       - set `description_raw` = "No incident description provided in source incident <INC_NUMBER>."
       - record warning code `DESCRIPTION_EMPTY_FALLBACK_APPLIED`
       - this is the only permitted exception to the as-is copy rule, and it must be logged as such
    - Compute `context_fingerprint` as SHA256 of the raw narrative and routing metadata.
    - Persist canonical_context and context_fingerprint for all downstream creates and validations.
    - PRB and Jira narrative fields MUST use canonical_context as the only text source, copied as-is.

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

6) PRB creation policy (fresh-on-first-run, idempotent-on-retry):
   - First attempt: create a NEW PRB from incident.
   - Retry behavior: before creating another PRB, search for a PRB already linked to this incident
     (via incident.problem_id, or a problem whose `first_reported_by_task`/`origin_task` resolves to this
     incident) and reuse it when found.
   - Do NOT treat pre-existing incident.problem_id as authoritative unless its Problem statement/description
     still match the current canonical short_description_raw/description_raw (direct field comparison).
   - `flow_run_id` and `context_fingerprint` are internal orchestration bookkeeping only. Never write them,
     or any other internal flow-execution detail (flow name, run id, hashes, checkpoint names), into
     incident/problem `work_notes`, `description`, or comments. Keep them solely in the structured result
     payload (Step 10) returned to the caller.
   - Link incident.problem_id to the effective PRB sys_id.
   - Never create more than one new PRB for the same incident when an existing linked/parity-matching PRB is found.

7) Problem field requirements (on create):
   - Origin task = <Incident reference> (required; set via incident sys_id so the Problem form displays the correct Incident Number)
   - Category = <Incident_Category from canonical_context> (required)
   - Subcategory = <Incident_Subcategory from canonical_context> (required)
   - Service offering = <Incident_Service_offering from canonical_context> (required)
   - Configuration item = <Incident_Configuration_item from canonical_context> (required)
   - Assignment group = "IT - Epam - L2 - ODP" (required)
   - Problem statement = <Incident_Short_description_raw> (required, copied as-is)
   - Description = <Incident_Description_raw> (required, copied as-is; no rephrasing/enrichment)
   - Verify linkage and parity after create; fail flow when mismatched:
     - Prefer `origin_task` display verification when field is available.
     - If `origin_task` is unavailable on this instance, verify equivalent linkage field (for example `first_reported_by_task`) resolves to expected incident.
     - Problem statement must equal canonical short description.
     - Problem description must equal canonical description (as-is copy; no normalization beyond whitespace-trim).
   - Backpropagate problem number to incident field Problem

7A) Origin task / first_reported_by_task backfill (break-point fix):
   - `origin_task` is not reliably readable on this instance (platform findings memory). Relying on it
     alone leaves linkage verification with nothing to check when it silently fails to persist.
   - Immediately after Problem create, call `update_problem_fields(problem_sys_id=<PRB sys_id>, fields={"first_reported_by_task": <incident_sys_id>})`.
   - Treat `first_reported_by_task` as the **authoritative** linkage-verification field on this instance;
     `origin_task` remains best-effort/secondary evidence only.
   - If the `first_reported_by_task` backfill write fails, record it as a diagnostics warning
     (`FIRST_REPORTED_BY_TASK_BACKFILL_FAILED`) but do not block PRB stage success on its own —
     PRB stage success still requires the core create in Step 7 to have succeeded.

8) Preferred issue creation route = native ServiceNow->Jira from PRB (capability-gated):
    - Route by final incident priority:
       - P3 -> routing_project=DDL
       - P4 or P5 -> routing_project=ODPT
       - P1 or P2 -> ask explicit routing confirmation before project selection; if not explicitly confirmed, STOP with status=skipped
    - Required issue type for DDL/ODPT routes = `Problem`
    - Resolve `current_release_version` via `ConfluenceClient.resolve_release_calendar()` (existing
      promoted resolver, same one used by the CVE DDL handoff) for the `Affects Version/s` mapping in
      Step 8B; do not build a new release-resolution mechanism for this flow.
    - Build mandatory issue payload from canonical_context:
       - summary = "<INC_NUMBER> | <PRB_NUMBER> | <short_description_raw>"
       - description MUST include blocks:
         1. Source Incident (number and reference)
         2. Source Problem (number and reference)
         3. Incident Description (full description_raw, copied as-is; no rephrasing/enrichment)
         4. Priority/Impact/Urgency (final values)
         5. Service metadata (category/subcategory/service_offering/cmdb_ci)
       - Do NOT include flow_run_id, context_fingerprint, checkpoint names, or any other internal
         flow-execution detail in the description; those remain internal-only (Step 10 result payload).
    - Run native capability detection from Problem context
    - If native capability is `available`:
       - execute native ServiceNow->Jira creation path from PRB using mandatory issue payload
       - verify issue identifier (Jira key or equivalent) is returned
    - If native capability is `conditionally_available` or `unavailable`:
       - delegate to @Jira with strict handoff contract including full mandatory issue payload and required_fields list
       - fallback must fail closed if any mandatory description block is missing
       - do NOT create PTASK as a fallback artifact in this branch

8B) Affects Version/s and attachment propagation (non-blocking on the resolution gate):
    - After issue creation succeeds (native or delegated), set `Affects Version/s` on the created Jira
      issue to `current_release_version` via `update_issue(issue_key, fields={"versions": [{"name": current_release_version}]})`.
    - Fetch incident support files via `list_incident_attachments(incident_sys_id=...)` and re-upload each
      via `download_attachment(...)` + `add_attachment(issue_key, filename=..., content=...)`.
    - Record `affects_version_applied` (true/false) and `attachments_uploaded` (count + filenames) in
      diagnostics.
    - Failures in this step alone downgrade overall_status to `partial_success`; they do not block
      Step 8A parity verification or Step 9 resolution, since Affects Version and attachments are
      supportive metadata, not core parity fields.

8A) Mandatory post-create Jira parity verification:
    - Read back the created Jira issue fields.
    - Validate all of the following:
       - issue type is `Problem`
       - project equals routing decision
       - description contains Source Incident block and full canonical incident description
       - Source Incident number and Source Problem number in the description match the input contract exactly
         (structural reference match; do not rely on any embedded fingerprint/hash marker)
    - If parity verification fails:
       - set issue status=`failed_parity_validation`
       - do NOT resolve incident
       - return failure_reason with mismatch details and observed excerpt

9) Resolve incident only after end-to-end parity success:
    - Preconditions:
       - PRB stage status = success
       - Jira issue creation status = success
       - Jira parity verification status = success
    - Resolution note is a fixed compact template (not the general 3-part quality note), referencing the
      Jira issue created for follow-up:
       - `"Incident closed. Investigation ongoing under scope of <ISSUE_KEY> (<issue_url>)."`
    - If native ServiceNow->Jira succeeded:
       - Set incident Vendor Ticket = <ISSUE_KEY_OR_IDENTIFIER>
       - Set close_notes to the compact template above using the native issue key/URL
    - If Jira delegation succeeded:
       - Set incident Vendor Ticket = <ISSUE_KEY>
       - Set close_notes to the compact template above using the delegated issue key/URL
      - Set State = Resolved
      - Set Resolution code = Fixed
      - Resolve incident
      - If any precondition fails:
         - keep incident open
         - append actionable work note with failed step, reason_code, and retry guidance

10) Return strict result payload:
   - confirmation:
     - required (true/false)
     - user_response
   - execution:
      - flow_run_id
      - context_fingerprint
      - checkpoints: incident_fetched, incident_enriched, priority_updated, prb_ready, first_reported_by_task_backfilled, issue_created, parity_verified, affects_version_applied, attachments_propagated, incident_resolved
      - retry_recommended (true/false)
   - incident:
     - number, final_priority, state, vendor_ticket, status
   - problem:
      - number, created_mode, status, parity_verified, first_reported_by_task_verified
   - issue:
      - route_used (servicenow_native_jira | jira_agent_delegation)
      - number_or_key
      - required_issue_type
      - issue_type_verified
      - project
      - url
      - parity_verified
      - affects_version_applied
      - attachments_uploaded (count + filenames)
      - status
   - overall_status: success | partial_success | skipped | failed
   - failure_reason (if not success)
   - diagnostics:
      - warning_codes
      - mismatch_details

11) Failure guardrails:
   - Never resolve incident unless PRB and Jira parity verification both succeeded.
   - Never resolve incident if both issue routes fail (native ServiceNow + Jira delegation)
   - Never downgrade required issue type from `Problem` to `Task` silently for DDL/ODPT routes
   - Never accept issue creation when mandatory Incident Description block is missing from Jira description
   - Never paraphrase, summarize, or otherwise regenerate the incident description/short_description when
     building Problem or Jira fields; only whitespace-trim is permitted (see Step 2A exception for empty descriptions)
   - Never silently skip required fields; fail with explicit step and reason
   - Retries must search by incident_number and existing structural linkage (incident.problem_id,
     problem first_reported_by_task/origin_task, Jira `ServiceNow #` field) before creating new PRB/Jira
     artifacts; do not rely on any fingerprint/hash marker embedded in ticket text
   - If matching Jira issue already exists and passes parity, reuse it and skip new create
   - If matching Jira issue exists but parity fails, require explicit operator confirmation before recreate
   - If custom/target fields are unavailable, return partial_success or failed with precise diagnostics
   - Affects Version/s and attachment propagation failures (Step 8B) downgrade overall_status to
     `partial_success` only; they never block Step 9 incident resolution on their own
   - Never write internal flow-execution details (flow_run_id, context_fingerprint, flow name, checkpoint
     names, reason codes) into incident/problem `description`, `work_notes`, resolution `close_notes`, or
     Jira description/comments. These remain internal-only, reported solely in the Step 10 result payload.

Do not use Confluence or any external knowledge source for this operation, with the single narrow
exception of `ConfluenceClient.resolve_release_calendar()` in Step 8/8B for `Affects Version/s`
resolution. No other Confluence read/search capability is in scope for this flow.
```

Example:
`@ServiceNow, process incident INC0044438 with requested priority P3 and execute strict incident -> problem -> issue flow (native ServiceNow->Jira preferred, Jira-agent fallback).`
