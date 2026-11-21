---
name: agent-handoff-result-schema
description: "Use this reusable handoff schema to keep ServiceNow and Jira responses machine-readable and consistent."
disable-model-invocation: true
---
# Reusable Agent Handoff Result Schema

Use this shared output contract within `@ServiceNow` and `@Jira` handoffs. It standardizes
responses only; it is not an agent, does not perform operations, and does not authorize writes.

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
Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```
