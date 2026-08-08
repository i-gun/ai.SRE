---
name: 'azuregit-repository-operations'
description: 'Azure DevOps Git repository operations skill for scoped repository discovery, file listing, read-only code search, and lightweight code analysis across one or more configured projects.'
keywords: ['azure-devops', 'azuregit', 'repositories', 'code-search', 'read-only', 'analysis']
---

# AzureGit Repository Operations Skill

This skill provides read-only Azure DevOps Git operations across configured projects using `.env` credentials.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Credential Requirements

The skill expects these variables in `.env`:
- `AZURE_ORG` (Azure DevOps organization name, e.g. `my_org`)
- `AZURE_PROJECT` (comma-separated project list, e.g. `project_1,project_2`)
- `AZURE_PAT` (PAT with read scopes only)
- `AZURE_API_VERSION` (optional, defaults to `7.1`)

Security rules:
- Do not log credential values
- Do not commit `.env`
- Use `.env.template` for structure and `.env.example` for sanitized examples

## Supported Operations

### 0. Refresh Project/Repository Mapping Artifact
Refresh and persist a project/repository mapping snapshot when mapping data is requested.

Behavior:
- Uses `scripts/azuregit/fetch_repo_map.py`
- Writes local-only snapshot to `artifacts/azuregit_repo_map.json` (gitignored; regenerate per environment)
- Committed team-visible reports live in `docs/`:
  - `docs/COMBINED_SERVICE_REPOSITORY_MAPPING_REPORT.md` — Canonical combined mapping snapshot
  - `docs/AZUREGIT_REPOSITORY_MAPPING_REPORT.md` — Repository inventory snapshot
  - `docs/SERVICE_REPOSITORY_MAPPING_REPORT.md` — AzureGit-focused service-to-repository baseline analysis
- Supports forced refresh (`--force-refresh`) for latest mapping
- Supports cache freshness threshold (`--max-age-hours`)
- Returns mapping metadata (`generated_at`, `organization`, project and repository counts)

### 1. Lookup Repositories
Retrieve repositories across one or all scoped projects.

Behavior:
- Supports optional single-project override (must be in configured scope)
- Supports `name_contains` filtering
- Returns concise repository metadata

### 2. Fetch Repository Details
Retrieve one repository by ID or name in a scoped project.

Behavior:
- Requires explicit project and repository identifier
- Returns normalized repository details

### 3. List Repository Items
List files/folders from a repository with recursion support.

Behavior:
- Supports optional branch targeting
- Supports optional `scopePath`
- Returns concise item metadata
- Bounded by `limit`

### 4. Search Code (Read-Only)
Search file content in scoped repositories.

Behavior:
- Requires non-empty query
- Supports optional project/repository/path/extension constraints
- Uses read-only item-content retrieval
- Returns bounded match list with short previews

### 5. Analyze Repository Structure
Provide lightweight repository analysis summary.

Behavior:
- Reports file count and top-level directory distribution
- Reports extension frequency
- Uses read-only inventory data only

## API Endpoints Used

- `GET /{organization}/{project}/_apis/git/repositories`
- `GET /{organization}/{project}/_apis/git/repositories/{repositoryIdOrName}`
- `GET /{organization}/{project}/_apis/git/repositories/{repositoryId}/items`

## Validation Standards

- Do not perform operations when auth validation fails
- Do not resolve projects outside configured `AZURE_PROJECT` scope
- Do not accept empty search query values
- Do not run unbounded scans
- Do not execute non-GET requests

## Python Implementation

Use [azuregit_client.py](azuregit_client.py) for operational code.

Mapping refresh script:
- `scripts/azuregit/fetch_repo_map.py`

Core methods:
- `list_repositories(...)`
- `get_repository(...)`
- `list_repository_items(...)`
- `fetch_file_content(...)`
- `search_code(...)`
- `analyze_repository_structure(...)`
- `generate_repository_map(...)`
- `ensure_repository_map(...)`
