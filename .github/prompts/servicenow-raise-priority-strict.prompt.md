# ServiceNow Prompt: Strict Incident Priority Raise

Use this prompt with the ServiceNow agent to increase incident priority with strict scope and ownership confirmation gates.

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

4) Mandatory confirmation gate:
   - If assignment_group is outside configured scope OR assigned_to is not the configured user,
     STOP and ask for explicit confirmation before any priority change.
   - Confirmation question must include:
     - incident number
     - current assignment_group
     - current assignee
     - requested target priority
   - If confirmation is not explicitly given, do not update anything.

5) Apply priority change only after passing gate:
   - Use priority matrix logic (update impact/urgency), do NOT patch priority directly.
   - Add work note:
     "[PRIORITY] Priority changed to <TARGET_PRIORITY> via matrix after scope/ownership validation."

6) Verify update:
   - Re-fetch incident and confirm resulting priority matches requested target.
   - If mismatch, report as failed and include returned priority.

7) Return strict result:
   - Incident number, previous priority, requested priority, resulting priority
   - assignment_group, assignee
   - whether confirmation was required and user response
   - status: success / skipped / failed
   - failure reason (if any)

Do not use Confluence or any external knowledge source for this operation.
```

Example:
`@ServiceNow, raise priority of incident INC1234 to P3.`
