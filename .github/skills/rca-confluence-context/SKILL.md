---
name: 'rca-confluence-context'
description: 'Confluence operational context extraction skill for retrieving architecture documentation, service ownership pages, runbooks, known-error records, and prior RCA guidance relevant to a target incident or service.'
keywords: ['rca', 'confluence', 'architecture', 'runbook', 'known-error', 'service-ownership', 'knowledge']
---

# RCA Confluence Context Skill

This skill drives the **Confluence knowledge-acquisition stream** for RCA workflows. It retrieves architecture context, service ownership documentation, runbooks, known-error mappings, and prior RCA artifacts.

## Credential Requirements

Delegates to `confluence-authentication` and `confluence-knowledge-operations` skills.
Required variables in `.env`:

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.
## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `service_name` | string | yes | Target service or component name |
| `incident_number` | string | no | ServiceNow incident reference for cross-search |
| `error_signatures` | string list | no | Error patterns or keywords to search in pages |
| `space_keys` | string list | no | Override Confluence space scope (must be subset of configured) |

## Operations

### 1. Architecture Documentation Retrieval
Locate and retrieve architecture pages for the target service.

Behavior:
- CQL query: `space IN (<configured_spaces>) AND text ~ "<service_name>" AND ancestor = "Architecture"`
- Fallback: broader text search if ancestor filter returns no results
- Return: page title, URL, last-modified date, summary excerpt (first 500 characters of content)

### 2. Service Ownership Page Retrieval
Retrieve pages describing service ownership, on-call rotation, and team contact information.

Behavior:
- CQL query combining service name with labels or titles containing: `ownership`, `runbook`, `on-call`, `contacts`
- Return: team name, primary contact, on-call rotation reference, escalation path (if present in page)

### 3. Runbook Retrieval
Locate operational runbooks relevant to the target service or incident symptoms.

Behavior:
- Search for pages with labels: `runbook`, `playbook`, `sop`, or titles containing `runbook`
- Filter by service name proximity in content
- Return: runbook title, URL, key procedural steps (extracted from headings and ordered lists)

### 4. Known Error and Prior Incident Mapping
Retrieve documented known errors, prior RCA pages, and post-mortem records.

Behavior:
- Search for pages with labels: `known-error`, `rca`, `post-mortem`, `incident`
- Filter by service name and optionally by incident number
- Return: page title, URL, documented root cause (extracted from content), status (open/resolved)

### 5. Incident Cross-Reference Search
Search for any Confluence page referencing the target incident number.

Behavior:
- CQL: `text ~ "<incident_number>" AND space IN (<configured_spaces>)`
- Useful for finding manually authored investigation notes or stakeholder updates
- Return: page list with title, URL, last-modified date, content excerpt

## Outputs

| Output | Description |
|---|---|
| `architecture_pages` | Matched architecture documentation summaries |
| `ownership_pages` | Service ownership and contact information |
| `runbooks` | Matched runbook pages with procedural highlights |
| `known_errors` | Known error and prior RCA/post-mortem page list |
| `cross_reference_pages` | Pages referencing the incident number |
| `knowledge_gaps` | Areas where no documentation was found |
| `cql_queries` | Reproducibility record: CQL strings used, space scope |

## Validation Standards

- Do not proceed if `CONFLUENCE_HOST`, `CONFLUENCE_USERNAME`, or `CONFLUENCE_API_TOKEN` are absent
- Do not search outside configured `CONFLUENCE_SPACE_KEYS` unless explicitly overridden
- Do not infer architecture from pages that do not explicitly describe the target service
- Truncate page content extracts to 1000 characters to avoid unbounded payloads
- Report `knowledge_gaps` explicitly rather than returning empty sections silently
