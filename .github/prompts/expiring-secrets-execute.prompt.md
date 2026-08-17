---
name: "Expiring Secrets Execute (Requires Confirmation)"
description: "Load a resolution_matrix artifact from expiring-secrets-analysis.prompt.md, re-validate freshness, re-check live state, and — only after explicit operator confirmation — raise/repair ServiceNow and Jira artifacts."
agent: "Advisor"
---

# Expiring Secrets Execute (Requires Confirmation)

This is the **complementary** Secrets flow. It never runs on its own schedule and never
runs automatically after the analysis flow — the operator must explicitly invoke it
and supply (or accept the auto-discovered latest) `resolution_matrix` artifact produced by
[expiring-secrets-analysis.prompt.md](./expiring-secrets-analysis.prompt.md).

This flow performs writes and therefore defaults to a hard stop before any create/repair
action until the operator explicitly confirms.

```text
Inputs:
- --resolution-matrix-path (optional). If omitted, use the latest artifact for domain=secrets:
    python scripts/common/resolution_matrix.py find-latest --domain secrets
- --max-age-hours: use tier-appropriate default per row urgency at Step 2 —
    critical/urgent rows: 8 hours; moderate rows: 24 hours.
  If the artifact contains a mix of urgencies, apply the strictest applicable threshold
  (8 hours) to the whole artifact unless rows are individually re-validated.

━━━ STEP 1 — Load and Validate Artifact [serial] ━━━

  python scripts/common/resolution_matrix.py validate --path {resolution_matrix_path} --domain secrets

Hard fail (stop, do not proceed) if:
- schema_version mismatch
- domain != "secrets"
- file not found / invalid JSON

━━━ STEP 2 — Freshness / Integrity Check [serial] ━━━

  python scripts/common/resolution_matrix.py check-staleness --path {resolution_matrix_path} \
    --domain secrets --max-age-hours {max_age_hours}

If is_stale = true:
- Report the reasons (age exceeded, or row content no longer matches source_data_fingerprint —
  possible tampering/corruption).
- STOP. Do not proceed to Step 3. Instruct operator to re-run expiring-secrets-analysis.prompt.md.

━━━ STEP 3 — Lightweight Live Re-Check [serial, only rows classified repair_needed or needs_full_creation] ━━━

For each such row (vaultName, objectName, urgency), re-run only the cheap read-only lookups
(not the full NewRelic collection) to detect drift since analysis time:

@Jira:
  python scripts/jira/secrets_task_manager.py chain-check \
    --vault "{vaultName}" --secret "{objectName}" --urgency {urgency} --json

@ServiceNow: re-search Incidents/Problems by the exact short_description template
  [Secret {urgency}] {objectName} in {vaultName}
  (same search logic and windows as Phase 2 of the analysis flow, scoped to designated assignment groups)

Also re-check suppression: re-query AzureKeyVaultEvent for a SecretNewVersionCreated event
in the last 30 days for (vaultName, objectName). If one now exists that did not exist at
analysis time, mark the row "suppressed_at_execute_time" and skip it from writes.

Diff against the row's stored `existing.*` fields:
- If a DDL/BET/INC/PRB now exists that did not exist at analysis time -> reclassify this row live
  (e.g. needs_full_creation -> report_only or repair_needed) and mark it "reclassified_at_execute_time".
- If nothing changed -> row proceeds with its original classification.

Rows marked "reclassified_at_execute_time" to report_only, or "suppressed_at_execute_time",
are skipped from writes and reported, not executed against stale assumptions.

━━━ STEP 4 — Approval Gate [serial, mandatory, blocks Step 5] ━━━

Present to the operator, and require an explicit affirmative response before continuing:
- Artifact path, generated_at, age_hours
- Row count by classification (report_only / repair_needed / needs_full_creation), by urgency tier
- Any approval_gate_flags carried from the analysis artifact (stale incident >7d, linkage gaps,
  conflicting candidates, dual NEW_VERSION_CREATED + expiration notification)
- Any rows reclassified or suppressed in Step 3

Do NOT proceed to Step 5 without an explicit "yes, proceed" confirmation for this run.
An operator confirmation from a previous run does not carry over.

━━━ STEP 5 — Execute Writes [serial, only after Step 4 confirmation] ━━━

For each row still classified repair_needed or needs_full_creation after Step 3:

ServiceNow (reuse-before-create, using the promoted script in --execute mode):

  python scripts/servicenow/create_secrets_incident_problem.py \
    --vault "{vaultName}" --secret "{objectName}" --urgency {urgency} \
    --days-remaining {daysUntilExpiry} --event-type {eventType} --execute

  Notes:
  - The script performs its own reuse search; if it exposes an approval-gate flag similar to
    the CVE script, treat a required-but-unconfirmed gate as a secondary hard stop requiring a
    fresh manual check before retrying — do not blindly pass any confirmation flag.
  - assign the incident to the currently configured ServiceNow user
  - set or update Assignment group to the currently configured/default designated group
  - category = Application, subcategory = E-Commerce
  - service_offering = cmdb_ci when a configuration item is supplied; otherwise
    set both to `canadiantire.ca`
  - set Incident priority to P3 through the existing impact/urgency matrix
    (impact=2, urgency=2)
  - set Problem Origin Task to the Incident number
  - Use the standard description template (Azure Key Vault Secret Expiration Alert block)
    from the analysis flow's carried-forward row fields.

Jira DDL/BET (only for rows needing DDL/BET creation or repair):
  DDL: project = DDL, issue type = Problem,
    labels = [L2toL3, ODP, SRE, AzureKV], banner = [CanadianTire, SportChek],
    components = [Azure], team = Site Reliability Engineering,
    rootCause = Lifecycle Management, priority = Major,
    ServiceNow Priority = P3 (selectable option),
    description must exactly match the ServiceNow Incident description for the same tuple
  On successful DDL creation, clone its summary and description into BET as a Task,
  assign team [Daas] Operational Squad, add label DaaS, and cross-link DDL <-> BET
  (relates-to).

Use the promoted Secrets handoff for this operation:

  python scripts/jira/create_secrets_ddl_bet.py \
    --incident-number "{incident_number}" --problem-number "{problem_number}" \
    --summary "[Secret {urgency}] {objectName} in {vaultName}" \
    --description "{service_now_incident_description}" --idempotency-days 30

The handoff is idempotent, creates the DDL `Problem` first, applies the required
fields, resolves current/upcoming versions from the Confluence Digital Release
Calendar, writes Affected version and Fix Versions to both DDL and BET, writes
the resulting DDL key to the ServiceNow Incident Vendor Ticket field, then creates
the BET `Task` clone and links the two Jira issues. After the
chain is verified, resolve the Incident with State = Resolved, Resolution code =
Fixed, and Resolution notes: `Secret rotation task has been assigned to Operational
Squad. {BET_ticket_number} is for tracking.`

  For repair_needed rows, apply only the delta (add missing label, link BET,
  create BET and link to existing DDL) — do not recreate existing records.

Record every created/reused ID immediately in the execution report as each write completes
(do not wait until the end of the batch), so a retry after a partial failure does not
recreate already-created records.

━━━ FINAL REPORT ━━━

Sections:
1. Artifact used (path, generated_at, age_hours at execute time)
2. Freshness/Integrity result (Step 2)
3. Live re-check deltas, reclassifications, and suppressions (Step 3)
4. Approval Gate transcript (Step 4) — confirmation received, flags shown
5. Execution Results (Step 5) — per tuple: action taken (reused / created / repaired / skipped),
   resulting INC/PRB/DDL/BET keys
6. Exceptions (auth errors, script failures, secondary approval gates triggered)

Success criteria:
- No writes occurred before explicit Step 4 confirmation
- No row executed with age past its tier's --max-age-hours threshold
- Every write result (created or reused ID) captured immediately, not only at report time
- Rows reclassified or suppressed during Step 3 were not executed against their stale Step-1 classification
```
