"""Jira Cloud project, dashboard, and issue operations client."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


class JiraConfigError(Exception):
    """Raised when Jira configuration is invalid."""


class JiraValidationError(Exception):
    """Raised when Jira operation inputs fail validation checks."""


class JiraAPIError(Exception):
    """Raised when Jira API calls fail."""


@dataclass
class JiraConfig:
    host: str
    username: str
    api_token: str

    @classmethod
    def from_env(cls) -> "JiraConfig":
        host = os.getenv("JIRA_HOST", "").strip()
        username = os.getenv("JIRA_USERNAME", "").strip()
        api_token = os.getenv("JIRA_API_TOKEN", "").strip()

        missing = [
            name
            for name, value in [
                ("JIRA_HOST", host),
                ("JIRA_USERNAME", username),
                ("JIRA_API_TOKEN", api_token),
            ]
            if not value
        ]

        if missing:
            raise JiraConfigError(
                "Missing required Jira environment variables: " + ", ".join(missing)
            )

        if not (host.startswith("https://") or host.startswith("http://")):
            raise JiraConfigError("JIRA_HOST must start with http:// or https://")

        return cls(
            host=host.rstrip("/"),
            username=username,
            api_token=api_token,
        )


class JiraClient:
    """Client wrapper for Jira Cloud project, dashboard, and issue operations."""

    PROJECT_SEARCH_PATH = "/rest/api/3/project/search"
    DASHBOARD_SEARCH_PATH = "/rest/api/3/dashboard/search"
    ISSUE_SEARCH_PATH = "/rest/api/3/search"
    ISSUE_PATH = "/rest/api/3/issue"
    PROJECT_STATUSES_PATH_TEMPLATE = "/rest/api/3/project/{project_key}/statuses"
    ISSUE_SEARCH_JQL_PATH = "/rest/api/3/search/jql"
    TEAM_FIELD_ID = "customfield_11002"
    DEFAULT_TIMEOUT_SECONDS = 30

    DEFAULT_ISSUE_FIELDS = [
        "summary",
        "status",
        "assignee",
        "priority",
        "issuetype",
        "project",
        "labels",
        "updated",
    ]

    def __init__(self, config: JiraConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.username, config.api_token)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def from_env(cls) -> "JiraClient":
        return cls(JiraConfig.from_env())

    def _url(self, path: str) -> str:
        return f"{self.config.host}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        try:
            response = self.session.request(
                method=method,
                url=self._url(path),
                params=params,
                json=json,
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise JiraAPIError(f"Jira request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = self._safe_error_detail(response)
            raise JiraAPIError(f"Jira API error ({response.status_code}): {detail}")

        if response.status_code == 204 or not response.text.strip():
            return {}

        try:
            payload = response.json()
        except ValueError as exc:
            raise JiraAPIError("Jira returned non-JSON response") from exc

        return payload

    @staticmethod
    def _safe_error_detail(response: requests.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text[:300] if response.text else "Unknown error"

        if isinstance(body, dict):
            messages: List[str] = []
            error_messages = body.get("errorMessages")
            if isinstance(error_messages, list):
                messages.extend(str(item) for item in error_messages if item)

            errors = body.get("errors")
            if isinstance(errors, dict):
                messages.extend(f"{key}: {value}" for key, value in errors.items())

            if messages:
                return "; ".join(messages)

            return str(body)

        return str(body)

    @staticmethod
    def _normalize_issue_key(issue_key: str) -> str:
        normalized = issue_key.strip()
        if not normalized:
            raise JiraValidationError("Issue key or ID is required.")
        return normalized

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        if limit <= 0:
            raise JiraValidationError("Limit must be greater than zero.")
        return limit

    def list_projects(self, *, limit: int = 25) -> List[Dict[str, Any]]:
        payload = self._request(
            "GET",
            self.PROJECT_SEARCH_PATH,
            params={"maxResults": self._normalize_limit(limit)},
        )
        values = payload.get("values", [])
        if not isinstance(values, list):
            raise JiraAPIError("Jira project search returned an unexpected response shape")
        return values

    def list_dashboards(self, *, limit: int = 25) -> List[Dict[str, Any]]:
        payload = self._request(
            "GET",
            self.DASHBOARD_SEARCH_PATH,
            params={"maxResults": self._normalize_limit(limit)},
        )
        values = payload.get("values", [])
        if not isinstance(values, list):
            raise JiraAPIError("Jira dashboard search returned an unexpected response shape")
        return values

    def search_issues(
        self,
        *,
        jql: str,
        limit: int = 25,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        normalized_jql = jql.strip()
        if not normalized_jql:
            raise JiraValidationError("JQL is required for Jira issue search.")

        payload = self._request(
            "POST",
            self.ISSUE_SEARCH_PATH,
            json={
                "jql": normalized_jql,
                "maxResults": self._normalize_limit(limit),
                "fields": fields or self.DEFAULT_ISSUE_FIELDS,
            },
        )
        issues = payload.get("issues", [])
        if not isinstance(issues, list):
            raise JiraAPIError("Jira issue search returned an unexpected response shape")
        return issues

    def get_issue(
        self,
        issue_key: str,
        *,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        normalized_issue_key = self._normalize_issue_key(issue_key)
        return self._request(
            "GET",
            f"{self.ISSUE_PATH}/{normalized_issue_key}",
            params={"fields": ",".join(fields or self.DEFAULT_ISSUE_FIELDS)},
        )

    def get_project_issue_types(self, *, project_key: str) -> List[str]:
        normalized_project_key = project_key.strip()
        if not normalized_project_key:
            raise JiraValidationError("project_key is required for issue type lookup.")

        payload = self._request(
            "GET",
            self.PROJECT_STATUSES_PATH_TEMPLATE.format(project_key=normalized_project_key),
        )

        records: List[Dict[str, Any]] = []
        if isinstance(payload, list):
            records = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            # Defensive compatibility for potential proxies/wrappers.
            possible = payload.get("values") or payload.get("result") or []
            if isinstance(possible, list):
                records = [item for item in possible if isinstance(item, dict)]

        issue_types: List[str] = []
        seen = set()
        for item in records:
            name = str(item.get("name") or "").strip()
            if name and name.lower() not in seen:
                issue_types.append(name)
                seen.add(name.lower())

        return issue_types

    def ensure_issue_type_available(self, *, project_key: str, issue_type: str) -> None:
        normalized_project_key = project_key.strip()
        normalized_issue_type = issue_type.strip()

        if not normalized_project_key:
            raise JiraValidationError("project_key is required for issue type preflight.")
        if not normalized_issue_type:
            raise JiraValidationError("issue_type is required for issue type preflight.")

        available_issue_types = self.get_project_issue_types(project_key=normalized_project_key)
        if not available_issue_types:
            raise JiraValidationError(
                "Unable to verify issue type availability for project "
                f"'{normalized_project_key}'."
            )

        normalized_available = {name.lower(): name for name in available_issue_types}
        if normalized_issue_type.lower() not in normalized_available:
            raise JiraValidationError(
                f"Issue type '{normalized_issue_type}' is not available in project "
                f"'{normalized_project_key}'. Available types: {', '.join(available_issue_types)}"
            )

    def create_issue(
        self,
        *,
        project_key: str,
        issue_type: str,
        summary: str,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        components: Optional[List[str]] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
        verify_issue_type_available: bool = True,
    ) -> Dict[str, Any]:
        normalized_project_key = project_key.strip()
        normalized_issue_type = issue_type.strip()
        normalized_summary = summary.strip()

        if not normalized_project_key:
            raise JiraValidationError("project_key is required for Jira issue creation.")
        if not normalized_issue_type:
            raise JiraValidationError("issue_type is required for Jira issue creation.")
        if not normalized_summary:
            raise JiraValidationError("summary is required for Jira issue creation.")

        if verify_issue_type_available:
            self.ensure_issue_type_available(
                project_key=normalized_project_key,
                issue_type=normalized_issue_type,
            )

        fields: Dict[str, Any] = {
            "project": {"key": normalized_project_key},
            "issuetype": {"name": normalized_issue_type},
            "summary": normalized_summary,
        }

        if description and description.strip():
            fields["description"] = description.strip()
        if assignee and assignee.strip():
            fields["assignee"] = {"id": assignee.strip()}
        if priority and priority.strip():
            fields["priority"] = {"name": priority.strip()}
        if labels:
            fields["labels"] = [label.strip() for label in labels if label and label.strip()]
        if components:
            fields["components"] = [
                {"name": component.strip()}
                for component in components
                if component and component.strip()
            ]
        if extra_fields:
            fields.update(extra_fields)

        return self._request("POST", self.ISSUE_PATH, json={"fields": fields})

    def update_issue(self, issue_key: str, *, fields: Dict[str, Any]) -> Dict[str, Any]:
        normalized_issue_key = self._normalize_issue_key(issue_key)
        if not fields:
            raise JiraValidationError("At least one field change is required.")

        return self._request(
            "PUT",
            f"{self.ISSUE_PATH}/{normalized_issue_key}",
            json={"fields": fields},
        )

    def resolve_team_id_from_project_history(
        self,
        *,
        project_key: str,
        team_name: str,
        limit: int = 50,
    ) -> str:
        """Resolve Atlassian Team UUID for a project by sampling recent issues.

        Team fields of schema type `team` often do not expose allowedValues,
        so this method derives a safe UUID by matching visible team names on
        recent issues where Team is already populated.
        """
        normalized_project_key = project_key.strip()
        normalized_team_name = team_name.strip()
        if not normalized_project_key:
            raise JiraValidationError("project_key is required for team resolution.")
        if not normalized_team_name:
            raise JiraValidationError("team_name is required for team resolution.")

        payload = self._request(
            "POST",
            self.ISSUE_SEARCH_JQL_PATH,
            json={
                "jql": (
                    f'project = {normalized_project_key} '
                    'AND "Team[Team]" is not EMPTY ORDER BY updated DESC'
                ),
                "maxResults": self._normalize_limit(limit),
                "fields": [self.TEAM_FIELD_ID],
            },
        )

        issues = payload.get("issues", [])
        if not isinstance(issues, list):
            raise JiraAPIError("Jira team lookup returned an unexpected response shape")

        for issue in issues:
            if not isinstance(issue, dict):
                continue
            fields = issue.get("fields", {})
            if not isinstance(fields, dict):
                continue

            team_value = fields.get(self.TEAM_FIELD_ID)
            if not isinstance(team_value, dict):
                continue

            candidate_id = str(team_value.get("id") or "").strip()
            candidate_name = str(team_value.get("name") or team_value.get("title") or "").strip()
            if not candidate_id or not candidate_name:
                continue

            if candidate_name.lower() == normalized_team_name.lower():
                return candidate_id

        raise JiraValidationError(
            "Unable to resolve team id from project history for "
            f"project '{normalized_project_key}' and team '{normalized_team_name}'."
        )

    def set_issue_team(
        self,
        *,
        issue_key: str,
        team_id: Optional[str] = None,
        team_name: Optional[str] = None,
        project_key: Optional[str] = None,
        verify: bool = True,
    ) -> Dict[str, Any]:
        """Set Team field on an issue using UUID directly or resolved from history."""
        normalized_issue_key = self._normalize_issue_key(issue_key)
        normalized_team_id = (team_id or "").strip()

        if not normalized_team_id:
            normalized_team_name = (team_name or "").strip()
            normalized_project_key = (project_key or "").strip()
            if not normalized_team_name:
                raise JiraValidationError(
                    "Either team_id or team_name must be provided for Team field update."
                )
            if not normalized_project_key:
                raise JiraValidationError(
                    "project_key is required when resolving team_id from team_name."
                )
            normalized_team_id = self.resolve_team_id_from_project_history(
                project_key=normalized_project_key,
                team_name=normalized_team_name,
            )

        self.update_issue(
            normalized_issue_key,
            fields={self.TEAM_FIELD_ID: normalized_team_id},
        )

        if not verify:
            return {
                "issue_key": normalized_issue_key,
                "team_id": normalized_team_id,
                "team_name": None,
            }

        issue = self.get_issue(normalized_issue_key, fields=[self.TEAM_FIELD_ID])
        issue_fields = issue.get("fields", {}) if isinstance(issue, dict) else {}
        team_value = issue_fields.get(self.TEAM_FIELD_ID) if isinstance(issue_fields, dict) else None

        if not isinstance(team_value, dict):
            raise JiraValidationError(
                "Team update completed but verification could not read a team object from the issue."
            )

        applied_team_id = str(team_value.get("id") or "").strip()
        if applied_team_id != normalized_team_id:
            raise JiraValidationError(
                "Team update completed but verification mismatch was detected. "
                f"Expected team id '{normalized_team_id}', got '{applied_team_id or 'N/A'}'."
            )

        applied_team_name = str(team_value.get("name") or team_value.get("title") or "").strip() or None
        return {
            "issue_key": normalized_issue_key,
            "team_id": applied_team_id,
            "team_name": applied_team_name,
        }

    def add_comment(self, issue_key: str, *, comment: str) -> Dict[str, Any]:
        normalized_issue_key = self._normalize_issue_key(issue_key)
        normalized_comment = comment.strip()
        if not normalized_comment:
            raise JiraValidationError("Comment body cannot be empty.")

        return self._request(
            "POST",
            f"{self.ISSUE_PATH}/{normalized_issue_key}/comment",
            json={"body": normalized_comment},
        )

    def link_issues(
        self,
        *,
        inward_issue_key: str,
        outward_issue_key: str,
        link_type: str = "Relates",
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_inward_issue_key = self._normalize_issue_key(inward_issue_key)
        normalized_outward_issue_key = self._normalize_issue_key(outward_issue_key)
        normalized_link_type = link_type.strip() or "Relates"

        payload: Dict[str, Any] = {
            "type": {"name": normalized_link_type},
            "inwardIssue": {"key": normalized_inward_issue_key},
            "outwardIssue": {"key": normalized_outward_issue_key},
        }

        if comment and comment.strip():
            payload["comment"] = {"body": comment.strip()}

        return self._request("POST", "/rest/api/3/issueLink", json=payload)