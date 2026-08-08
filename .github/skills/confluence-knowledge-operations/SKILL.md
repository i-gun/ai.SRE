---
name: 'confluence-knowledge-operations'
description: 'Confluence Cloud knowledge operations skill for space browsing, CQL search, page retrieval, schema extraction, service linkage, and service-flow graph generation using Jira credentials plus one or more Confluence space keys.'
keywords: ['confluence', 'cql', 'knowledge', 'service', 'graph']
---

# Confluence Knowledge Operations Skill

This skill provides scoped Confluence Cloud knowledge operations for cross-page discovery and service-flow analysis using `.env` credentials.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Credential Requirements

The skill expects these variables in `.env`:
- `JIRA_HOST` (example: `https://your-domain.atlassian.net`)
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`
- `CONFLUENCE_SPACE_KEY` — single key or comma-separated list (examples: `PLATFORM` | `PLATFORM,DEV,OPS`)

Security rules:
- Do not log credential values
- Do not commit `.env`
- Use `.env.template` for structure and `.env.example` for sanitized examples

## Supported Operations

### 1. Browse Space Pages
Retrieve pages from one or all configured Confluence spaces.

Behavior:
- Return concise page summaries
- Support bounded result counts and pagination offsets
- Aggregates results across all configured space keys by default
- Accepts an optional `space_key` argument to restrict to a single space

### 2. Search Content With CQL
Search Confluence content in a bounded and space-scoped way.

Validation:
- CQL must be provided and non-empty
- Result count must remain bounded

Behavior:
- Scope queries to all configured space keys by default using `(space = "K1" OR space = "K2") AND (...)`
- Preserves existing `space =` filter in CQL without modification
- Return concise result summaries

### 3. Retrieve Page Details
Retrieve a specific page by ID.

Validation:
- Page identifier required

Behavior:
- Return normalized page details with metadata and storage body

### 4. Find Page by Title
Resolve one page by title across all configured spaces (or a specific space when provided).

Validation:
- Title must be non-empty

Behavior:
- Iterates configured space keys in order; returns the first match
- Return `None` when no match exists in any configured space

### 5. Extract Service Signals
Extract service nodes and relationships from one or more page bodies.

Behavior:
- Detect service names from headings and common naming patterns
- Detect relationship phrases (`calls`, `depends on`, `publishes to`, `consumes from`, `sends to`, `reads from`, `writes to`)
- Preserve evidence references to source pages

### 6. Build Service-Flow Graph
Build graph output from detected service relationships.

Behavior:
- Produce machine-readable graph (`nodes`, `edges`, `adjacency`)
- Produce Mermaid flowchart output
- Include graph summary metrics
- Report `space_keys` (list) instead of a single `space_key` in all graph outputs

## API Endpoints Used

- `GET /wiki/rest/api/content`
- `GET /wiki/rest/api/content/{id}`
- `GET /wiki/rest/api/content/search`

## Validation Standards

- Do not perform operations when auth validation fails
- Do not send empty CQL or empty page identifiers
- Do not infer high-confidence service links without evidence

## Python Implementation

Use [confluence_client.py](confluence_client.py) for operational code.

Core methods:
- `list_space_pages(*, limit, start, space_key=None)`
- `search_content(...)`
- `get_page(...)`
- `find_page_by_title(*, title, space_key=None)`
- `extract_service_relationships(...)`
- `build_service_flow_graph(...)`
