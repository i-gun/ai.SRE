# Prompt Pack: ServiceNow + Jira Strict Workflow

This folder contains reusable prompts for strict incident to problem to Jira orchestration.

Files:
- [.github/prompts/servicenow-incident-to-prb-jira-strict.prompt.md](.github/prompts/servicenow-incident-to-prb-jira-strict.prompt.md)
  Primary orchestrator prompt for ServiceNow with confirmation gate, always-fresh PRB behavior, ServiceNow-first issue creation (PTASK), Jira fallback, and strict completion reporting.
- [.github/prompts/jira-create-issue-from-servicenow-handoff.prompt.md](.github/prompts/jira-create-issue-from-servicenow-handoff.prompt.md)
  Companion Jira prompt for routed issue creation with field-resolution guardrails and strict verification output.
- [.github/prompts/servicenow-finalize-incident-from-jira-result.prompt.md](.github/prompts/servicenow-finalize-incident-from-jira-result.prompt.md)
  Companion ServiceNow prompt for vendor-ticket backpropagation and controlled incident resolution from PTASK or Jira results.
- [.github/prompts/agent-handoff-result-schema.prompt.md](.github/prompts/agent-handoff-result-schema.prompt.md)
  Reusable response schema for consistent machine-readable handoffs.

# Use this prompt pack from .github/prompts in this sequence.

1. Primary orchestration prompt:
@ServiceNow, process incident INC0044438 with requested priority P3 and execute strict incident -> problem -> issue flow (ServiceNow-first, Jira fallback).

2. Jira companion prompt (fallback only if ServiceNow PTASK creation fails):
@Jira, create issue from ServiceNow handoff using strict field mapping and return a structured result.

3. ServiceNow finalization prompt (after PTASK or Jira returns issue identifier):
@ServiceNow, finalize incident INC0044438 using issue result and close workflow strictly.

4. Optional reusable schema prompt (for consistent agent outputs):
Use [.github/prompts/agent-handoff-result-schema.prompt.md](.github/prompts/agent-handoff-result-schema.prompt.md) as the required output contract for both agents, especially for ServiceNow -> Jira and Jira -> ServiceNow handoffs.

# Troubleshooting

1. Flow stopped with status=skipped before updates:
- Cause: confirmation gate was triggered and explicit confirmation was not provided.
- Action: rerun and provide explicit confirmation including incident number and requested priority.

2. Existing PRB was reused when a fresh one was expected:
- Cause: old flow used idempotent reuse logic.
- Action: enforce always-fresh PRB creation from incident; do not reuse incident.problem_id and do not search by origin_task.

3. Jira issue created but required fields were not applied:
- Cause: custom fields (Banner, Team, ServiceNow Priority, ServiceNow #) not resolved by field name to actual field IDs.
- Action: in Jira step, resolve field IDs first and fail fast if a required field is unavailable.

4. Jira step failed on description format:
- Cause: Jira Cloud API expected Atlassian Document Format (ADF) instead of plain text.
- Action: send description in valid ADF payload and retry issue creation.

5. Incident was not resolved after issue creation:
- Cause: finalization step was not executed or failed during vendor-ticket backpropagation.
- Action: run [.github/prompts/servicenow-finalize-incident-from-jira-result.prompt.md](.github/prompts/servicenow-finalize-incident-from-jira-result.prompt.md) with issue identifier/result and verify state, resolution code, and vendor ticket.

6. Wrong Jira project routing:
- Cause: routing used requested priority instead of final incident priority after matrix update.
- Action: always re-fetch incident after priority logic and route by final priority (P3 -> DDL, P4/P5 -> ODPT).

7. Partial success returned:
- Cause: core entity creation succeeded but one or more backpropagation or verification steps failed.
- Action: inspect failure_reason and next_action from the response schema, remediate only failed step, then re-run that step (not full flow).