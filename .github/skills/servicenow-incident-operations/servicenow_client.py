"""ServiceNow incident operations client.

Capabilities:
- List incidents constrained to designated assignment groups
- Create incidents with required input validation
- Assign or reassign incidents in designated assignment groups
- Update incident work notes and optional operational fields
- Change priority via impact/urgency matrix mapping
- Create a problem (PRB) from an incident and link them
- Detect native ServiceNow-to-Jira capability from Problem context
- Route issue creation to native ServiceNow integration or Jira handoff
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
import re
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
    # 'Create Issue' on a Problem form creates a problem_task record (PTASK prefix).
    # The /api/now/table/issue endpoint does not exist on this instance.
    PROBLEM_TASK_TABLE_PATH = "/api/now/table/problem_task"
    SUPPORTED_ROUTING_PROJECTS = {"DDL", "ODPT"}

    # Common field names observed in ServiceNow Jira integration variants.
    PROBLEM_JIRA_SIGNAL_FIELDS = [
        "u_jira_project",
        "u_jira_ticket",
        "u_jira_issue_key",
        "u_jira_issue_url",
        "u_jira_ticket_creation_status",
    ]

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
        "u_vendor_ticket",
        "vendor_ticket",
        "sys_updated_on",
    ]

    PROBLEM_FIELDS = [
        "sys_id",
        "number",
        "origin_task",
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

    # Fields returned when creating/reading a problem_task (PTASK) record.
    PROBLEM_TASK_FIELDS = [
        "sys_id",
        "number",
        "short_description",
        "description",
        "problem",
        "problem_task_type",
        "state",
        "priority",
        "assignment_group",
        "cmdb_ci",
        "u_jira_project",
        "u_jira_ticket_creation_status",
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

    @classmethod
    def is_resolved_state(cls, state_value: Any) -> bool:
        """Return True when a state value represents Resolved.

        ServiceNow responses may return either numeric state codes or display
        values depending on query parameters and instance behavior.
        """
        normalized = cls._extract_reference_value(state_value).strip().lower()
        if not normalized:
            return False
        return (
            normalized == "6"
            or normalized.startswith("6 -")
            or normalized == "resolved"
            or "resolved" in normalized
        )

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

    @staticmethod
    def _is_sys_id(value: str) -> bool:
        return bool(re.fullmatch(r"[0-9a-fA-F]{32}", value or ""))

    @classmethod
    def _assigned_to_query_clause(cls, assigned_to: str) -> str:
        assignee = (assigned_to or "").strip()
        if not assignee:
            raise ServiceNowValidationError("assigned_to must not be empty")
        if cls._is_sys_id(assignee):
            return f"assigned_to={assignee}"
        # Username-based filtering is reliable for values like Igor.Gunia.
        return f"assigned_to.user_name={assignee}"

    @staticmethod
    def _derive_incident_number_from_problem(problem: Dict[str, Any]) -> str:
        direct = ServiceNowClient._extract_reference_value(problem.get("origin_task"))
        if direct:
            return direct

        candidates = [
            ServiceNowClient._extract_reference_value(problem.get("description")),
            ServiceNowClient._extract_reference_value(problem.get("short_description")),
            ServiceNowClient._extract_reference_value(problem.get("problem_statement")),
        ]
        for candidate in candidates:
            match = re.search(r"\bINC\d{4,}\b", candidate or "", flags=re.IGNORECASE)
            if match:
                return match.group(0).upper()
        return ""

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
        exclude_resolved: bool = False,
        unassigned_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List incidents scoped to designated assignment groups."""

        if limit <= 0 or limit > 500:
            raise ServiceNowValidationError("limit must be between 1 and 500")

        query_parts: List[str] = []
        if assigned_to:
            query_parts.append(self._assigned_to_query_clause(assigned_to))

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

        if exclude_resolved:
            # Server-side guard: state code 6 is Resolved.
            query_parts.append("state!=6")

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

        incidents = result.get("result", [])
        if not exclude_resolved:
            return incidents

        # Defensive client-side guard in case instance display/value behavior
        # or ACL rules bypass the server-side state condition.
        return [
            incident
            for incident in incidents
            if not self.is_resolved_state(incident.get("state"))
        ]

    def query_incidents(
        self,
        *,
        query_parts: List[str],
        assignment_group: Optional[str] = None,
        limit: int = 50,
        fields: Optional[List[str]] = None,
        order_by_desc: Optional[str] = "sys_updated_on",
        exclude_resolved: bool = False,
    ) -> List[Dict[str, Any]]:
        """Query incidents within designated scope using additional encoded query parts.

        This helper centralizes scope enforcement for scripts that need more
        specific ServiceNow filters than list_incidents(...).
        """
        if limit <= 0 or limit > 500:
            raise ServiceNowValidationError("limit must be between 1 and 500")

        effective_query_parts: List[str] = []
        if assignment_group:
            self._validate_assignment_group_allowed(assignment_group)
            effective_query_parts.append(f"assignment_group.name={assignment_group}")
        else:
            effective_query_parts.append(self._designated_assignment_group_query_clause())

        effective_query_parts.extend(part for part in query_parts if str(part or "").strip())

        if exclude_resolved:
            effective_query_parts.append("state!=6")

        params: Dict[str, Any] = {
            "sysparm_query": "^".join(effective_query_parts),
            "sysparm_limit": limit,
            "sysparm_fields": ",".join(fields or self.LIST_FIELDS),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
        }
        if order_by_desc:
            params["sysparm_order_by_desc"] = order_by_desc

        result = self._request("GET", self.INCIDENT_TABLE_PATH, params=params)
        incidents = result.get("result", [])
        if not exclude_resolved:
            return incidents
        return [
            incident
            for incident in incidents
            if not self.is_resolved_state(incident.get("state"))
        ]

    def create_incident(
        self,
        *,
        short_description: str,
        description: str,
        caller_id: str,
        assignment_group: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        assigned_to: Optional[str] = None,
        service_offering: Optional[str] = None,
        cmdb_ci: Optional[str] = None,
        contact: Optional[str] = None,
        contact_type: Optional[str] = None,
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
        if assigned_to and assigned_to.strip():
            payload["assigned_to"] = assigned_to.strip()
        if service_offering and service_offering.strip():
            payload["service_offering"] = service_offering.strip()
        if cmdb_ci and cmdb_ci.strip():
            payload["cmdb_ci"] = cmdb_ci.strip()
        if contact and contact.strip():
            payload["u_contact"] = contact.strip()
        if contact_type and contact_type.strip():
            payload["contact_type"] = contact_type.strip()
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

    def update_incident_fields(
        self,
        *,
        incident_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        fields: Dict[str, Any],
        require_active: bool = False,
        forbid_resolved: bool = False,
    ) -> Dict[str, Any]:
        """Patch incident fields after validating scope and state constraints."""
        if not fields:
            raise ServiceNowValidationError("fields is required")

        incident = self._find_incident(incident_number=incident_number, sys_id=sys_id)
        target_sys_id = incident.get("sys_id")
        if not target_sys_id:
            raise ServiceNowValidationError("Target incident does not have sys_id")

        if require_active:
            active_value = self._extract_reference_value(incident.get("active")).lower()
            if active_value in {"false", "0", "no"}:
                raise ServiceNowValidationError("Incident is not active and cannot be updated.")

        if forbid_resolved and self.is_resolved_state(incident.get("state")):
            raise ServiceNowValidationError("Incident is already resolved and cannot be updated.")

        payload = {
            key: value
            for key, value in fields.items()
            if value is not None
        }
        if not payload:
            raise ServiceNowValidationError("fields must contain at least one non-null value")

        assignment_group = payload.get("assignment_group")
        if assignment_group is not None:
            self._validate_assignment_group_allowed(str(assignment_group))

        result = self._request(
            "PATCH",
            f"{self.INCIDENT_TABLE_PATH}/{target_sys_id}",
            json=payload,
            params={
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_fields": ",".join(self.LIST_FIELDS + ["close_code", "close_notes", "active"]),
            },
        )

        updated = result.get("result", {})
        self._validate_incident_assignment_group_scope(updated)
        return updated

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
        return self.update_incident_fields(sys_id=target_sys_id, fields=payload)

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
        updated = self.update_incident_fields(sys_id=target_sys_id, fields=payload)

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
            # origin_task is a reference field; provide the incident sys_id for reliable linkage.
            "origin_task": incident_sys_id,
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
                "sysparm_input_display_value": "true",
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
        jira_project: Optional[str] = None,
        problem_task_type: str = "General",
    ) -> Dict[str, Any]:
        """Create a Problem Task (PTASK) linked to a problem.

        ServiceNow's native 'Create Issue' button on the Problem form creates a
        problem_task record in /api/now/table/problem_task (PTASK prefix), not
        /api/now/table/issue (which does not exist on this instance).

        The optional `jira_project` field (u_jira_project) links the PTASK to a
        downstream Jira project for cross-system traceability.  For INC→PRB→Jira
        flows the Jira issue is created separately via the @Jira agent using the
        jira-create-issue-from-servicenow-handoff prompt; this method only manages
        the ServiceNow side of the chain.
        """
        problem = self._find_problem(problem_number=problem_number, sys_id=sys_id)
        problem_sys_id = self._extract_reference_value(problem.get("sys_id"))
        if not problem_sys_id:
            raise ServiceNowValidationError("Target problem does not have sys_id")

        problem_number_value = self._extract_reference_value(problem.get("number"))
        problem_short_desc = self._extract_reference_value(problem.get("short_description"))
        problem_desc = self._extract_reference_value(problem.get("description"))
        problem_category = self._extract_reference_value(problem.get("category"))
        problem_subcategory = self._extract_reference_value(problem.get("subcategory"))
        problem_configuration_item = self._extract_reference_value(problem.get("cmdb_ci"))
        problem_group = self._extract_reference_value(problem.get("assignment_group"))

        issue_short = (issue_short_description or "").strip()
        if not issue_short:
            base_short = problem_short_desc or "Problem follow-up"
            suffix = problem_number_value or "problem"
            issue_short = f"Issue from {suffix}: {base_short}"[:160]

        issue_desc = (issue_description or "").strip()
        if not issue_desc:
            issue_desc = problem_desc or "Raised from linked problem record."

        task_payload: Dict[str, Any] = {
            "short_description": issue_short,
            "description": issue_desc,
            "problem": problem_sys_id,
            "problem_task_type": problem_task_type,
        }
        if problem_category:
            task_payload["category"] = problem_category
        if problem_subcategory:
            task_payload["subcategory"] = problem_subcategory
        if problem_configuration_item:
            task_payload["cmdb_ci"] = problem_configuration_item
        if problem_group:
            task_payload["assignment_group"] = problem_group
        if jira_project and jira_project.strip():
            task_payload["u_jira_project"] = jira_project.strip()

        result = self._request(
            "POST",
            self.PROBLEM_TASK_TABLE_PATH,
            json=task_payload,
            params={
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_fields": ",".join(self.PROBLEM_TASK_FIELDS),
            },
        )

        created_task = result.get("result", {})
        if not self._extract_reference_value(created_task.get("sys_id")):
            raise ServiceNowValidationError("Created problem task does not have sys_id")

        return {
            "problem": problem,
            "problem_task": created_task,
        }

    def detect_native_jira_from_problem_capability(
        self,
        *,
        problem_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        routing_project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Detect whether native ServiceNow->Jira path is available for a problem.

        Outcome classes:
        - available: strong evidence native path is usable now
        - conditionally_available: integration signals exist but no reliable trigger evidence
        - unavailable: missing access/signals, use Jira handoff without PTASK creation
        """
        problem = self._find_problem(problem_number=problem_number, sys_id=sys_id)
        normalized_project = (routing_project or "").strip().upper()
        if normalized_project and normalized_project not in self.SUPPORTED_ROUTING_PROJECTS:
            raise ServiceNowValidationError(
                "routing_project must be one of: DDL, ODPT"
            )

        checks: List[Dict[str, Any]] = []
        missing_requirements: List[str] = []
        mode = "unavailable"
        confidence = "low"

        # Probe Problem Task table using Jira-related fields without creating data.
        task_probe_ok = False
        task_probe_result: List[Dict[str, Any]] = []
        try:
            response = self._request(
                "GET",
                self.PROBLEM_TASK_TABLE_PATH,
                params={
                    "sysparm_limit": 1,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                    "sysparm_fields": ",".join(
                        [
                            "number",
                            "sys_id",
                            "u_jira_project",
                            "u_jira_ticket",
                            "u_jira_issue_key",
                            "u_jira_issue_url",
                            "u_jira_ticket_creation_status",
                            "sys_updated_on",
                        ]
                    ),
                },
            )
            task_probe_result = response.get("result", []) or []
            task_probe_ok = True
            checks.append(
                {
                    "name": "problem_task_table_probe",
                    "ok": True,
                    "detail": "problem_task table is readable",
                }
            )
        except Exception as exc:
            checks.append(
                {
                    "name": "problem_task_table_probe",
                    "ok": False,
                    "detail": str(exc),
                }
            )
            missing_requirements.append("problem_task_read_access_or_fields")

        jira_signal_present = False
        existing_native_success = False
        if task_probe_ok and task_probe_result:
            sample = task_probe_result[0]
            jira_signal_present = any(
                field in sample for field in self.PROBLEM_JIRA_SIGNAL_FIELDS
            )

            status_value = self._extract_reference_value(
                sample.get("u_jira_ticket_creation_status")
            ).lower()
            ticket_value = self._extract_reference_value(
                sample.get("u_jira_ticket")
            ) or self._extract_reference_value(sample.get("u_jira_issue_key"))
            existing_native_success = bool(ticket_value) and status_value in {
                "created",
                "success",
                "succeeded",
                "complete",
                "completed",
            }

        checks.append(
            {
                "name": "jira_signal_fields_present",
                "ok": jira_signal_present,
                "detail": "jira integration fields visible on problem_task sample"
                if jira_signal_present
                else "jira integration fields were not confirmed from readable sample",
            }
        )

        if existing_native_success:
            mode = "native_via_ptask"
            confidence = "high"
            availability = "available"
            recommended_route = "servicenow_native_jira"
        elif jira_signal_present:
            mode = "native_via_ptask"
            confidence = "medium"
            availability = "conditionally_available"
            recommended_route = "jira_agent_delegation"
        else:
            availability = "unavailable"
            recommended_route = "jira_agent_delegation"
            missing_requirements.append("native_jira_trigger_evidence")

        return {
            "availability": availability,
            "mode": mode,
            "confidence": confidence,
            "problem_number": self._extract_reference_value(problem.get("number")),
            "routing_project": normalized_project or None,
            "checks": checks,
            "missing_requirements": sorted(set(missing_requirements)),
            "recommended_route": recommended_route,
        }

    def create_native_jira_issue_from_problem(
        self,
        *,
        problem_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        routing_project: str,
    ) -> Dict[str, Any]:
        """Attempt native ServiceNow->Jira creation from Problem context.

        This method only proceeds when capability detection reports "available".
        Current supported native mode is "native_via_ptask".
        """
        capability = self.detect_native_jira_from_problem_capability(
            problem_number=problem_number,
            sys_id=sys_id,
            routing_project=routing_project,
        )
        if capability.get("availability") != "available":
            raise ServiceNowValidationError(
                "Native ServiceNow->Jira path is not confirmed as available. "
                "Use Jira delegation instead."
            )

        if capability.get("mode") != "native_via_ptask":
            raise ServiceNowValidationError(
                "No supported native ServiceNow->Jira mode is implemented for this instance."
            )

        ptask_result = self.create_issue_from_problem(
            problem_number=problem_number,
            sys_id=sys_id,
            jira_project=routing_project,
        )
        ptask = ptask_result.get("problem_task", {})

        # Best-effort extraction from common native integration fields.
        issue_key = self._extract_reference_value(ptask.get("u_jira_ticket")) or \
            self._extract_reference_value(ptask.get("u_jira_issue_key"))
        issue_url = self._extract_reference_value(ptask.get("u_jira_issue_url")) or None

        status_value = self._extract_reference_value(
            ptask.get("u_jira_ticket_creation_status")
        )

        return {
            "route_used": "servicenow_native_jira",
            "native_mode": "native_via_ptask",
            "problem": ptask_result.get("problem", {}),
            "problem_task": ptask,
            "issue_number_or_key": issue_key or self._extract_reference_value(ptask.get("number")),
            "issue_url": issue_url,
            "issue_status": status_value or "created",
            "project": routing_project,
        }

    def create_issue_from_problem_with_routing(
        self,
        *,
        problem_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        routing_project: str,
        required_issue_type: str = "Problem",
        allow_jira_agent_fallback: bool = True,
    ) -> Dict[str, Any]:
        """Route issue creation to native ServiceNow integration or Jira handoff.

        Policy:
        - Try native only when explicitly detected as available.
        - If unavailable/conditional, do not create PTASK as fallback artifact.
        - Return a structured Jira handoff payload when delegation is required.
        """
        normalized_project = (routing_project or "").strip().upper()
        if normalized_project not in self.SUPPORTED_ROUTING_PROJECTS:
            raise ServiceNowValidationError(
                "routing_project must be one of: DDL, ODPT"
            )

        issue_type = (required_issue_type or "").strip() or "Problem"
        capability = self.detect_native_jira_from_problem_capability(
            problem_number=problem_number,
            sys_id=sys_id,
            routing_project=normalized_project,
        )

        if capability.get("availability") == "available":
            return self.create_native_jira_issue_from_problem(
                problem_number=problem_number,
                sys_id=sys_id,
                routing_project=normalized_project,
            )

        if not allow_jira_agent_fallback:
            raise ServiceNowValidationError(
                "Native ServiceNow->Jira path is not available and Jira fallback is disabled."
            )

        problem = self._find_problem(problem_number=problem_number, sys_id=sys_id)
        incident_number = self._derive_incident_number_from_problem(problem)
        return {
            "route_used": "jira_agent_delegation",
            "status": "handoff_required",
            "capability": capability,
            "handoff": {
            "incident_number": incident_number,
                "problem_number": self._extract_reference_value(problem.get("number")),
                "problem_url": None,
                "incident_summary": self._extract_reference_value(problem.get("problem_statement"))
                or self._extract_reference_value(problem.get("short_description")),
                "incident_description": self._extract_reference_value(problem.get("description")),
                "routing_project": normalized_project,
                "required_issue_type": issue_type,
                "issue_type_policy_source": "route_default",
            },
            "next_action": "delegate_to_jira_agent",
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

        return self.update_incident_fields(sys_id=target_sys_id, fields=update_payload)

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

        payload: Dict[str, Any] = {
            "state": resolved_state,
            "close_code": code,
            "close_notes": close_notes.strip(),
        }

        if work_note and work_note.strip():
            payload["work_notes"] = work_note.strip()

        return self.update_incident_fields(
            incident_number=incident_number,
            sys_id=sys_id,
            fields=payload,
            require_active=True,
            forbid_resolved=True,
        )

    def resolve_incident_with_updates(
        self,
        *,
        incident_number: Optional[str] = None,
        sys_id: Optional[str] = None,
        close_code: str,
        close_notes: str,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        service_offering: Optional[str] = None,
        vendor_ticket: Optional[str] = None,
        work_note: Optional[str] = None,
        resolved_state: str = "6",
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resolve an incident while applying additional operational fields safely."""
        code = (close_code or "").strip()
        if not code:
            raise ServiceNowValidationError("close_code is required for resolution")

        self._validate_resolution_note(close_notes)

        payload: Dict[str, Any] = {
            "state": resolved_state,
            "close_code": code,
            "close_notes": close_notes.strip(),
        }
        if category and category.strip():
            payload["category"] = category.strip()
        if subcategory and subcategory.strip():
            payload["subcategory"] = subcategory.strip()
        if service_offering and service_offering.strip():
            payload["service_offering"] = service_offering.strip()
        if vendor_ticket and vendor_ticket.strip():
            payload["u_vendor_ticket"] = vendor_ticket.strip()
            payload["vendor_ticket"] = vendor_ticket.strip()
        if work_note and work_note.strip():
            payload["work_notes"] = work_note.strip()
        if extra_fields:
            payload.update({key: value for key, value in extra_fields.items() if value is not None})

        updated = self.update_incident_fields(
            incident_number=incident_number,
            sys_id=sys_id,
            fields=payload,
            require_active=True,
            forbid_resolved=True,
        )
        if not self.is_resolved_state(updated.get("state")):
            raise ServiceNowValidationError(
                "Incident update completed but resulting state is not Resolved. "
                f"Result: {self._extract_reference_value(updated.get('state'))}"
            )
        return updated
