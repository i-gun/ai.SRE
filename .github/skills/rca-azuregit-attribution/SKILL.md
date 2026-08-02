---
name: 'rca-azuregit-attribution'
description: 'AzureGit source attribution and code-path analysis skill for scoped repository discovery, service-name-driven code search, call-path tracing, fault location hypothesis generation, and explicit no-match reporting with confidence scoring.'
keywords: ['rca', 'azuregit', 'code-attribution', 'source-analysis', 'repository-discovery', 'fault-location', 'confidence']
---

# RCA AzureGit Attribution Skill

This skill drives the **source code attribution stream** for RCA workflows. It performs scoped repository discovery, targeted code search, call-path tracing, and produces either file/line-level fault location candidates with confidence scores, or an explicit no-evidence outcome — never speculation.

## Credential Requirements

Delegates to `azuregit-authentication` and `azuregit-repository-operations` skills.
Required variables in `.env`:
- `AZURE_ORG`
- `AZURE_PROJECT` (comma-separated scoped project list)
- `AZURE_PAT` (read-only scopes only)

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `service_name` | string | yes | Target service name (used for repository discovery and code search) |
| `error_signatures` | string list | yes | Error message templates, exception class names, endpoint paths, or feature flag names derived from log forensics |
| `project_scope` | string list | no | Project subset override (must be within configured `AZURE_PROJECT`) |
| `dependency_names` | string list | no | Known downstream dependency names to search for in client/config files |
| `endpoint_paths` | string list | no | API endpoint paths derived from error logs (e.g. `/cds/displayvalue/partTerminologyGroupId`) |

## Operations

### 1. Repository Candidate Discovery
Identify repositories likely to contain the target service code.

Behavior:
- Load `artifacts/azuregit_repo_map.json`; if absent or stale (> 24 h), trigger `azuregit-repository-operations` → Refresh Project/Repository Mapping Artifact
- Filter repositories by name proximity to `service_name` using token matching
- Return: `project`, `repository`, `defaultBranch`, `remoteUrl`, `match_reason`
- If no name-match candidates: proceed to code-search-based discovery

### 2. Code Search — Error Signatures
Search repository files for each error signature.

Behavior:
- For each `error_signature` and each candidate repository: execute scoped read-only code search
- Bound results to `max_files_per_repo = 200` and `max_results_per_query = 500`
- Return per-match: `project`, `repository`, `path`, `line_number`, `excerpt` (≤ 300 chars), `matched_signature`
- Deduplicate matches on `(project, repository, path, line_number, signature)`

### 3. Endpoint Path Tracing
Locate route definitions, handler registrations, and controller entry points for known error-producing endpoints.

Behavior:
- Search for endpoint path strings in routing files (e.g. `routes.js`, `startup.cs`, `app.py`, `application.yml`)
- Identify controller/handler class and method names
- Return: file path, line, handler name, framework hint

### 4. Dependency Client Search
Search for client code that calls known failing downstream dependencies.

Behavior:
- Search for dependency base URLs, client class names, and configuration keys in source files
- Identify retry/circuit-breaker configuration (timeout values, retry counts, backoff settings)
- Return: file path, line, configuration excerpt, dependency name

### 5. Call-Path Tracing
Trace the call path from entry point to fault location using file-content analysis.

Behavior:
- Starting from handler entry points discovered in operations 3 and 4
- Search for method invocation chains (caller → callee) via read-only content retrieval
- Return: ordered call chain list with file paths and line numbers where available
- Depth limit: 4 levels to prevent runaway traversal

### 6. Attribution Evidence Assembly
Assemble final attribution candidates with confidence scoring.

Confidence scoring criteria:

| Evidence Level | Confidence |
|---|---|
| Direct signature match + handler trace + dependency client found | High |
| Signature match in 2+ files + endpoint or dependency reference | Medium |
| Signature match in 1 file only, no corroborating evidence | Low |
| No matches in any configured repository | Not verified |

Output schema per candidate:

```
{
  "project": "<azure-devops-project>",
  "repository": "<repository-name>",
  "path": "<file-path>",
  "line": <line-number-or-null>,
  "excerpt": "<code-excerpt>",
  "confidence": "high|medium|low|not_verified",
  "evidence_type": "observed|inferred|unknown",
  "matched_signatures": ["<sig1>", "<sig2>"],
  "attribution_notes": "<free-text rationale>"
}
```

### 7. No-Match Reporting
When no attribution evidence is found, produce an explicit no-match report.

Required fields:
```
{
  "status": "no_evidence",
  "reason": "<specific reason: no matching repo / PAT scope insufficient / config gap>",
  "searched_projects": ["<project1>", "<project2>"],
  "searched_queries": ["<sig1>", "<sig2>"],
  "next_step": "<exact action required to unblock attribution>"
}
```

## Outputs

| Output | Description |
|---|---|
| `repository_candidates` | Repositories matching service name with discovery evidence |
| `attribution_candidates` | File/line candidates with confidence scores and evidence schema |
| `call_path_traces` | Handler-to-dependency call chains |
| `dependency_client_locations` | Retry/timeout configuration file references |
| `no_match_report` | Explicit no-evidence record when no attribution found |
| `query_parameters` | Reproducibility record: queries, project scope, result limits |

## AzureGit Attribution Rules (Strict)

1. Use only configured `AZURE_ORG` and `AZURE_PROJECT` scope
2. If repository mapping is incomplete: report `Repository mapping incomplete; attribution partial`
3. Never infer exact line numbers without direct file-content evidence
4. Never fabricate project names, repository names, file paths, or symbol names
5. Distinguish clearly between:
   - `observed evidence` — direct match in retrieved file content
   - `inferred hypothesis` — logical deduction from partial matches
   - `unknown/unverified` — no matching evidence in scope

## Validation Standards

- Do not proceed if `AZURE_ORG`, `AZURE_PROJECT`, or `AZURE_PAT` are absent; report as `Configuration gap`
- Do not execute write operations of any kind
- Do not access projects outside configured `AZURE_PROJECT` scope
- Do not return unbounded result sets — enforce per-query limits
- If PAT lacks code-search scope, report `PAT scope insufficient for code search` and fall back to repository-name-based discovery only
