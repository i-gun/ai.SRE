---
name: 'dynatrace-problem-operations'
description: 'Dynatrace problem operations skill for Problems v2 search, native Davis AI evidence retrieval, and audit-trail comment-based acknowledgment using .env-based environment URL and API token.'
keywords: ['dynatrace', 'problems', 'davis', 'acknowledge', 'comment', 'severity']
---

# Dynatrace Problem Operations Skill

This skill provides Dynatrace Problems v2 search, detail retrieval, and comment-based acknowledgment using `.env` credentials.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Credential Requirements

The skill expects these variables in `.env`:
- `DYNATRACE_ENVIRONMENT_URL` — Environment base URL, no trailing slash
- `DYNATRACE_API_TOKEN` — API Token with `problems.read` and `problems.write` (comments only) scopes
- `DYNATRACE_USERNAME` — Username recorded on posted comments

Security rules:
- Do not log credential values
- Do not commit `.env`
- Use `.env.template` for structure and `.env.example` for sanitized examples

## Platform Caveat (do not contradict)

Dynatrace has **no native "acknowledge" mutation**. Problems transition `OPEN` → `CLOSED`
(automatically when resolved, or manually via close/mute operations this skill does not perform).
The closest analog to acknowledgment is posting an audit-trail comment via
`POST /api/v2/problems/{problemId}/comments`. Every acknowledgment-related response must state
that problem status is unchanged.

## Supported Operations

### 1. Search Problems
Query Dynatrace problems with status, severity, and management-zone filters.

Validation:
- Limit must be greater than zero

Behavior:
- Filter by `status` (default `OPEN`), `severity`, `management_zone`, and time window
- Returns `problemId`, `title`, `status`, `severityLevel`, `startTime`, and UI deep link

### 2. Get Problem Details
Retrieve full problem detail including Davis AI root cause evidence.

Behavior:
- `GET /api/v2/problems/{problemId}`
- Returns `rootCauseEntity`, `impactAnalysis`, `evidenceDetails.details[]`, `status`, `severityLevel`

### 3. Acknowledge Problem via Comment
Post an audit-trail comment recording that a human/agent has picked up a problem.

Validation:
- `problem_id` must be non-empty
- `username` (from `DYNATRACE_USERNAME`) must be non-empty

Behavior:
- `POST /api/v2/problems/{problemId}/comments` with message and username context
- Returns the comment ID and problem ID
- Response must explicitly state problem status is unchanged (still `OPEN`/`CLOSED` as returned by the API)
- Idempotent in effect: posting multiple comments does not fail or change status

## API Endpoints Used

- `GET {environment}/api/v2/problems` — Problem search
- `GET {environment}/api/v2/problems/{problemId}` — Problem detail + Davis evidence
- `POST {environment}/api/v2/problems/{problemId}/comments` — Audit-trail comment

## Validation Standards

- Do not perform operations when auth validation fails
- Do not describe comment posting as changing problem status
- Do not resolve, close, or mute problems — out of scope for this skill

## Python Implementation

Use [dynatrace_problems_client.py](dynatrace_problems_client.py) for operational code.

Core methods:
- `search_problems(*, status="OPEN", severity=None, management_zone=None, since, limit)`
- `get_problem_details(*, problem_id)`
- `acknowledge_problem_via_comment(*, problem_id, username, message=None)`
