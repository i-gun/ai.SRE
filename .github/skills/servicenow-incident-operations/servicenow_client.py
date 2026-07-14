"""ServiceNow incident operations client.

Capabilities:
- List incidents constrained to designated assignment groups
- Create incidents with required input validation
- Assign or reassign incidents in designated assignment groups
- Update incident work notes and optional operational fields
- Change priority via impact/urgency matrix mapping
- Create a problem (PRB) from an incident and link them
- Create an issue from a problem with fixed project selection
- Resolve incidents with resolution note quality validation

Authentication:
- Basic auth using .env variables:
  - SERVICENOW_HOST
  - SERVICENOW_USERNAME
  - SERVICENOW_PASSWORD
  - SERVICENOW_ASSIGNMENT_GROUPS
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import requests


class ServiceNowConfigError(Exception):
    """Raised when ServiceNow configuration is invalid."""


class ServiceNowValidationError(Exception):
    """Raised when operation inputs fail validation checks."""


class ServiceNowAPIError(Exception):
    """Raised when ServiceNow API call fails."""


@dataclass
class ServiceNowConfig:
    host: str
    username: str
    password: str
    assignment_groups: List[str]

    @classmethod
    def from_env(cls) -> "ServiceNowConfig":
        host = os.getenv("SERVICENOW_HOST", "").strip()
        username = os.getenv("SERVICENOW_USERNAME", "").strip()
        password = os.getenv("SERVICENOW_PASSWORD", "").strip()
        assignment_groups_raw = os.getenv("SERVICENOW_ASSIGNMENT_GROUPS", "").strip()
        assignment_groups = cls._parse_assignment_groups(assignment_groups_raw)

        missing = [
            name
            for name, value in [
                ("SERVICENOW_HOST", host),
                ("SERVICENOW_USERNAME", username),
                ("SERVICENOW_PASSWORD", password),
                ("SERVICENOW_ASSIGNMENT_GROUPS", assignment_groups_raw),
            ]
            if not value
        ]

        if missing:
            raise ServiceNowConfigError(
                "Missing required ServiceNow environment variables: " + ", ".join(missing)
            )

        if not (host.startswith("https://") or host.startswith("http://")):
            raise ServiceNowConfigError(
                "SERVICENOW_HOST must start with http:// or https://"
            )

        if not assignment_groups:
            raise ServiceNowConfigError(
                "SERVICENOW_ASSIGNMENT_GROUPS must include at least one assignment group."
            )

        return cls(
            host=host.rstrip("/"),
            username=username,
            password=password,
            assignment_groups=assignment_groups,
        )

    @staticmethod
    def _parse_assignment_groups(raw_value: str) -> List[str]:
        parsed: List[str] = []
        seen: Set[str] = set()
        for item in raw_value.split(","):
            value = item.strip()
            if not value or value in seen:
                continue
            parsed.append(value)
            seen.add(value)
        return parsed


class ServiceNowClient:
    """Client wrapper for ServiceNow incident operations."""

    INCIDENT_TABLE_PATH = "/api/now/table/incident"
    PROBLEM_TABLE_PATH = "/api/now/table/problem"
    ISSUE_TABLE_PATH = "/api/now/table/issue"

    LIST_FIELDS = [
        "sys_id",
        "number",
        "short_description",
        "description",
        "category",
        "subcategory",
        "service_offering",
        "cmdb_ci",
        "state",
        "priority",
        "impact",
        "urgency",
        "caller_id",
        "assigned_to",
        "assignment_group",
        "problem_id",
        "sys_updated_on",
    ]

    PROBLEM_FIELDS = [
        "sys_id",
        "number",
        "short_description",
        "description",
        "category",
        "subcategory",
        "service_offering",
        "cmdb_ci",
        "assignment_group",
        "problem_statement",
        "sys_updated_on",
    ]

    DEFAULT_TIMEOUT_SECONDS = 30

    # Priority matrix: (impact, urgency) -> priority
    PRIORITY_MATRIX: Dict[tuple[str, str], str] = {
        ("1", "1"): "1",
        ("1", "2"): "2",
        ("1", "3"): "3",
        ("2", "1"): "2",
        ("2", "2"): "3",
        ("2", "3"): "4",
        ("3", "1"): "3",
        ("3", "2"): "4",
        ("3", "3"): "5",
    }

    # Deterministic defaults when multiple pairs map to same priority.
    PRIORITY_DEFAULT_IMPACT_URGENCY: Dict[str, tuple[str, str]] = {
        "1": ("1", "1"),
        "2": ("1", "2"),
        "3": ("2", "2"),
        "4": ("2", "3"),
        "5": ("3", "3"),
    }

    def __init__(self, config: ServiceNowConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.username, config.password)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def from_env(cls) -> "ServiceNowClient":
        return cls(ServiceNowConfig.from_env())

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
            raise ServiceNowAPIError(f"ServiceNow request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = self._safe_error_detail(response)
            raise ServiceNowAPIError(
                f"ServiceNow API error ({response.status_code}): {detail}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ServiceNowAPIError("ServiceNow returned non-JSON response") from exc

        return payload

    @staticmethod
    def _safe_error_detail(response: requests.Response) -> str:
        try:
            body = response.json()
            if isinstance(body, dict):
                err = body.get("error") or body.get("message") or body
                return str(err)
            return str(body)
        except ValueError:
            return response.text[:300] if response.text else "Unknown error"

    def _designated_assignment_group_query_clause(self) -> str:
        # Use display name matching from .env (group names), not sys_id values.
        return "assignment_group.nameIN" + ",".join(self.config.assignment_groups)

    def _is_designated_assignment_group(self, incident: Dict[str, Any]) -> bool:
        assignment_group = incident.get("assignment_group")
        if assignment_group is None:
            return False

        candidate_values: Set[str] = set()
        if isinstance(assignment_group, str):
            value = assignment_group.strip()
            if value:
                candidate_values.add(value)
        elif isinstance(assignment_group, dict):
            for key in ("value", "display_value"):
                raw = assignment_group.get(key)
                if isinstance(raw, str):
                    value = raw.strip()
                    if value:
                        candidate_values.add(value)

        if not candidate_values:
            return False

        return any(
            candidate in self.config.assignment_groups for candidate in candidate_values
        )

    def _validate_incident_assignment_group_scope(self, incident: Dict[str, Any]) -> None:
        if self._is_designated_assignment_group(incident):
            return

        configured_groups = ", ".join(self.config.assignment_groups)
        raise ServiceNowValidationError(
            "Incident is outside designated assignment groups. "
            f"Allowed groups: {configured_groups}"
        )

    @staticmethod
    def _extract_reference_value(value: Any) -> str:
        if isinstance(value, dict):
            raw = value.get("value") or value.get("display_value") or ""
            return str(raw).strip()
        return str(value or "").strip()

    def _validate_assignment_group_allowed(self, assignment_group: str) -> None:
        group = (assignment_group or "").strip()
        if not group:
            raise ServiceNowValidationError("assignment_group is required")
        if group not in self.config.assignment_groups:
            configured_groups = ", ".join(self.config.assignment_groups)
            raise ServiceNowValidationError(
                "assignment_group must be one of the designated groups. "
                f"Allowed groups: {configured_groups}"
            )

    def _find_incident(
        self, *, incident_number: Optional[str], sys_id: Optional[str]
    ) -> Dict[str, Any]:
        if not incident_number and not sys_id:
            raise ServiceNowValidationError(
                "Either incident_number or sys_id must be provided."
            )

        if sys_id:
            result = self._request(
                "GET",
                f"{self.INCIDENT_TABLE_PATH}/{sys_id}",
                params={
                    "sysparm_fields": ",".join(
                        self.LIST_FIELDS + ["close_code", "close_notes", "active"]
                    ),
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                },
            )
            incident = result.get("result")
            if not incident:
                raise ServiceNowValidationError(f"Incident with sys_id '{sys_id}' was not found.")
            self._validate_incident_assignment_group_scope(incident)
            return incident

        query = "^".join(
            [
                f"number={incident_number}",
                self._designated_assignment_group_query_clause(),
            ]
        )
        result = self._request(
            "GET",
            self.INCIDENT_TABLE_PATH,
            params={
                "sysparm_query": query,
                "sysparm_limit": 1,
                "sysparm_fields": ",".join(self.LIST_FIELDS + ["close_code", "close_notes", "active"]),
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )

        records = result.get("result", [])
        if not records:
            raise ServiceNowValidationError(
                f"Incident with number '{incident_number}' was not found."
            )
        self._validate_incident_assignment_group_scope(records[0])
        return records[0]

    def _find_problem(
        self, *, problem_number: Optional[str], sys_id: Optional[str]
    ) -> Dict[str, Any]:
        if not problem_number and not sys_id:
            raise ServiceNowValidationError(
                "Either problem_number or sys_id must be provided."
            )

        if sys_id:
            result = self._request(
                "GET",
                f"{self.PROBLEM_TABLE_PATH}/{sys_id}",
                params={
                    "sysparm_fields": ",".join(self.PROBLEM_FIELDS),
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                },
            )
            problem = result.get("result")
            if not problem:
                raise ServiceNowValidationError(f"Problem with sys_id '{sys_id}' was not found.")
            return problem

        query = f"number={problem_number}"
        result = self._request(
            "GET",
            self.PROBLEM_TABLE_PATH,
            params={
                "sysparm_query": query,
                "sysparm_limit": 1,
                "sysparm_fields": ",".join(self.PROBLEM_FIELDS),
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )

        records = result.get("result", [])
        if not records:
            raise ServiceNowValidationError(
                f"Problem with number '{problem_number}' was not found."
            )
        return records[0]

    def list_incidents(
        self,
        *,
        assigned_to: Optional[str] = None,
        assignment_group: Optional[str] = None,
        active_only: bool = True,
        unassigned_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List incidents scoped to designated assignment groups."""

        if limit <= 0 or limit > 500:
            raise ServiceNowValidationError("limit must be between 1 and 500")

        query_parts: List[str] = []
        if assigned_to:
            query_parts.append(f"assigned_to={assigned_to}")

        if assignment_group:
            if assignment_group not in self.config.assignment_groups:
                configured_groups = ", ".join(self.config.assignment_groups)
                raise ServiceNowValidationError(
                    "assignment_group must be one of the designated groups. "
                    f"Allowed groups: {configured_groups}"
                )
            query_parts.append(f"assignment_group.name={assignment_group}")
        else:
            query_parts.append(self._designated_assignment_group_query_clause())

        if active_only:
            query_parts.append("active=true")

        if unassigned_only:
            query_parts.append("assigned_toISEMPTY")

        query = "^".join(query_parts)

        result = self._request(
            "GET",
            self.INCIDENT_TABLE_PATH,
            params={
                "sysparm_query": query,
                "sysparm_limit": limit,
                "sysparm_fields": ",".join(self.LIST_FIELDS),
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_order_by_desc": "sys_updated_on",
            },
        )

        return result.get("result", [])

    def create_incident(
        self,
        *,
        short_description: str,
        description: str,
        caller_id: str,
        assignment_group: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        impact: str = "3",
        urgency: str = "3",
        work_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new incident using required and validated inputs."""
        short_desc = (short_description or "").strip()
        details = (description or "").strip()
        caller = (caller_id or "").strip()
        if not short_desc:
            raise ServiceNowValidationError("short_description is required")
        if not details:
            raise ServiceNowValidationError("description is required")
        if not caller:
            raise ServiceNowValidationError("caller_id is required")

        group = (assignment_group or "").strip() or self.config.assignment_groups[0]
        self._validate_assignment_group_allowed(group)

        impact_value = str(impact).strip()
        urgency_value = str(urgency).strip()
        if impact_value not in {"1", "2", "3"}:
            raise ServiceNowValidationError("impact must be one of: 1, 2, 3")
        if urgency_value not in {"1", "2", "3"}:
            raise ServiceNowValidationError("urgency must be one of: 1, 2, 3")

        payload: Dict[str, Any] = {
            "short_description": short_desc,
            "description": details,
            "caller_id": caller,
            "assignment_group": group,
            "impact": impact_value,
            "urgency": urgency_value,
        }
        if category and category.strip():
            payload["category"] = category.strip()
        if subcategory and subcategory.strip():
            payload["subcategory"] = subcategory.strip()
        if work_note and work_note.strip():
            payload["work_notes"] = work_note.strip()

        result = self._request(
            "POST",
            self.INCIDENT_TABLE_PATH,
            json=payload,
            params={
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_fields": ",".join(self.LIST_FIELDS),
            },
        )

        created = result.get("result", {})
        self._validate_incident_assignment_group_scope(created)
        return created

    def assign_incident(
        self,
        *,
        incident_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        assigned_to: str,
        allow_reassign: bool = True,
        work_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assign or reassign an incident to a user.

        Args:
            incident_number: Incident number (e.g., INC0012345)
            sys_id: Incident sys_id
            assigned_to: User identifier accepted by ServiceNow for assigned_to
            allow_reassign: If False, fails when incident already has an assignee
            work_note: Optional transition note to append while assigning
        """
        assignee = (assigned_to or "").strip()
        if not assignee:
            raise ServiceNowValidationError("assigned_to is required")

        incident = self._find_incident(incident_number=incident_number, sys_id=sys_id)
        target_sys_id = incident.get("sys_id")
        if not target_sys_id:
            raise ServiceNowValidationError("Target incident does not have sys_id")

        current_assignee = incident.get("assigned_to")
        if not allow_reassign and current_assignee:
            raise ServiceNowValidationError(
                "Incident already has an assignee; set allow_reassign=True to overwrite assigned_to."
            )

        payload: Dict[str, Any] = {"assigned_to": assignee}
        if work_note and work_note.strip():
            payload["work_notes"] = work_note.strip()

        result = self._request(
            "PATCH",
            f"{self.INCIDENT_TABLE_PATH}/{target_sys_id}",
            json=payload,
            params={"sysparm_display_value": "true", "sysparm_exclude_reference_link": "true"},
        )

        return result.get("result", {})

    @staticmethod
    def _normalize_priority_request(priority: str) -> str:
        value = (priority or "").strip().lower()
        if not value:
            raise ServiceNowValidationError("priority is required")

        compact = value.replace(" ", "")
        if compact in {"1", "2", "3", "4", "5"}:
            return compact
        if compact in {"p1", "p2", "p3", "p4", "p5"}:
            return compact[1:]
        if compact.startswith("priority") and compact[len("priority") :] in {
            "1",
            "2",
            "3",
            "4",
            "5",
        }:
            return compact[len("priority") :]

        raise ServiceNowValidationError(
            "priority must be one of: 1..5, P1..P5, or 'priority 1'..'priority 5'"
        )

    def set_priority_by_matrix(
        self,
        *,
        incident_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        target_priority: str,
        work_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set incident priority by updating impact and urgency using the matrix rules.

        This method does not patch the priority field directly.
        """
        normalized_priority = self._normalize_priority_request(target_priority)
        impact, urgency = self.PRIORITY_DEFAULT_IMPACT_URGENCY[normalized_priority]

        incident = self._find_incident(incident_number=incident_number, sys_id=sys_id)
        target_sys_id = incident.get("sys_id")
        if not target_sys_id:
            raise ServiceNowValidationError("Target incident does not have sys_id")

        payload: Dict[str, Any] = {
            "impact": impact,
            "urgency": urgency,
        }
        if work_note and work_note.strip():
            payload["work_notes"] = work_note.strip()

        result = self._request(
            "PATCH",
            f"{self.INCIDENT_TABLE_PATH}/{target_sys_id}",
            json=payload,
            params={"sysparm_display_value": "true", "sysparm_exclude_reference_link": "true"},
        )

        updated = result.get("result", {})

        # Validate resulting priority whenever it is returned by ServiceNow.
        resulting_priority = updated.get("priority")
        if isinstance(resulting_priority, dict):
            resulting_priority = (
                resulting_priority.get("value")
                or resulting_priority.get("display_value")
                or ""
            )
        resulting_priority_text = str(resulting_priority).strip()
        if resulting_priority_text and not resulting_priority_text.startswith(normalized_priority):
            raise ServiceNowValidationError(
                "Priority update completed but resulting priority does not match requested target. "
                f"Requested: {normalized_priority}, Result: {resulting_priority_text}"
            )

        return updated

    def create_problem_from_incident(
        self,
        *,
        incident_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        problem_short_description: Optional[str] = None,
        problem_description: Optional[str] = None,
        work_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a problem from an incident and link both records."""
        incident = self._find_incident(incident_number=incident_number, sys_id=sys_id)
        incident_sys_id = incident.get("sys_id")
        if not incident_sys_id:
            raise ServiceNowValidationError("Target incident does not have sys_id")

        incident_number_value = self._extract_reference_value(incident.get("number"))
        incident_short_desc = self._extract_reference_value(incident.get("short_description"))
        incident_desc = self._extract_reference_value(incident.get("description"))
        incident_group = self._extract_reference_value(incident.get("assignment_group"))
        incident_configuration_item = self._extract_reference_value(incident.get("cmdb_ci"))

        problem_short = (problem_short_description or "").strip()
        if not problem_short:
            base_short = incident_short_desc or "Incident follow-up"
            suffix = incident_number_value or "incident"
            problem_short = f"Problem from {suffix}: {base_short}"[:160]

        problem_desc = (problem_description or "").strip()
        if not problem_desc:
            problem_desc = (
                f"Raised from incident {incident_number_value or incident_sys_id}.\n\n"
                f"Incident short description: {incident_short_desc or 'N/A'}\n"
                f"Incident details: {incident_desc or 'N/A'}"
            )

        problem_payload: Dict[str, Any] = {
            "origin_task": incident_number_value,
            "category": "Application",
            "subcategory": "E-Commerce",
            "problem_statement": incident_short_desc,
            "short_description": problem_short,
            "description": problem_desc,
        }
        if incident_group:
            problem_payload["assignment_group"] = incident_group
        if incident_configuration_item:
            problem_payload["service_offering"] = incident_configuration_item
            problem_payload["cmdb_ci"] = incident_configuration_item

        problem_result = self._request(
            "POST",
            self.PROBLEM_TABLE_PATH,
            json=problem_payload,
            params={
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )
        created_problem = problem_result.get("result", {})
        problem_sys_id = self._extract_reference_value(created_problem.get("sys_id"))
        if not problem_sys_id:
            raise ServiceNowValidationError("Created problem does not have sys_id")

        incident_patch_payload: Dict[str, Any] = {
            "problem_id": problem_sys_id,
        }
        if work_note and work_note.strip():
            incident_patch_payload["work_notes"] = work_note.strip()

        incident_update_result = self._request(
            "PATCH",
            f"{self.INCIDENT_TABLE_PATH}/{incident_sys_id}",
            json=incident_patch_payload,
            params={
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_fields": ",".join(self.LIST_FIELDS),
            },
        )

        updated_incident = incident_update_result.get("result", {})

        return {
            "problem": created_problem,
            "incident": updated_incident,
        }

    def create_issue_from_problem(
        self,
        *,
        problem_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        issue_short_description: Optional[str] = None,
        issue_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an issue from a problem using fixed project selection rules."""
        problem = self._find_problem(problem_number=problem_number, sys_id=sys_id)
        problem_sys_id = self._extract_reference_value(problem.get("sys_id"))
        if not problem_sys_id:
            raise ServiceNowValidationError("Target problem does not have sys_id")

        problem_number_value = self._extract_reference_value(problem.get("number"))
        problem_short_desc = self._extract_reference_value(problem.get("short_description"))
        problem_desc = self._extract_reference_value(problem.get("description"))
        problem_category = self._extract_reference_value(problem.get("category"))
        problem_subcategory = self._extract_reference_value(problem.get("subcategory"))
        problem_service_offering = self._extract_reference_value(problem.get("service_offering"))
        problem_configuration_item = self._extract_reference_value(problem.get("cmdb_ci"))

        issue_short = (issue_short_description or "").strip()
        if not issue_short:
            base_short = problem_short_desc or "Problem follow-up"
            suffix = problem_number_value or "problem"
            issue_short = f"Issue from {suffix}: {base_short}"[:160]

        issue_desc = (issue_description or "").strip()
        if not issue_desc:
            issue_desc = problem_desc or "Raised from linked problem record."

        issue_payload: Dict[str, Any] = {
            "short_description": issue_short,
            "description": issue_desc,
            "select_project": "Digital Delivery",
            "problem": problem_sys_id,
        }
        if problem_category:
            issue_payload["category"] = problem_category
        if problem_subcategory:
            issue_payload["subcategory"] = problem_subcategory
        if problem_service_offering:
            issue_payload["service_offering"] = problem_service_offering
        if problem_configuration_item:
            issue_payload["cmdb_ci"] = problem_configuration_item

        result = self._request(
            "POST",
            self.ISSUE_TABLE_PATH,
            json=issue_payload,
            params={
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )

        created_issue = result.get("result", {})
        if not self._extract_reference_value(created_issue.get("sys_id")):
            raise ServiceNowValidationError("Created issue does not have sys_id")

        return {
            "problem": problem,
            "issue": created_issue,
        }

    def add_work_note(
        self,
        *,
        incident_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        work_note: str,
        state: Optional[str] = None,
        assigned_to: Optional[str] = None,
        assignment_group: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append work note and optionally update selected fields."""
        note = (work_note or "").strip()
        if not note:
            raise ServiceNowValidationError("work_note cannot be empty")

        incident = self._find_incident(incident_number=incident_number, sys_id=sys_id)
        target_sys_id = incident.get("sys_id")
        if not target_sys_id:
            raise ServiceNowValidationError("Target incident does not have sys_id")

        update_payload: Dict[str, Any] = {"work_notes": note}

        if state is not None:
            update_payload["state"] = state
        if assigned_to is not None:
            update_payload["assigned_to"] = assigned_to
        if assignment_group is not None:
            if assignment_group not in self.config.assignment_groups:
                configured_groups = ", ".join(self.config.assignment_groups)
                raise ServiceNowValidationError(
                    "assignment_group must be one of the designated groups. "
                    f"Allowed groups: {configured_groups}"
                )
            update_payload["assignment_group"] = assignment_group

        result = self._request(
            "PATCH",
            f"{self.INCIDENT_TABLE_PATH}/{target_sys_id}",
            json=update_payload,
            params={"sysparm_display_value": "true", "sysparm_exclude_reference_link": "true"},
        )

        return result.get("result", {})

    @staticmethod
    def _validate_resolution_note(close_notes: str) -> None:
        note = (close_notes or "").strip()
        if not note:
            raise ServiceNowValidationError("close_notes is required for resolution")

        if len(note) < 30:
            raise ServiceNowValidationError(
                "close_notes is too short. Provide a meaningful remediation summary."
            )

        weak_notes = {"fixed", "resolved", "done", "n/a"}
        if note.lower() in weak_notes:
            raise ServiceNowValidationError(
                "close_notes is too generic. Include what was changed and why it resolved the issue."
            )

    def resolve_incident(
        self,
        *,
        incident_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        close_code: str,
        close_notes: str,
        work_note: Optional[str] = None,
        resolved_state: str = "6",
    ) -> Dict[str, Any]:
        """Resolve incident after validating resolution inputs and state."""
        code = (close_code or "").strip()
        if not code:
            raise ServiceNowValidationError("close_code is required for resolution")

        self._validate_resolution_note(close_notes)

        incident = self._find_incident(incident_number=incident_number, sys_id=sys_id)
        target_sys_id = incident.get("sys_id")
        if not target_sys_id:
            raise ServiceNowValidationError("Target incident does not have sys_id")

        active_value = str(incident.get("active", "")).lower()
        if active_value in {"false", "0"}:
            raise ServiceNowValidationError("Incident is not active and cannot be resolved.")

        payload: Dict[str, Any] = {
            "state": resolved_state,
            "close_code": code,
            "close_notes": close_notes.strip(),
        }

        if work_note and work_note.strip():
            payload["work_notes"] = work_note.strip()

        result = self._request(
            "PATCH",
            f"{self.INCIDENT_TABLE_PATH}/{target_sys_id}",
            json=payload,
            params={"sysparm_display_value": "true", "sysparm_exclude_reference_link": "true"},
        )

        return result.get("result", {})
