# Reusable Prompt: Agent Handoff Result Schema

Use this reusable schema prompt to keep ServiceNow and Jira responses machine-readable and consistent.

```text
Return response as strict JSON with these keys:
{
  "status": "success | partial_success | skipped | failed",
  "step": "string",
  "entity": "incident | problem | issue | orchestration",
  "id": "string",
  "details": {
    "before": {},
    "after": {},
    "applied": [],
    "missing": [],
    "issue_type_requested": "string|null",
    "issue_type_created": "string|null",
    "issue_type_verified": "boolean|null"
  },
  "failure_reason": "string|null",
  "next_action": "string|null"
}

Rules:
- Always include status.
- Never omit failure_reason on non-success states.
- Use partial_success if primary action succeeds but validation/backpropagation is incomplete.
- Use skipped only for explicit confirmation-gate stops.
```
