---
name: 'jira-issue-operations'
description: 'Jira Cloud issue operations skill for project lookup, dashboard discovery, JQL issue search, issue fetch/create/update, comments, and issue linking using .env-based host, username, and API token authentication.'
keywords: ['jira', 'issue', 'jql', 'dashboard', 'comment', 'link']
---

# Jira Issue Operations Skill

This skill provides Jira Cloud operational capabilities for project discovery and issue lifecycle management using `.env` credentials.

## Credential Requirements

The skill expects these variables in `.env`:
- `JIRA_HOST` (example: `https://your-domain.atlassian.net`)
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`

Security rules:
- Do not log credential values
- Do not commit `.env`
- Use `.env.template` for structure and `.env.example` for sanitized examples

## Supported Operations

### 1. Lookup Projects
Retrieve Jira projects accessible to the configured identity.

Behavior:
- Return concise project summaries
- Support bounded result counts
- Treat projects as lookup targets, not admin-managed resources

### 2. Lookup Dashboards
Retrieve Jira dashboards visible to the configured identity.

Behavior:
- Return concise dashboard summaries
- Support bounded result counts
- Treat dashboards as read-only discovery targets

### 3. Search Issues With JQL
Search Jira issues via JQL.

Validation:
- JQL must be provided and non-empty
- Result count must remain bounded

Behavior:
- Default to a concise field set
- Return issue summaries rather than full payloads unless detail is explicitly requested

### 4. Fetch Issue Details
Retrieve a specific issue by key or ID.

Validation:
- Issue identifier required

Behavior:
- Return normalized issue details with focused fields

### 5. Create Issue
Create a Jira issue after collecting required inputs.

Required fields:
- `project_key`
- `issue_type`
- `summary`

Optional fields:
- `description`
- `assignee`
- `priority`
- `labels`
- `components`
- extra field mappings

Validation:
- Missing required fields must be requested from the user before create

### 6. Update Issue
Update an existing issue with minimal field changes.

Validation:
- Issue identifier required
- At least one field change required

Behavior:
- Patch only requested fields

### 7. Add Comment
Append a comment to an existing issue.

Validation:
- Issue identifier required
- Comment body cannot be empty

### 8. Link Issues
Link two existing issues.

Validation:
- Source issue identifier required
- Destination issue identifier required

Behavior:
- Use explicit link type when provided
- Default link type to `Relates` when omitted
- Optionally add a comment after link creation when requested

## API Endpoints Used

- `GET /rest/api/3/project/search`
- `GET /rest/api/3/dashboard/search`
- `POST /rest/api/3/search`
- `GET /rest/api/3/issue/{issueIdOrKey}`
- `POST /rest/api/3/issue`
- `PUT /rest/api/3/issue/{issueIdOrKey}`
- `POST /rest/api/3/issue/{issueIdOrKey}/comment`
- `POST /rest/api/3/issueLink`

## Field Set for Search and Fetch

The default issue field projection:
- `summary`
- `status`
- `assignee`
- `priority`
- `issuetype`
- `project`
- `labels`
- `updated`

## Validation Standards

- Do not perform write operations when auth validation fails
- Do not send empty JQL, empty comments, or empty issue updates
- Do not assume Jira writeable fields beyond those explicitly requested

## Python Implementation

Use [jira_client.py](jira_client.py) for operational code.

Core methods:
- `list_projects(...)`
- `list_dashboards(...)`
- `search_issues(...)`
- `get_issue(...)`
- `create_issue(...)`
- `update_issue(...)`
- `add_comment(...)`
- `link_issues(...)`