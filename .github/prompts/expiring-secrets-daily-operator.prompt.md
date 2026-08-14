---
name: "Daily Expiring Secrets Orchestrator (Deprecated)"
description: "DEPRECATED: superseded by expiring-secrets-analysis.prompt.md + expiring-secrets-execute.prompt.md. This wrapper only runs the read-only analysis half by default and never auto-chains into execute."
agent: "Advisor"
---

# Daily Expiring Secrets Orchestrator (Deprecated)

> **Deprecated.** This monolithic prompt is retained for backward compatibility only.
> Use the decoupled pair instead:
> - [expiring-secrets-analysis.prompt.md](./expiring-secrets-analysis.prompt.md) — default,
>   read-only data retrieval/classification, persists a `resolution_matrix` artifact.
> - [expiring-secrets-execute.prompt.md](./expiring-secrets-execute.prompt.md) — complementary
>   flow that loads that artifact, re-validates freshness, re-checks live state, and requires
>   explicit operator confirmation before raising/repairing any Incident/Problem/DDL/BET.
>
> Running this wrapper executes **only** the analysis flow described in
> [expiring-secrets-analysis.prompt.md](./expiring-secrets-analysis.prompt.md) end to end
> (Phases 1-4 there, including persisting the resolution_matrix artifact) and then **stops**.
> It does not run the execute flow automatically under any circumstance — the operator must
> invoke [expiring-secrets-execute.prompt.md](./expiring-secrets-execute.prompt.md) separately
> and confirm before any write occurs. This preserves today's default dry-run behavior exactly.

Use this prompt to run the daily expiring secrets flow with strict reuse-before-create behavior.

Dry-run mode:
- Read-only only; do not create, raise, update, or resolve incidents, problems, issues, or other artifacts.
- Report findings and reuse candidates only.
- Any create/repair branch must be described as hypothetical and must not be executed.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
Execution model: 4 phases. Phases 1 and 3-4 are serial. Phase 2 dispatches @NewRelic, @ServiceNow,
and @Jira simultaneously — do not wait for one before starting the others.

Read credentials only from .env. Prefer promoted core scripts over ad-hoc queries.
This run is dry-run/read-only: do not create, raise, or mutate any incidents, problems, issues,
or other records.

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

━━━ PHASE 2 — Chain Discovery and Incident Lookup [parallel] ━━━

Dispatch the following three agent tasks at the same time using the impact_matrix from Phase 1.
Do not wait for one to complete before starting the others.

── @Jira (runs in parallel with @ServiceNow) ──

For each (vaultName, objectName, urgency) in impact_matrix, run the promoted chain-check script:

  python scripts/jira/secrets_task_manager.py chain-check \
    --vault "{vaultName}" --secret "{objectName}" --urgency {urgency} --json

The script executes all 5 JQL tiers internally and returns chain_status:
  complete  — DDL found with correct parent (DDL-28477), Secrets label, and linked BET
  partial   — DDL found but one or more of: parent, label, BET link is missing
  no_chain  — no DDL or BET found on any tier

Return per tuple:
- vaultName, objectName, urgency
- chain_status: complete | partial | no_chain
- best_ddl_key, ddl_parent, ddl_has_secrets_label, ddl_status
- best_bet_key, bet_status
- gaps[]

── @ServiceNow (runs in parallel with @Jira) ──

For each (vaultName, objectName, urgency) in impact_matrix, search for existing Incidents and Problems.

Incident search logic:
- Search window: 30 days back for moderate/urgent; 7 days back for critical
- Query by exact short_description: "[Secret {urgency}] {objectName} in {vaultName}"
- Fallback: search by vaultName alone
- Fallback: search by objectName alone
- Scope to designated SN assignment groups

Problem search logic:
- Same search windows and fallback logic as incidents
- Scope to designated assignment groups
- Check if linked to the incident (if found)

Return per tuple:
- vaultName, objectName, urgency
- existing_incident: number, short_description, state, sys_id  (null if not found)
- existing_problem: number, short_description, state, sys_id  (null if not found)
- sn_status: reuse | create_needed | auth_error | not_searched

Sample incident short descriptions (authoritative format):
  "[Secret Moderate] corp-prod-095-dms-spn-client-secret in digital-prd-mer-cc-01-k"
  "[Secret Urgent] dam-aws-s3-product-key in digital-prd-asm-cc-01-kv"
  "[Secret Expired] rotation-key-prod in digital-prd-kv-01"

Use the promoted create_secrets_incident_problem.py script (dry-run mode) to validate
and preview incident/problem payloads:

  python scripts/servicenow/create_secrets_incident_problem.py \
    --vault "{vaultName}" --secret "{objectName}" --urgency {urgency} \
    --days-remaining {daysUntilExpiry} --event-type {eventType} --json

━━━ PHASE 3 — Synthesis [serial, after both Phase 2 tasks complete] ━━━

Merge the Jira chain_results and ServiceNow sn_results per (vaultName, objectName, urgency).
Classify each tuple into one of:

  report_only
    chain_status = complete AND sn_status = reuse
    Action: no writes needed; document existing artifacts and their status.

  repair_needed
    chain_status = partial (DDL exists but gaps present)
    Action (dry-run): describe what repairs would be made (add label, fix parent, link BET).
    ServiceNow: reuse existing INC/PRB if found; otherwise flag for creation.

  needs_full_creation
    chain_status = no_chain
    Action (dry-run): describe full artifact set to create (INC → PRB → DDL → BET).

Output — resolution_matrix[]:
- vaultName, objectName, urgency, classification, existing_ddl_key, existing_bet_key,
  existing_inc_number, existing_prb_number, gaps[], sn_reuse_status

━━━ PHASE 4 — Creation Specification [serial, dry-run only] ━━━

For each tuple classified as needs_full_creation or repair_needed, describe hypothetical
actions in the order below. Do NOT execute any writes.

ServiceNow (if no existing INC/PRB):
  Incident:
    short_description = [Secret {urgency}] {objectName} in {vaultName}
    description       = See template below
    category          = Infrastructure
    subcategory       = Cloud Services
    impact            = 2 (Medium)
    urgency           = (derived from urgency tier: critical→1, urgent→2, moderate→3)
    assignment_group  = <to be determined from CMDB lookup or designated group>

  Problem (linked to Incident):
    short_description = [Secret {urgency}] {objectName} in {vaultName}
    description       = Same as Incident

Incident/Problem Description Template:
  ────────────────────────────────────────────
  Azure Key Vault Secret Expiration Alert

  Secret:         {objectName}
  Key Vault:      {vaultName}
  Days Remaining: {daysUntilExpiry}
  Urgency:        {urgency.UPPER()}
  Event Type:     {eventType}
  Expiry Time:    {expiryTime}
  Last Modified:  {lastModified}

  Status:
  - Secret NEW_VERSION_CREATED since notification? {hasNewVersionEvent}
  - Incidents raised in last {searchWindow} days? {existing_incident_count}
  - Problems linked to incidents? {existing_problem_count}

  Recommended Actions:
  1. Verify secret rotation schedule with owning team
  2. Coordinate renewal with dependent services
  3. Validate new version creation before expiration
  4. Update automation if using hardcoded expiration dates
  5. Document remediation in related Jira issues

  Next Steps:
  - Assign to Key Vault Operations team for coordinate rotation
  - Link related DDL and BET issues once created
  ────────────────────────────────────────────

Jira DDL:
  project = DDL, parent = DDL-28477
  summary = short_description from ServiceNow context for the tuple
  labels  = [Secrets, {urgency}, ODP, SRE, key-vault-operations]
  banner (selectable) = CanadianTire (required)
  components (selectable) = [Key Vault Operations]
  team (selectable) = Site Reliability Engineering
  serviceNowPriority (selectable) = P3
  serviceNowNumber = [INC, PRB] if exists
  rootCause (selectable) = Configuration
  description = Same as ServiceNow Incident description (exact match)
  Do NOT include Evidence section or explicit metadata lines

Jira BET:
  project = BET
  summary = [Secret {urgency}] {objectName} in {vaultName}
  description = Same as DDL
  assignee = DaaS team (selectable field)
  labels = [Secrets, {urgency}, DaaS, ODP]
  cross-link: DDL ↔ BET (relates-to)

For repair_needed tuples, describe only the delta:
  - "add label 'Secrets' to DDL-XXXXX"
  - "update parent of DDL-XXXXX to DDL-28477"
  - "create BET-XXXXX and link to DDL-XXXXX"

Approval Gate:
If any of these conditions hold, flag for manual review before execute:
  1. Existing incident > 7 days old (possible stale reuse)
  2. Existing problem not linked to incident (linkage gap)
  3. Multiple incident/problem candidates with conflicting states
  4. Secret with both NEW_VERSION_CREATED event AND expiration notification

━━━ FINAL REPORT ━━━

Sections:
1. Scope (evaluation time, account, business unit, urgency distribution)
2. Grouped Impact Matrix (from Phase 1) — secrets by urgency tier
3. Resolution Matrix (from Phase 3) — one row per vaultName+objectName+urgency tuple
4. Hypothetical Creation Actions (from Phase 4, if any)
5. Repair Actions (repair_needed tuples only)
6. Exceptions (auth errors, script failures, suppressed secrets with NEW_VERSION_CREATED)
7. Approval Gate Decisions (manual checks required before execute)

Success criteria:
- Every discovered (vaultName, objectName) with expiration represented in resolution_matrix
- Every tuple has exactly one resolved path (report_only | repair_needed | needs_full_creation)
- No duplicate artifact creation when reusable ones exist
- Every hypothetical DDL has parent DDL-28477
- Every hypothetical DDL has label "Secrets"
- Every artifact uses the exact summary template: [Secret {urgency}] {objectName} in {vaultName}
- Jira DDL/BET description must exactly match ServiceNow Incident description for the same tuple
- Every completed chain has valid DDL↔BET cross-link
- Secrets with recent NEW_VERSION_CREATED events excluded from output (suppressed)
```
