---
name: "Expiring Secrets Analysis (Read-Only)"
description: "Discover expiring Azure Key Vault secrets, chain-check Jira/ServiceNow reuse candidates, and persist a resolution_matrix artifact. Strictly read-only — never invokes any --execute write path."
agent: "Advisor"
---

# Expiring Secrets Analysis (Read-Only)

This is the **default** Secrets flow. It performs data retrieval, chain discovery, and
classification only, then persists the result as a `resolution_matrix` JSON artifact
for the companion [expiring-secrets-execute.prompt.md](./expiring-secrets-execute.prompt.md)
flow to consume. This flow never creates, updates, or resolves any ServiceNow or Jira
record and never invokes a script with `--execute`.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

Secret-name exclusion policy:
- Exclude secrets whose `objectName` contains any of these case-insensitive patterns:
  `subscription-key`, `spn-object-id`, or `spn-client-id`.
- Apply this filter immediately after Phase 1 collection, before suppression handling and
  before dispatching any Jira, ServiceNow, or Confluence lookup.
- Excluded secrets must not appear in `impact_matrix`, `resolution_matrix`, approval gates,
  or any final artifact. Report the excluded names and count as an exception.

```text
Execution model: 4 phases. Phases 1 and 3-4 are serial. Phase 2 dispatches @NewRelic, @ServiceNow,
@Jira, and @Confluence simultaneously — do not wait for one before starting the others.

Read credentials only from .env. Prefer promoted core scripts over ad-hoc queries.
This flow is read-only by construction: do not create, raise, or mutate any incidents,
problems, issues, or other records, and do not invoke any script with --execute.

Urgency tier classification:
- moderate:  7 ≤ daysUntilExpiry < 30  → "less than 30 days remaining"
- urgent:    0 < daysUntilExpiry < 7   → "less than 7 days remaining"
- critical:  daysUntilExpiry ≤ 0        → "expired"

━━━ PHASE 1 — Data Collection [serial] ━━━

@NewRelic
Use the promoted core script to collect expiring Key Vault secrets for Digital business unit:

  python scripts/newrelic/expiring_secrets_report.py --business-unit Digital --mode detail --json

The script queries account 1679802 (CTC Production) and returns rows faceted by secret name,
vault name, and event type. Classify by daysUntilExpiry into urgency tiers (moderate/urgent/critical).

Before processing the returned rows, exclude every secret whose `objectName` contains one of
the case-insensitive exclusion patterns above. Do not perform NEW_VERSION_CREATED checks or
any downstream lookup for excluded secrets.

Filter out secrets with recent SecretNewVersionCreated events:
- For each secret identified as (vaultName, objectName) with days_remaining status:
  Query: FROM AzureKeyVaultEvent
         WHERE objectName = '{objectName}'
         AND vaultName = '{vaultName}'
         AND eventType = 'Microsoft.KeyVault.SecretNewVersionCreated'
         SINCE 30 days ago
- If result count > 0: exclude this secret from further processing (already handled via new version)
- If result count = 0: include in impact_matrix

Output (impact_matrix) — required as input to Phase 2:
- evaluated_at
- business_unit = "Digital"
- account_id = 1679802
- grouped_secrets[]:
    urgency (moderate|urgent|critical), objectName, vaultName, daysUntilExpiry, eventType,
    expiryTime, lastModified, hasNewVersionEvent (boolean)
- total_secrets_at_risk, secrets_by_urgency{}

**STOP CONDITION — NO EXPIRING SECRETS:** If `total_secrets_at_risk = 0` or
`grouped_secrets[]` is empty after Phase 1, report that no expiring secrets were found
for the requested business unit and window. Stop the flow immediately. Do not dispatch
@Jira, @ServiceNow, or @Confluence; do not run incident, problem, issue, chain, or
release-calendar lookups; do not persist a resolution matrix; and do not perform any
writes. The final report must state that no further lookups or release version
retrieval were necessary.

━━━ PHASE 2 — Chain Discovery and Incident Lookup [parallel] ━━━

Dispatch the following three agent tasks at the same time using the impact_matrix from Phase 1.
Do not wait for one to complete before starting the others.

── @Jira (runs in parallel with @ServiceNow) ──

For each (vaultName, objectName, urgency) in impact_matrix, run the promoted chain-check script:

  python scripts/jira/secrets_task_manager.py chain-check \
    --vault "{vaultName}" --secret "{objectName}" --urgency {urgency} \
    --search-days 30 --json

The chain-check applies `created >= -30d` to every DDL and BET tier. Only Jira
issues created within the last 30 days are eligible for reuse; an old issue that
was recently updated must not be selected for this recent-expiration flow.

The script executes all 5 JQL tiers internally and returns chain_status:
  complete  — DDL found with AzureKV label and linked BET
  partial   — DDL found without the required label or BET, or a recent BET exists without its corresponding DDL
  no_chain  — no DDL or BET found on any tier

Return per tuple:
- vaultName, objectName, urgency
- chain_status: complete | partial | no_chain
- best_ddl_key, ddl_has_azurekv_label, ddl_status
- best_bet_key, bet_status
- gaps[]

── @ServiceNow (runs in parallel with @Jira) ──

For each (vaultName, objectName, urgency) in impact_matrix, search for existing Incidents and Problems.
This is a search/preview step only — do not call any script in --execute mode here.

Incident search logic:
- Search window: 30 days back for every urgency tier
- Filter by incident creation time (`sys_created_on`); records older than 30 days
  are not eligible even when they are still open or were recently updated
- Query by exact short_description: "[Secret {urgency}] {objectName} in {vaultName}"
- Fallback: search by vaultName alone
- Fallback: search by objectName alone
- Scope to designated SN assignment groups

Problem search logic:
- Same 30-day creation window and fallback logic as incidents
- Filter by problem creation time (`sys_created_on`); records older than 30 days
  are not eligible even when they are still open or were recently updated
- Scope to designated assignment groups
- When an incident is found, inspect its linked `problem_id` first and apply the
  same 30-day creation filter; never reuse an older linked problem
- Use vault/object-name fallback matches only when they are also within the same
  30-day creation window

Return per tuple:
- vaultName, objectName, urgency
- existing_incident: number, short_description, state, sys_id  (null if not found)
- existing_problem: number, short_description, state, sys_id  (null if not found)
- sn_status: reuse | create_needed | auth_error | not_searched

Sample incident short descriptions (authoritative format):
  "[Secret Moderate] corp-prod-095-dms-spn-client-secret in digital-prd-mer-cc-01-k"
  "[Secret Urgent] dam-aws-s3-product-key in digital-prd-asm-cc-01-kv"
  "[Secret Expired] rotation-key-prod in digital-prd-kv-01"

Use the promoted create_secrets_incident_problem.py script (dry-run mode only in this flow;
never pass --execute) to validate and preview incident/problem payloads:

  python scripts/servicenow/create_secrets_incident_problem.py \
    --vault "{vaultName}" --secret "{objectName}" --urgency {urgency} \
    --days-remaining {daysUntilExpiry} --event-type {eventType} --json

  ── @Confluence (runs in parallel with @Jira and @ServiceNow) ──

  Resolve the authoritative Digital Release Calendar page `80217385` through the promoted
  Confluence release-calendar contract. Use only `Production Release date` and `Release Name`:
  - `current_release_version`: latest production deployment date on or before the analysis date
  - `future_release_version`: nearest production deployment date after the analysis date

  Return `current_release_version`, `future_release_version`, `source_page_id`,
  `source_page_version`, `current_production_date`, and `future_production_date` once per run.

━━━ PHASE 3 — Synthesis and Classification [serial, after both Phase 2 tasks complete] ━━━

Merge the Jira chain_results and ServiceNow sn_results per (vaultName, objectName, urgency).
Classify each tuple into one of:

  report_only
    chain_status = complete AND sn_status = reuse
    Action: no writes needed; document existing artifacts and their status.

  repair_needed
    chain_status = partial (DDL exists but gaps present)
    Action: describe what repairs would be made (add label, link BET) — decision only.

  needs_full_creation
    chain_status = no_chain
    Action: describe full artifact set that would be created (INC → PRB → DDL → BET) — decision only.

Output — resolution_matrix rows, one per (vaultName, objectName, urgency):
- entity_key: { vaultName, objectName, urgency }
- classification: report_only | repair_needed | needs_full_creation
- existing: { ddl_key, bet_key, incident_number, problem_number }
- gaps[]
- carry forward daysUntilExpiry, eventType, expiryTime, lastModified, hasNewVersionEvent,
  current_release_version, future_release_version, and release-calendar evidence
  needed by Phase 4 of the execute flow
- approval_gate_flags: append one entry per row when any of these hold:
    - existing incident > 7 days old (possible stale reuse)
    - existing problem not linked to incident (linkage gap)
    - multiple incident/problem candidates with conflicting states
    - secret with both NEW_VERSION_CREATED event AND expiration notification

━━━ PHASE 4 — Persist Artifact [serial] ━━━

1. Build the full resolution_matrix JSON object with fields:
   schema_version = "1.0", domain = "secrets", generated_at, generated_by = "expiring-secrets-analysis.prompt.md",
   window = { start: evaluated_at, end: evaluated_at }, source_data_fingerprint, rows[] (from Phase 3),
   approval_gate_flags[]
2. Write it to `artifacts/resolution_matrix_secrets_{UTC timestamp}.json` using the shared helper:

   python scripts/common/resolution_matrix.py validate --path artifacts/resolution_matrix_secrets_{timestamp}.json --domain secrets

   (Use the create_file/write tool to persist the JSON, then run the validate command above to confirm
   schema correctness before reporting completion.)
3. Report the artifact path in the final report. Do NOT invoke the execute flow automatically —
   the operator must separately run [expiring-secrets-execute.prompt.md](./expiring-secrets-execute.prompt.md).

━━━ FINAL REPORT ━━━

Sections:
1. Scope (evaluation time, account, business unit, urgency distribution)
2. Grouped Impact Matrix (from Phase 1) — secrets by urgency tier
3. Resolution Matrix (from Phase 3) — one row per vaultName+objectName+urgency tuple
4. Persisted Artifact (path from Phase 4)
5. Exceptions (auth errors, script failures, suppressed secrets with NEW_VERSION_CREATED)
6. Approval Gate Flags (carried into the resolution_matrix, to be re-surfaced by the execute flow)
7. Next step reminder: "To raise/repair tickets for these findings, run expiring-secrets-execute.prompt.md
   with this artifact path. It will re-validate freshness and require explicit confirmation before any write."

Success criteria:
- Every discovered non-excluded (vaultName, objectName) with expiration represented in resolution_matrix
- Every secret matching the name exclusion policy reported as excluded and absent from all downstream artifacts
- Every tuple has exactly one resolved classification
- Secrets with recent NEW_VERSION_CREATED events excluded from output (suppressed)
- resolution_matrix artifact passes `resolution_matrix.py validate`
- No script was invoked with --execute anywhere in this flow
```
