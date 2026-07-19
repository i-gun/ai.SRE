---
name: "Incident Priority Raise"
description: "Raise the priority of a ServiceNow incident with strict validation and confirmation gates."
agent: "ServiceNow"
---

# ServiceNow Prompt: Strict Incident Priority Raise

Use this prompt with the ServiceNow agent to increase incident priority with strict scope, ownership, and approval confirmation gates.

```text
@ServiceNow, raise priority of incident <INC_NUMBER> to <TARGET_PRIORITY>.

STRICT EXECUTION POLICY (must follow in order):

1) Validate input:
   - INC_NUMBER is required (e.g., INC1234)
   - TARGET_PRIORITY must be one of: 1..5, P1..P5, or "priority 1".."priority 5"
   - Normalize TARGET_PRIORITY to P1..P5

2) Fetch incident details first:
   - number, sys_id, state, active, priority, impact, urgency
   - assignment_group (name/sys_id)
   - assigned_to (user identifier/display value)

3) Scope and ownership guardrails:
   - Check whether assignment_group is inside configured SERVICENOW_ASSIGNMENT_GROUPS scope.
   - Check whether assigned_to matches the currently configured ServiceNow user.
   - Distinguish between:
     - in-scope but assigned to another user
     - outside configured assignment-group scope

4) Mandatory confirmation gate:
   - If assignment_group is inside configured scope but assigned_to is not the configured user,
     ask for explicit approval and confirmation before any priority change.
   - If assignment_group is outside configured scope,
     STOP and return failed unless the platform policy explicitly permits cross-scope action.
   - Confirmation question must include:
     - incident number
     - current assignment_group
     - current assignee
     - currently configured ServiceNow user
     - whether the incident is merely not assigned to the current user or also outside configured scope
     - requested target priority
   - If explicit approval/confirmation is not given, do not update anything.
   - If confirmation is required but not explicitly given, STOP with status=skipped.

5) Ownership override behavior:
   - If the incident is in scope and assigned to another user, the current user may still raise priority after explicit approval/confirmation.
   - Do not reassign the incident automatically unless reassignment is explicitly requested.
   - Record that the priority raise was executed with ownership override approval.

5.1) Cross-scope policy behavior:
    - If assignment_group is outside configured scope and no explicit cross-scope policy permit is provided,
       STOP with status=failed.
    - Do not mutate priority, assignment, or notes in this branch.

6) Apply priority change only after passing gate:
   - Use priority matrix logic (update impact/urgency), do NOT patch priority directly.
   - Add work note:
     "[PRIORITY] Priority changed to <TARGET_PRIORITY> via matrix after scope/ownership validation and required approval checks."

7) Verify update:
   - Re-fetch incident and confirm resulting priority matches requested target.
   - If mismatch, report as failed and include returned priority.

8) Return strict result:
    - confirmation:
       - required (true/false)
       - user_response
    - incident:
       - number
       - previous_priority
       - requested_priority
       - resulting_priority
       - assignment_group
       - assignee
    - policy:
       - ownership_override_used
       - cross_scope_action_blocked
    - status: success | skipped | failed
    - failure_reason (if any)

Do not use Confluence or any external knowledge source for this operation.
```

Example:
`@ServiceNow, raise priority of incident INC1234 to P3.`
