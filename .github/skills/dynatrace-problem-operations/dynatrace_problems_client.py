"""Dynatrace Problems v2 client for problem search, Davis evidence retrieval, and comment-based acknowledgment."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from dynatrace_env import DynatraceAuthConfig, load_dynatrace_auth_config_from_env


class DynatraceProblemsConfigError(Exception):
    """Raised when Dynatrace configuration is invalid."""


class DynatraceProblemsValidationError(Exception):
    """Raised when operation inputs fail validation checks."""


class DynatraceProblemsAPIError(Exception):
    """Raised when Dynatrace Problems API calls fail."""


class DynatraceProblemsClient:
    """Client for Dynatrace problem search, detail retrieval, and comment-based acknowledgment.

    Note: Dynatrace has no native "acknowledge" mutation. Problems transition
    OPEN -> CLOSED (auto-resolved or manually closed elsewhere); this client only
    posts an audit-trail comment and never changes problem status.
    """

    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(self, config: DynatraceAuthConfig) -> None:
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Api-Token {config.api_token}",
            }
        )

    @classmethod
    def from_env(cls) -> "DynatraceProblemsClient":
        return cls(load_dynatrace_auth_config_from_env())

    def search_problems(
        self,
        *,
        status: str = "OPEN",
        severity: Optional[str] = None,
        management_zone: Optional[str] = None,
        since: str = "-1h",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if limit <= 0:
            raise DynatraceProblemsValidationError("limit must be greater than zero.")

        selector_parts = [f"status({status})"]
        if severity:
            selector_parts.append(f"severityLevel({severity.upper()})")
        if management_zone:
            selector_parts.append(f'managementZone("{management_zone}")')

        params = {
            "problemSelector": ",".join(selector_parts),
            "from": since,
            "pageSize": limit,
        }
        url = f"{self.config.environment_url}/api/v2/problems"
        try:
            resp = self._session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise DynatraceProblemsAPIError(f"Dynatrace problem search failed: {exc}") from exc

        problems = resp.json().get("problems", [])
        results = []
        for p in problems[:limit]:
            results.append(
                {
                    "problemId": p.get("problemId"),
                    "title": p.get("title"),
                    "status": p.get("status"),
                    "severityLevel": p.get("severityLevel"),
                    "startTime": p.get("startTime"),
                    "problemLink": f"{self.config.environment_url}/ui/apps/dynatrace.classic.problems/"
                                   f"problem/{p.get('problemId')}",
                }
            )
        return results

    def get_problem_details(self, *, problem_id: str) -> Dict[str, Any]:
        if not problem_id or not problem_id.strip():
            raise DynatraceProblemsValidationError("problem_id must not be empty.")

        url = f"{self.config.environment_url}/api/v2/problems/{problem_id}"
        try:
            resp = self._session.get(url, timeout=self.DEFAULT_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise DynatraceProblemsAPIError(f"Dynatrace problem detail fetch failed: {exc}") from exc

        problem = resp.json()
        return {
            "problemId": problem.get("problemId"),
            "status": problem.get("status"),
            "severityLevel": problem.get("severityLevel"),
            "rootCauseEntity": problem.get("rootCauseEntity"),
            "impactAnalysis": problem.get("impactAnalysis"),
            "evidenceDetails": problem.get("evidenceDetails", {}).get("details", []),
        }

    def acknowledge_problem_via_comment(
        self,
        *,
        problem_id: str,
        username: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not problem_id or not problem_id.strip():
            raise DynatraceProblemsValidationError("problem_id must not be empty.")

        attributed_user = (username or self.config.username or "").strip()
        if not attributed_user:
            raise DynatraceProblemsValidationError("username must not be empty.")

        comment_message = message or f"Acknowledged by {attributed_user} (audit-trail comment; problem status unchanged)."

        url = f"{self.config.environment_url}/api/v2/problems/{problem_id}/comments"
        body = {"message": comment_message, "context": attributed_user}
        try:
            resp = self._session.post(url, json=body, timeout=self.DEFAULT_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise DynatraceProblemsAPIError(f"Dynatrace problem comment post failed: {exc}") from exc

        location = resp.headers.get("Location", "")
        comment_id = location.rstrip("/").rsplit("/", 1)[-1] if location else None

        return {
            "problemId": problem_id,
            "commentId": comment_id,
            "acknowledgedBy": attributed_user,
            "status_changed": False,
            "note": "This posts an audit-trail comment only. Dynatrace has no acknowledge "
                    "mutation; problem status (OPEN/CLOSED) is unchanged.",
        }
