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
Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```
