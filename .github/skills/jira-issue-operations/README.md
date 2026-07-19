# Jira Issue Operations

This skill package provides Jira Cloud lookup and issue lifecycle helpers backed by `.env` credentials.

## Required Variables

- `JIRA_HOST`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`

## Included Files

- `SKILL.md` - behavior contract for Jira project/dashboard/issue operations
- `jira_client.py` - implementation for Jira Cloud REST operations

## Supported Workflows

- List accessible Jira projects
- List visible Jira dashboards
- Search issues with JQL
- Fetch a single issue by key
- Create a new issue
- Update issue fields
- Add issue comments
- Link two issues

## Usage Examples

```python
from jira_client import JiraClient

client = JiraClient.from_env()

projects = client.list_projects(limit=10)

dashboards = client.list_dashboards(limit=10)

issues = client.search_issues(
    jql="project = ODP AND statusCategory != Done ORDER BY updated DESC",
    limit=20,
)

issue = client.get_issue("ODP-123")

created = client.create_issue(
    project_key="ODP",
    issue_type="Problem",
    summary="Recurring account pending verification errors during bot activity",
    description="Create problem-level Jira tracking from ServiceNow escalation handoff.",
    labels=["servicenow", "escalation"],
)

client.update_issue(
    issue_key="ODP-123",
    fields={"priority": {"name": "High"}},
)

client.add_comment(
    issue_key="ODP-123",
    comment="Validated migration checklist and requested final sign-off.",
)

client.link_issues(
    inward_issue_key="ODP-123",
    outward_issue_key="ODP-456",
    link_type="Blocks",
)
```

## Notes

- Jira Cloud basic auth uses `JIRA_USERNAME` and `JIRA_API_TOKEN`
- Keep `.env` local and use `.env.example` only for sanitized examples
- Dashboards are treated as read-only discovery resources in this skill
- Issue creation performs project issue-type preflight by default and fails fast if the requested issue type is unavailable