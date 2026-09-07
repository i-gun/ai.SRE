---
name: 'dynatrace-monitoring-operations'
description: 'Dynatrace monitoring operations skill for Grail/DQL log search, trend analysis, Smartscape dependency traversal, and Davis AI-evidence-first root cause analysis using .env-based environment URL and API token.'
keywords: ['dynatrace', 'dql', 'grail', 'logs', 'smartscape', 'dependencies', 'rca', 'davis']
---

# Dynatrace Monitoring Operations Skill

This skill provides Dynatrace Grail/DQL log operations, Smartscape dependency traversal, and root-cause analysis using `.env` credentials.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Credential Requirements

The skill expects these variables in `.env`:
- `DYNATRACE_ENVIRONMENT_URL` — Environment base URL, no trailing slash
- `DYNATRACE_API_TOKEN` — API Token with `storage:logs:read`, `storage:events:read`,
  `storage:entities:read`, `problems.read` scopes

Security rules:
- Do not log credential values
- Do not commit `.env`
- Use `.env.template` for structure and `.env.example` for sanitized examples

## Platform Mechanics (do not deviate from these facts)

- **Grail queries are asynchronous.** `POST {environment}/platform/storage/query/v1/query:execute`
  returns `requestToken` with `state: RUNNING` (or `SUCCEEDED` immediately for fast queries).
  When `RUNNING`, poll `POST {environment}/platform/storage/query/v1/query:poll` with the
  `requestToken` until `state: SUCCEEDED`, then read `result.records`.
- **Dependency traversal uses the Smartscape entity model**, not span/trace data:
  `GET /api/v2/entities?entitySelector=type(SERVICE),entityName(...)` returns entities with
  `fromRelationships` (callers/upstream) and `toRelationships` (dependencies/downstream).
- **Root cause analysis should prefer Davis AI's native evidence.** `GET /api/v2/problems/{problemId}`
  returns `rootCauseEntity`, `impactAnalysis`, and `evidenceDetails.details[]` — use these directly
  rather than reimplementing a custom scoring model. Only fall back to log-pattern analysis when
  this evidence is absent or inconclusive.

## Supported Operations

### 1. Search Logs
Query Grail log records via DQL `fetch logs` with text, severity, and service filters.

Validation:
- Limit must be greater than zero

Behavior:
- Filter by message content, log level (`ERROR`, `CRITICAL`, etc.), and service/entity name
- Scoped to the single configured environment
- Returns log result lists with `timestamp`, `content`, `loglevel`, `dt.entity.service`, `trace_id`

### 2. Analyze Log Trends
Return time-series log counts, optionally faceted, to surface anomaly windows.

Behavior:
- DQL pattern: `fetch logs | filter ... | summarize count(), by:{bin(timestamp, <bucket>) [, <facet>]}`
- Configurable `bucket` size (default `10m`)
- Optional `facet` dimension (e.g. `loglevel`, `dt.entity.service`)
- Returns bucketed count series

### 3. Trace Service Dependencies
Discover upstream callers and downstream dependencies of a named service using Smartscape relationships.

Behavior:
- Resolves the service entity via `entitySelector=type(SERVICE),entityName(...)`
- Reads `fromRelationships` (upstream) and `toRelationships` (downstream) from the entity payload
- Returns `upstream_services`, `downstream_services`, and a `dependency_graph` (nodes + edges)

### 4. Root Cause Analysis
Identify the most probable root cause of a problem or service degradation.

Behavior:
1. If a `problem_id` is available, fetch problem details and extract `rootCauseEntity`,
   `impactAnalysis`, `evidenceDetails.details[]` as primary evidence
2. If no Davis evidence is available/conclusive, collect error-level logs for the target
   service/window and normalize repetitive error patterns as a fallback signal
3. Return `root_cause` (labeled by evidence source), `contributing_factors`,
   `recommendation`, and `escalation_points`

## API Endpoints Used

- `POST {environment}/platform/storage/query/v1/query:execute` — Grail DQL execution
- `POST {environment}/platform/storage/query/v1/query:poll` — Grail DQL result polling
- `GET {environment}/api/v2/entities` — Smartscape entity lookup and relationships
- `GET {environment}/api/v2/problems/{problemId}` — Davis AI problem evidence

## Validation Standards

- Do not perform operations when auth validation fails
- Do not send empty DQL queries
- Do not infer high-confidence root causes without Davis evidence or corroborating log data
- Do not expose raw DQL query strings or polling mechanics to end users unless explicitly
  requested for debugging

## Python Implementation

Use [dynatrace_client.py](dynatrace_client.py) for operational code.

Core methods:
- `execute_dql(*, query, timeout_s=30)` — internal-only; handles execute+poll cycle
- `search_logs(*, message_contains, severity, service, since, limit)`
- `analyze_log_trends(*, message_contains, service, since, bucket, facet=None)`
- `trace_service_dependencies(*, service, since)`
- `root_cause_analysis(*, problem_id=None, service=None, since=None)`
