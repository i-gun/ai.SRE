# AzureGit Repository Operations Skill

This skill enables scoped, read-only Azure DevOps Git repository operations with `.env` configuration.

## Capabilities

- Lookup repositories across configured Azure DevOps projects
- Fetch repository details by ID or name
- List repository files and folders with optional branch scoping
- Search code content with bounded scans
- Analyze repository file distribution (extensions and top-level directories)

## Required Environment Variables

Set these in `.env`:

- `AZURE_ORG`
- `AZURE_PROJECT` (comma-separated project allowlist)
- `AZURE_PAT`
- `AZURE_API_VERSION` (optional, defaults to `7.1`)

## Key Files

- `SKILL.md` - behavior and capability definition
- `azuregit_client.py` - implementation for read-only Azure DevOps Git operations

## Quick Example

```python
from azuregit_client import AzureGitClient

client = AzureGitClient.from_env()

# List repositories across scoped projects.
repos = client.list_repositories(limit=50)

# Search code in one project.
matches = client.search_code(
    query="accounts.verifyEmail",
    project="project_1",
    limit=20,
)

# Analyze one repository.
analysis = client.analyze_repository_structure(
    project="project_1",
    repository_id="my-repo",
    limit=500,
)
```

## Safety Notes

- Read-only operations only; non-GET methods are blocked
- Project scope is restricted to `AZURE_PROJECT`
- Never commit `.env` or expose PAT values
