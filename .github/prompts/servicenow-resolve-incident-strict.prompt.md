---
name: "ServiceNow Resolve Incident (Strict Input Gates)"
description: "Resolve a single ServiceNow incident using required gates (incident number, resolution code, resolution notes) and optional linkage fields when provided."
argument-hint: "Provide: incident number, resolution code, resolution notes. Optional: parent incident, problem, vendor ticket."
agent: "ServiceNow"
---

# ServiceNow Prompt: Resolve Single Incident With Strict Input Gates

Use this prompt with the ServiceNow agent to resolve one incident deterministically from caller-provided inputs.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@ServiceNow, resolve a single incident using strict input gates and provided closure details.

INPUT GATES (required):
- incident_number
- resolution_code_label
- resolution_notes

RESOLUTION CODE DROPDOWN POLICY (required):
- Use the incident Resolution code dropdown choice set (not free text).
- Select by label first, then persist with the platform-backed value.
- Preferred label for this flow: "No Action Taken".
- If label-to-value resolution cannot be verified, STOP and request a valid dropdown option from the caller.

OPTIONAL INPUTS (apply when provided):
- parent_incident
- problem_number
- vendor_ticket

STRICT EXECUTION POLICY (must follow in order):

1) Parse and normalize input:
   - Accept incident_number formats like INC1234.
   - Normalize resolution_code_label to platform dropdown value (resolution_code_value) while preserving caller intent.
   - Keep resolution_notes verbatim unless minor normalization is needed for safe write.

2) Required-gate enforcement before any mutation:
   - If incident_number is missing, ask for it and STOP.
   - If resolution_code_label is missing, ask for it and STOP.
   - If resolution_notes is missing, ask for it and STOP.
   - Do not update any record until all three required gates are present.

2.1) Dropdown selection gate before mutation:
   - Read available Resolution code choices from the incident form/context.
   - Resolve exact match for resolution_code_label (case-insensitive label match allowed).
   - Persist using the matched dropdown value, not arbitrary free text.
   - If requested label is "No Action Taken", select that exact dropdown label and its mapped value.
   - If no match exists, return failed with available options.

3) Fetch and validate target incident:
   - Read incident by incident_number.
   - Return failed if not found.
   - Return skipped if already resolved (treat as resolved: 6, 6 - Resolved, Resolved, or any display value containing Resolved).

4) Apply optional linkage/enrichment fields only when explicitly provided:
   - parent_incident -> Parent Incident field
   - problem_number -> Problem field
   - vendor_ticket -> Vendor Ticket field (prefer instance-authoritative field where applicable)
   - Never clear existing values when an optional field is omitted.

5) Apply closure fields:
   - Close notes = resolution_notes
   - Resolution code = resolved dropdown value for resolution_code_label
   - State = Resolved

6) Verify update:
   - Re-fetch incident and verify state reflects resolved.
   - Verify resolution_code label/value and close notes persisted.
   - Verify each optional field that was requested to be set.

7) Return strict result payload:
   - input:
     - incident_number
       - resolution_code_label
     - resolution_notes_present (true/false)
     - optional_fields_provided (parent_incident, problem_number, vendor_ticket)
   - incident:
     - number
     - state
       - resolution_code_label
       - resolution_code_value
     - close_notes_saved
     - parent_incident
     - problem_number
     - vendor_ticket
   - status: success | partial_success | skipped | failed
   - failure_reason (if any)

GUARDRAILS:
- Do not use Confluence or other external knowledge sources for this operation.
- Do not resolve when required gates are incomplete.
- Do not modify incidents other than the requested incident_number.
- Do not write free-text resolution codes; always use dropdown-backed value mapping.
```

Example invocation:
`@ServiceNow, resolve incident INC0054908 with resolution code label "No Action Taken" and resolution notes "Validated no customer impact; monitoring remains stable." Optional fields: parent incident INC0054000, problem PRB0040546, vendor ticket DDL-40001.`
