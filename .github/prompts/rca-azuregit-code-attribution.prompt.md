---
name: "RCA AzureGit Code Attribution"
description: "Execute a scoped, evidence-or-abstain AzureGit code attribution analysis for a named service and set of error signatures. Returns structured attribution candidates with confidence scores or an explicit no-evidence outcome."
argument-hint: "Provide: service name, error signatures, and optionally endpoint paths and dependency names."
agent: "RCA"
---

# RCA AzureGit Code Attribution

Use this prompt to perform targeted code attribution within the configured AzureGit scope. The agent must produce evidence-backed candidates or explicitly abstain — speculation is not permitted.

Reuse-first policy:
- Prefer existing promoted tools and shared functions before creating new automation.
- If new automation is unavoidable, keep it promotion-ready and call out required agent/prompt/skill/doc updates.
- Avoid duplicate tooling and consolidate overlap into the maintained artifact.

```text
@RCA, execute AzureGit code attribution via rca-azuregit-attribution.

Service: <SERVICE_NAME>

Error signatures (from log forensics):
<List each signature on a separate line — use normalized templates, not raw log lines:>
- <SIGNATURE_1>
- <SIGNATURE_2>
- <SIGNATURE_3>

Endpoint paths (from error evidence, optional):
- <ENDPOINT_PATH_1>
- <ENDPOINT_PATH_2>

Dependency names (from downstream error analysis, optional):
- <DEPENDENCY_NAME_1>
- <DEPENDENCY_NAME_2>

Project scope: <use configured AZURE_PROJECT — do NOT expand beyond configured scope>

Execute the following steps:

1. Configuration gate:
   - Verify AZURE_ORG, AZURE_PROJECT, and AZURE_PAT are present in .env
   - If any are missing, return:
     status: configuration_gap
     reason: <specific missing variable>
     next_step: populate missing .env variable and retry
   - Stop here if configuration gate fails

2. Repository discovery:
   - Load artifacts/azuregit_repo_map.json
   - If absent or older than 24 hours, refresh via azuregit-repository-operations
   - Filter repositories by name proximity to "<SERVICE_NAME>"
   - Return candidate list with match_reason

3. Code search — error signatures:
   - For each error signature, search all candidate repositories
   - Bound: max 200 files per repo, max 500 results per query
   - Return per match: project, repository, path, line_number, excerpt (≤300 chars)

4. Endpoint path tracing (if endpoint paths provided):
   - Search routing and configuration files for each endpoint path string
   - Identify handler/controller entry points

5. Dependency client search (if dependency names provided):
   - Search for client configuration, base URL references, and retry/timeout settings
   - Return file paths and configuration excerpts

6. Attribution assembly:
   - Score each candidate using the confidence matrix in rca-azuregit-attribution
   - Return attribution candidates with full output schema:
     { project, repository, path, line, excerpt, confidence, evidence_type, matched_signatures, attribution_notes }

7. No-match handling:
   - If zero evidence found after steps 3–5, return:
     { status: "no_evidence", reason: "<specific reason>", searched_projects: [...], searched_queries: [...], next_step: "<action>" }

Output requirements:
- Never infer line numbers without direct file-content evidence
- Never fabricate project, repository, file path, or symbol names
- Distinguish explicitly: "observed evidence" / "inferred hypothesis" / "unknown/unverified"
- Include query_parameters block with: organization, project scope, queries executed, result limits
- If attribution is partial (mapping incomplete), state "Repository mapping incomplete; attribution partial"
```

## Execution Requirements

- All operations are read-only — no write, update, or delete operations
- Do not access projects outside configured `AZURE_PROJECT` scope
- Do not skip the configuration gate
- Return `query_parameters` for full reproducibility
- Result is either a populated attribution candidates list OR an explicit no-match / configuration-gap report — never silence
