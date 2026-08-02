---
name: 'rca-jira-lifecycle'
description: 'Jira lifecycle interpretation skill for discovering related issues, extracting transition history, comment analysis, component and label ownership, fix-version linking, and dependency chain mapping to support RCA evidence assembly.'
keywords: ['rca', 'jira', 'lifecycle', 'transitions', 'comments', 'dependencies', 'fix-version', 'ownership']
---

# RCA Jira Lifecycle Skill

This skill drives the **Jira evidence-acquisition stream** for RCA workflows. It discovers related issues, reconstructs their lifecycle, extracts meaningful signals from comments and transitions, and maps dependencies and ownership.

## Credential Requirements

Delegates to `jira-authentication` and `jira-issue-operations` skills.
Required variables in `.env`:
- `JIRA_HOST`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `incident_number` | string | no | ServiceNow incident reference for cross-link search |
| `service_name` | string | yes | Affected service or component name |
| `error_signatures` | string list | no | Error keywords to match in issue summaries/descriptions |
| `lookback_days` | integer | no | JQL date filter depth in days (default: 90) |
| `jira_keys` | string list | no | Explicit Jira issue keys if already known |
| `max_issues` | integer | no | Maximum issues to retrieve (default: 20) |

## Operations

### 1. Related Issue Discovery
Discover Jira issues related to the incident via keyword and cross-reference search.

Behavior:
- Build JQL combining: `text ~ "<service_name>"`, component/label match, creation date filter
- If `incident_number` is provided, also search `text ~ "<incident_number>"`
- Combine and deduplicate results
- Return up to `max_issues` issues with summary fields

### 2. Issue Lifecycle Extraction
For each discovered issue, extract the full lifecycle narrative.

Behavior:
- Fetch: `key`, `summary`, `status`, `priority`, `assignee`, `reporter`, `created`, `updated`, `resolutionDate`, `resolution`, `labels`, `components`, `fixVersions`, `description`
- Retrieve transition history (status changes with timestamps and actors)
- Compute time-in-status per workflow stage
- Flag blocker transitions (issues that sat in `In Progress` or `Code Review` for > 4 hours during incident window)

### 3. Comment Analysis
Extract meaningful signals from issue comments.

Behavior:
- Retrieve all comments with `author`, `created`, and `body`
- Flag comments containing: root cause mentions, workaround steps, deployment references, external ticket cross-links, severity escalations
- Return flagged comments sorted by creation time

### 4. Component and Label Ownership
Map service/component ownership from issue metadata.

Behavior:
- Aggregate component names and labels across discovered issues
- Cross-reference with reporter and assignee fields
- Return ownership map: `component → typical_assignee_list`

### 5. Fix Version and Dependency Mapping
Identify fix versions and issue dependency chains.

Behavior:
- Collect `fixVersions` from all issues
- Traverse issue links: `is blocked by`, `blocks`, `relates to`, `duplicates`
- Return: fix version list, blocker chain, sibling issues

## Outputs

| Output | Description |
|---|---|
| `related_issues` | Discovered Jira issues with summary metadata |
| `lifecycle_records` | Per-issue lifecycle with transition history and time-in-status |
| `flagged_comments` | Comments containing actionable signals |
| `ownership_map` | Component/label to assignee mapping |
| `fix_versions` | Fix version references across issues |
| `dependency_chain` | Blocker and linked issue graph |
| `jql_queries` | Reproducibility record: JQL strings used |

## Validation Standards

- Do not proceed if `JIRA_HOST`, `JIRA_USERNAME`, or `JIRA_API_TOKEN` are absent
- Do not modify any Jira record — all operations are read-only
- Do not include issues outside the `lookback_days` window unless explicitly passed via `jira_keys`
- Do not infer ownership from a single data point — require at least 2 consistent signals
