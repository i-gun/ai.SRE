#!/usr/bin/env python3
"""Orchestrate New Relic alert acknowledgment with ServiceNow incident handling."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEWRELIC_ALERT_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "newrelic-alert-operations"
SERVICENOW_INCIDENT_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-incident-operations"
ASSIGNMENT_PROMPT_PATH = PROJECT_ROOT / ".github" / "prompts" / "servicenow-assign-unassigned-incidents.prompt.md"


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
    if env_path.exists():
        load_dotenv(env_path)

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


def _markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


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
        "| New Relic alert title | Acknowledgement status | ServiceNow incident | Assignee |",
        "| --- | --- | --- | --- |",
    ]
    for item in report:
        lines.append(
            "| "
            f"{_markdown_cell(item.get('newrelic_alert_title'))} | "
            f"{_markdown_cell(item.get('acknowledgement_status'))} | "
            f"{_markdown_cell(item.get('servicenow_incident_number'))} | "
            f"{_markdown_cell(item.get('servicenow_assignee'))} |"
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

                incident_number, assignee, incident_action = self._handle_incident_for_alert(
                    alert_title=title,
                    alert_url=str(alert.get("issueLink") or "").strip(),
                )

                if incident_action == "created_new":
                    raised_new_count += 1
                elif incident_action in {"existing_assigned", "existing_unassigned_assigned"}:
                    existing_incident_count += 1

                per_alert_report.append(
                    {
                        "newrelic_alert_title": title,
                        "acknowledgement_status": str(ack_result.get("status") or ""),
                        "servicenow_incident_number": incident_number,
                        "servicenow_assignee": assignee,
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

    def _handle_incident_for_alert(self, *, alert_title: str, alert_url: str) -> Tuple[str, str, str]:
        existing = self._find_active_incident_by_alert_title(alert_title)
        if existing:
            current_assignee = _extract_reference_value(existing.get("assigned_to"))
            incident_number = _extract_reference_value(existing.get("number"))
            if current_assignee:
                return incident_number, current_assignee, "existing_assigned"

            updated = self._assign_unassigned_incident(existing)
            return (
                _extract_reference_value(updated.get("number")) or incident_number,
                _extract_reference_value(updated.get("assigned_to")) or self.config.servicenow_user,
                "existing_unassigned_assigned",
            )

        created = self._create_new_incident(alert_title=alert_title, alert_url=alert_url)
        return (
            _extract_reference_value(created.get("number")),
            _extract_reference_value(created.get("assigned_to")) or self.config.servicenow_user,
            "created_new",
        )

    def _build_designated_group_clause(self) -> str:
        groups = getattr(self.servicenow_client.config, "assignment_groups", [])
        return "assignment_group.nameIN" + ",".join(groups)

    def _find_active_incident_by_alert_title(self, alert_title: str) -> Optional[Dict[str, Any]]:
        query_title = _escape_query_value(alert_title)
        query = "^".join(
            [
                self._build_designated_group_clause(),
                "active=true",
                f"short_descriptionLIKE{query_title}",
            ]
        )
        response = self.servicenow_client._request(
            "GET",
            self.servicenow_client.INCIDENT_TABLE_PATH,
            params={
                "sysparm_query": query,
                "sysparm_limit": 1,
                "sysparm_order_by_desc": "sys_updated_on",
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )
        incidents = response.get("result", [])
        return incidents[0] if incidents else None

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

        payload = {
            "caller_id": self.config.caller_id,
            "contact_type": self.config.contact,
            "channel": self.config.channel,
            "category": self.config.category,
            "subcategory": self.config.subcategory,
            "service_offering": self.config.service_offering,
            "cmdb_ci": self.config.configuration_item,
            "assignment_group": self.config.assignment_group,
            "assigned_to": self.config.servicenow_user,
            "short_description": alert_title,
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
