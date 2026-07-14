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
    ) -> Dict[str, Any]:
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

        if not isinstance(payload, dict):
            raise JiraAPIError("Jira returned an unexpected response shape")

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