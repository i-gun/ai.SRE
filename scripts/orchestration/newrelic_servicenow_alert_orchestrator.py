#!/usr/bin/env python3
"""Orchestrate New Relic alert acknowledgment with ServiceNow incident handling."""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEWRELIC_ALERT_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "newrelic-alert-operations"
SERVICENOW_INCIDENT_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-incident-operations"
ASSIGNMENT_PROMPT_PATH = PROJECT_ROOT / ".github" / "prompts" / "servicenow-assign-unassigned-incidents.prompt.md"


def _load_env_raw(env_path: Path) -> None:
    """Load .env without python-dotenv to preserve special characters."""
    if not env_path.exists():
        return

    with env_path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            os.environ[key] = value


@dataclass
class OrchestratorConfig:
    policy_name_starts_with: str = "Digital Operations"
    priority: Optional[str] = None
    since: str = "3 hours ago"
    limit: int = 100
    servicenow_user: str = ""
    caller_id: str = ""
    contact: str = "teams"
    channel: str = "Self-service"
    category: str = "Application"
    subcategory: str = "E-Commerce"
    service_offering: str = "Digital - New Relic Alerts - ODP"
    configuration_item: str = "Digital - New Relic Alerts - ODP"
    assignment_group: str = "IT - Epam - Monitoring - ODP"


def bootstrap() -> Path:
    """Load .env and register skill import paths."""
    env_path = PROJECT_ROOT / ".env"
    _load_env_raw(env_path)

    for skill_path in (NEWRELIC_ALERT_SKILL_PATH, SERVICENOW_INCIDENT_SKILL_PATH):
        path_str = str(skill_path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    return PROJECT_ROOT


def _extract_reference_value(value: Any) -> str:
    if isinstance(value, dict):
        raw = value.get("display_value") or value.get("value") or ""
        return str(raw).strip()
    return str(value or "").strip()


def _escape_query_value(value: str) -> str:
    return str(value or "").replace("^", " ").strip()


def _parse_since_to_timedelta(since: str) -> timedelta:
    value = (since or "").strip().lower()
    match = re.fullmatch(r"(\d+)\s+(minute|minutes|hour|hours|day|days)\s+ago", value)
    if not match:
        raise ValueError(
            "Unsupported since format. Use values like '30 minutes ago', '1 hour ago', or '3 days ago'."
        )

    amount = int(match.group(1))
    unit = match.group(2)
    if amount <= 0:
        raise ValueError("Since value amount must be greater than zero.")

    if unit in {"minute", "minutes"}:
        return timedelta(minutes=amount)
    if unit in {"hour", "hours"}:
        return timedelta(hours=amount)
    return timedelta(days=amount)


def _format_servicenow_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _normalize_match_text(value: str) -> str:
    lowered = str(value or "").lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(normalized.split())


def _matching_tokens(value: str) -> List[str]:
    tokens = [token for token in _normalize_match_text(value).split() if len(token) >= 3]
    return tokens


def _strip_quotes(value: str) -> str:
    return str(value or "").replace("'", "").replace('"', "").strip()


def _normalize_prefix_search_text(value: str) -> str:
    """Prepare alert title for STARTSWITH lookup in ServiceNow."""
    return " ".join(_strip_quotes(value).split())


def _lookup_anchor(value: str) -> str:
    original_tokens = re.findall(r"[A-Za-z0-9_-]{3,}", _strip_quotes(value))
    if original_tokens:
        return original_tokens[0]

    normalized_tokens = _matching_tokens(value)
    return normalized_tokens[0] if normalized_tokens else ""


def format_markdown_report(result: Dict[str, Any]) -> str:
    report = result.get("report", [])
    summary = result.get("summary", {})
    lines = [
        "# New Relic -> ServiceNow Orchestrator Report",
        "",
        f"- Policy prefix: `{_markdown_cell(result.get('policy_name_starts_with'))}`",
        f"- Since: `{_markdown_cell(result.get('since'))}`",
        "",
        "## Per-alert report",
        "",
        "| New Relic alert title | Acknowledgement status | ServiceNow incident | Assignee | Resolution notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report:
        lines.append(
            "| "
            f"{_markdown_cell(item.get('newrelic_alert_title'))} | "
            f"{_markdown_cell(item.get('acknowledgement_status'))} | "
            f"{_markdown_cell(item.get('servicenow_incident_number'))} | "
            f"{_markdown_cell(item.get('servicenow_assignee'))} | "
            f"{_markdown_cell(item.get('servicenow_resolution_notes'))} |"
        )

    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Open New Relic alerts acknowledged: **{summary.get('open_newrelic_alerts_acknowledged', 0)}**",
            f"- ServiceNow incidents raised (new): **{summary.get('servicenow_incidents_raised_new', 0)}**",
            (
                "- ServiceNow incidents acknowledged only (already raised): "
                f"**{summary.get('servicenow_incidents_acknowledged_only_already_raised', 0)}**"
            ),
        ]
    )
    return "\n".join(lines)


class AlertToIncidentOrchestrator:
    """Coordinates New Relic and ServiceNow alert/incident workflows."""

    def __init__(self, *, newrelic_client: Any, servicenow_client: Any, config: OrchestratorConfig):
        self.newrelic_client = newrelic_client
        self.servicenow_client = servicenow_client
        self.config = config

    def run(self) -> Dict[str, Any]:
        alerts_by_account = self.newrelic_client.fetch_open_alerts(
            policy_name_starts_with=self.config.policy_name_starts_with,
            priority=self.config.priority,
            since=self.config.since,
            limit=self.config.limit,
        )

        per_alert_report: List[Dict[str, str]] = []
        acknowledged_count = 0
        raised_new_count = 0
        existing_incident_count = 0

        for account_id, alerts in alerts_by_account.items():
            for alert in alerts:
                title = str(alert.get("title") or "").strip()
                ack_result = self._acknowledge_alert(account_id=account_id, alert=alert)
                if ack_result.get("status") == "success":
                    acknowledged_count += 1

                incident_number, assignee, incident_action, resolution_notes = self._handle_incident_for_alert(
                    alert_title=title,
                    alert_url=str(alert.get("issueLink") or "").strip(),
                )

                if incident_action == "created_new":
                    raised_new_count += 1
                elif incident_action in {
                    "existing_assigned",
                    "existing_unassigned_assigned",
                    "existing_resolved",
                }:
                    existing_incident_count += 1

                per_alert_report.append(
                    {
                        "newrelic_alert_title": title,
                        "acknowledgement_status": str(ack_result.get("status") or ""),
                        "servicenow_incident_number": incident_number,
                        "servicenow_assignee": assignee,
                        "servicenow_resolution_notes": resolution_notes,
                    }
                )

        return {
            "policy_name_starts_with": self.config.policy_name_starts_with,
            "since": self.config.since,
            "assignment_prompt_reference": str(ASSIGNMENT_PROMPT_PATH),
            "report": per_alert_report,
            "summary": {
                "open_newrelic_alerts_acknowledged": acknowledged_count,
                "servicenow_incidents_raised_new": raised_new_count,
                "servicenow_incidents_acknowledged_only_already_raised": existing_incident_count,
            },
        }

    def _acknowledge_alert(self, *, account_id: int, alert: Dict[str, Any]) -> Dict[str, Any]:
        issue_id = str(alert.get("issueId") or "").strip()
        incident_id = str(alert.get("incidentId") or "").strip()

        if not issue_id and incident_id:
            issue_id = self.newrelic_client.resolve_issue_id_from_incident_id(
                account_id=account_id,
                incident_id=incident_id,
                since=self.config.since,
            )

        if not issue_id:
            return {"status": "error: missing issueId"}

        return self.newrelic_client.acknowledge_issue(
            account_id=account_id,
            issue_id=issue_id,
        )

    def _handle_incident_for_alert(
        self,
        *,
        alert_title: str,
        alert_url: str,
    ) -> Tuple[str, str, str, str]:
        existing = self._find_incident_by_alert_title_and_time_window(alert_title)
        if existing:
            current_assignee = _extract_reference_value(existing.get("assigned_to"))
            incident_number = _extract_reference_value(existing.get("number"))
            resolution_notes = _extract_reference_value(existing.get("close_notes"))
            if not self._is_active_incident(existing):
                return incident_number, current_assignee, "existing_resolved", resolution_notes
            if current_assignee:
                return incident_number, current_assignee, "existing_assigned", resolution_notes

            updated = self._assign_unassigned_incident(existing)
            return (
                _extract_reference_value(updated.get("number")) or incident_number,
                _extract_reference_value(updated.get("assigned_to")) or self.config.servicenow_user,
                "existing_unassigned_assigned",
                resolution_notes,
            )

        created = self._create_new_incident(alert_title=alert_title, alert_url=alert_url)
        return (
            _extract_reference_value(created.get("number")),
            _extract_reference_value(created.get("assigned_to")) or self.config.servicenow_user,
            "created_new",
            "",
        )

    def _build_designated_group_clause(self) -> str:
        groups = getattr(self.servicenow_client.config, "assignment_groups", [])
        return "assignment_group.nameIN" + ",".join(groups)

    def _build_incident_lookup_query(
        self,
        *,
        alert_title: str,
        now: Optional[datetime] = None,
    ) -> str:
        current_time = now or datetime.now()
        window_start = current_time - _parse_since_to_timedelta(self.config.since)
        prefix_title = _escape_query_value(_normalize_prefix_search_text(alert_title))
        query_anchor = _escape_query_value(_lookup_anchor(alert_title))
        prefix_expression = prefix_title or query_anchor
        return "^".join(
            [
                self._build_designated_group_clause(),
                f"sys_created_on>={_format_servicenow_datetime(window_start)}",
                f"sys_created_on<={_format_servicenow_datetime(current_time)}",
                f"short_descriptionSTARTSWITH{prefix_expression}",
            ]
        )

    def _match_incident_to_alert(self, *, alert_title: str, incident: Dict[str, Any]) -> float:
        incident_title = _extract_reference_value(incident.get("short_description"))
        normalized_alert = _normalize_match_text(_strip_quotes(alert_title))
        normalized_incident = _normalize_match_text(incident_title)
        if not normalized_alert or not normalized_incident:
            return 0.0

        if normalized_alert == normalized_incident:
            return 1.0
        if normalized_alert in normalized_incident or normalized_incident in normalized_alert:
            return 0.98

        alert_tokens = set(_matching_tokens(alert_title))
        incident_tokens = set(_matching_tokens(incident_title))
        if not alert_tokens or not incident_tokens:
            return 0.0

        overlap_ratio = len(alert_tokens & incident_tokens) / len(alert_tokens)
        sequence_ratio = SequenceMatcher(None, normalized_alert, normalized_incident).ratio()

        if overlap_ratio < 0.6 and sequence_ratio < 0.72:
            return 0.0
        return max(overlap_ratio, sequence_ratio)

    @staticmethod
    def _is_active_incident(incident: Dict[str, Any]) -> bool:
        active_value = _extract_reference_value(incident.get("active")).lower()
        if active_value:
            return active_value not in {"false", "0", "no"}

        state_value = _extract_reference_value(incident.get("state")).lower()
        return state_value not in {"resolved", "closed", "6", "7"}

    def _find_incident_by_alert_title_and_time_window(self, alert_title: str) -> Optional[Dict[str, Any]]:
        query = self._build_incident_lookup_query(alert_title=alert_title)
        response = self.servicenow_client._request(
            "GET",
            self.servicenow_client.INCIDENT_TABLE_PATH,
            params={
                "sysparm_query": query,
                "sysparm_limit": max(self.config.limit * 5, 50),
                "sysparm_order_by_desc": "sys_updated_on",
                "sysparm_fields": (
                    "sys_id,number,short_description,assigned_to,assignment_group,"
                    "cmdb_ci,active,state,close_notes,sys_created_on,sys_updated_on"
                ),
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )
        incidents = response.get("result", [])
        if not incidents:
            return None

        scored_matches: List[Tuple[float, Dict[str, Any]]] = []
        for incident in incidents:
            score = self._match_incident_to_alert(alert_title=alert_title, incident=incident)
            if score > 0:
                scored_matches.append((score, incident))

        if not scored_matches:
            return None

        scored_matches.sort(
            key=lambda item: (
                item[0],
                1 if self._is_active_incident(item[1]) else 0,
                _extract_reference_value(item[1].get("sys_updated_on")),
            ),
            reverse=True,
        )
        return scored_matches[0][1]

    def _assign_unassigned_incident(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        sys_id = _extract_reference_value(incident.get("sys_id"))
        if not sys_id:
            raise ValueError("Cannot update incident without sys_id.")

        existing_ci = _extract_reference_value(incident.get("cmdb_ci"))
        payload = {
            "assigned_to": self.config.servicenow_user,
            "category": self.config.category,
            "subcategory": self.config.subcategory,
            "service_offering": existing_ci,
            "work_notes": "Auto-assigned for triage by configured ServiceNow user.",
        }
        response = self.servicenow_client._request(
            "PATCH",
            f"{self.servicenow_client.INCIDENT_TABLE_PATH}/{sys_id}",
            json=payload,
            params={
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )
        return response.get("result", {})

    def _create_new_incident(self, *, alert_title: str, alert_url: str) -> Dict[str, Any]:
        if self.config.assignment_group not in self.servicenow_client.config.assignment_groups:
            allowed = ", ".join(self.servicenow_client.config.assignment_groups)
            raise ValueError(
                "Configured assignment group is outside ServiceNow designated scope. "
                f"Allowed: {allowed}"
            )

        short_description = _strip_quotes(alert_title)
        payload = {
            "caller_id": self.config.caller_id,
            "u_contact": self.config.contact,
            "contact_type": self.config.channel,
            "category": self.config.category,
            "subcategory": self.config.subcategory,
            "service_offering": self.config.service_offering,
            "cmdb_ci": self.config.configuration_item,
            "assignment_group": self.config.assignment_group,
            "assigned_to": self.config.servicenow_user,
            "short_description": short_description,
            "description": alert_url,
        }
        response = self.servicenow_client._request(
            "POST",
            self.servicenow_client.INCIDENT_TABLE_PATH,
            json=payload,
            params={
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )
        return response.get("result", {})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Acknowledge open New Relic alerts and orchestrate ServiceNow incident "
            "lookup/assignment/creation."
        )
    )
    parser.add_argument("--policy-prefix", default="Digital Operations", help="Policy name prefix filter.")
    parser.add_argument("--priority", default=None, help="Optional New Relic priority filter.")
    parser.add_argument("--since", default="3 hours ago", help="NRQL SINCE expression.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum alerts per account.")
    parser.add_argument(
        "--servicenow-user",
        default=None,
        help="ServiceNow user for assigned_to and default caller.",
    )
    parser.add_argument(
        "--caller-id",
        default=None,
        help="ServiceNow caller_id for newly created incidents.",
    )
    parser.add_argument("--contact", default="teams", help="ServiceNow contact field value for new incidents.")
    parser.add_argument("--channel", default="Self-service", help="ServiceNow channel field value for new incidents.")
    parser.add_argument("--category", default="Application", help="ServiceNow category for incident updates/creates.")
    parser.add_argument("--subcategory", default="E-Commerce", help="ServiceNow subcategory for incident updates/creates.")
    parser.add_argument(
        "--service-offering",
        default="Digital - New Relic Alerts - ODP",
        help="Service offering for newly created incidents.",
    )
    parser.add_argument(
        "--configuration-item",
        default="Digital - New Relic Alerts - ODP",
        help="Configuration item for newly created incidents.",
    )
    parser.add_argument(
        "--assignment-group",
        default="IT - Epam - Monitoring - ODP",
        help="Assignment group for newly created incidents.",
    )
    parser.add_argument(
        "--output-format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format to print on screen.",
    )
    return parser.parse_args()


def main() -> None:
    bootstrap()
    args = parse_args()

    servicenow_user = (args.servicenow_user or os.getenv("SERVICENOW_USERNAME", "")).strip()
    caller_id = (args.caller_id or os.getenv("SERVICENOW_USERNAME", "")).strip()

    if not servicenow_user:
        raise ValueError("servicenow-user is required (or set SERVICENOW_USERNAME in .env).")
    if not caller_id:
        raise ValueError("caller-id is required (or set SERVICENOW_USERNAME in .env).")

    from newrelic_alerts_client import NewRelicAlertsClient  # pylint: disable=import-error
    from servicenow_client import ServiceNowClient  # pylint: disable=import-error

    orchestrator = AlertToIncidentOrchestrator(
        newrelic_client=NewRelicAlertsClient.from_env(),
        servicenow_client=ServiceNowClient.from_env(),
        config=OrchestratorConfig(
            policy_name_starts_with=args.policy_prefix,
            priority=args.priority,
            since=args.since,
            limit=args.limit,
            servicenow_user=servicenow_user,
            caller_id=caller_id,
            contact=args.contact,
            channel=args.channel,
            category=args.category,
            subcategory=args.subcategory,
            service_offering=args.service_offering,
            configuration_item=args.configuration_item,
            assignment_group=args.assignment_group,
        ),
    )
    result = orchestrator.run()
    if args.output_format == "json":
        import json

        print(json.dumps(result, indent=2, default=str))
        return

    print(format_markdown_report(result))


if __name__ == "__main__":
    main()
