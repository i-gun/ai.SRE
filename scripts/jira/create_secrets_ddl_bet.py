#!/usr/bin/env python3
"""Create the Secrets DDL Problem and its BET Task counterpart."""

from __future__ import annotations

import argparse
from datetime import date
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from bootstrap_shared import bootstrap_paths
from jira.adf_common import text_to_adf

JIRA_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "jira-issue-operations"
SERVICENOW_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-incident-operations"
CONFLUENCE_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "confluence-knowledge-operations"
CONFLUENCE_AUTH_PATH = PROJECT_ROOT / ".github" / "skills" / "confluence-authentication"
bootstrap_paths(
    skill_paths=[JIRA_SKILL_PATH, SERVICENOW_SKILL_PATH, CONFLUENCE_SKILL_PATH, CONFLUENCE_AUTH_PATH],
    override_env=True,
)

from jira_client import JiraAPIError, JiraClient, JiraValidationError  # type: ignore[reportMissingImports]
from servicenow_client import ServiceNowClient  # type: ignore[reportMissingImports]

DDL_LABELS = ["L2toL3", "ODP", "SRE", "AzureKV"]
DDL_BANNER = ["CanadianTire", "SportChek"]
DDL_ROOT_CAUSE = "Lifecycle Management"
DDL_PRIORITY = "Major"
DDL_COMPONENT = "Azure"
DDL_TEAM = "Site Reliability Engineering"
BET_TEAM = "[Daas] Operational Squad"
BET_LABELS = ["DaaS"]
RELEASE_CALENDAR_PAGE_ID = "80217385"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident-number", required=True)
    parser.add_argument("--problem-number", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--idempotency-days", type=int, default=30,
                        help="Reuse matching Jira issues created within this many days")
    parser.add_argument("--current-release", default=None,
                        help="Override the Confluence-derived affected version")
    parser.add_argument("--upcoming-release", default=None,
                        help="Override the Confluence-derived fix version")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def resolve_fields(client: JiraClient, names: List[str]) -> Dict[str, str]:
    fields = client._request("GET", "/rest/api/3/field")
    if not isinstance(fields, list):
        raise JiraValidationError("Unexpected Jira field metadata response")
    wanted = {name.lower(): name for name in names}
    resolved: Dict[str, str] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip().lower()
        field_id = str(field.get("id") or "").strip()
        if name in wanted and field_id:
            resolved[wanted[name]] = field_id
    missing = [name for name in names if name not in resolved]
    if missing:
        raise JiraValidationError("Missing Jira fields: " + ", ".join(missing))
    return resolved


def option_id(meta: Dict[str, Any], value: str) -> str:
    for item in meta.get("allowedValues") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("value") or item.get("name") or "").strip()
        identifier = str(item.get("id") or "").strip()
        if name.lower() == value.lower() and identifier:
            return identifier
    raise JiraValidationError(f"Jira option '{value}' is not available")


def select_value(meta: Dict[str, Any], identifier: str) -> Any:
    schema = meta.get("schema") or {}
    if str(schema.get("type") or "").lower() == "array":
        return [{"id": identifier}]
    return {"id": identifier}


def multi_select_values(meta: Dict[str, Any], identifiers: List[str]) -> Any:
    schema = meta.get("schema") or {}
    if str(schema.get("type") or "").lower() == "array":
        return [{"id": identifier} for identifier in identifiers]
    return {"id": identifiers[0]}


def component_payload(client: JiraClient, *, project: str, issue_type: str) -> Dict[str, str]:
    metadata = client.get_create_meta(project_key=project, issue_type=issue_type).get("fields", {})
    component_meta = metadata.get("components", {})
    allowed_values = component_meta.get("allowedValues") or []
    for item in allowed_values:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("value") or "").strip()
        identifier = str(item.get("id") or "").strip()
        if name.lower() == DDL_COMPONENT.lower() and identifier:
            return {"id": identifier}

    components = client._request("GET", f"/rest/api/3/project/{project}/components")
    if isinstance(components, list):
        azure_options = []
        for item in components:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            identifier = str(item.get("id") or "").strip()
            if identifier and name.lower() == DDL_COMPONENT.lower():
                return {"id": identifier}
            if identifier and name.lower().startswith("azure"):
                azure_options.append((name, identifier))
        if azure_options:
            # BET exposes "Azure Cloud" as its selectable Azure component.
            return {"id": azure_options[0][1]}

    # Some Jira projects omit component allowedValues from create metadata;
    # retain the normal name payload in that case.
    return {"name": DDL_COMPONENT}


def resolve_release_versions() -> Dict[str, Any]:
    """Resolve current/upcoming release values from the authoritative calendar."""
    confluence_path = PROJECT_ROOT / ".github" / "skills" / "confluence-knowledge-operations"
    if str(confluence_path) not in sys.path:
        sys.path.insert(0, str(confluence_path))
    confluence_auth_path = PROJECT_ROOT / ".github" / "skills" / "confluence-authentication"
    if str(confluence_auth_path) not in sys.path:
        sys.path.insert(0, str(confluence_auth_path))
    from confluence_client import ConfluenceClient  # type: ignore[import-not-found]

    page = ConfluenceClient.from_env().get_page(page_id=RELEASE_CALENDAR_PAGE_ID)
    body = ((page.get("body") or {}).get("storage") or {}).get("value") or ""
    rows = []
    for row_html in re.findall(r"<tr\b.*?</tr>", body, flags=re.IGNORECASE | re.DOTALL):
        dates = re.findall(r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})"', row_html, flags=re.IGNORECASE)
        versions = re.findall(r"\b(?:RC-)?\d{2,4}\.\d{2}\b", row_html, flags=re.IGNORECASE)
        if not dates or not versions:
            continue
        try:
            release_date = date.fromisoformat(dates[-1])
        except ValueError:
            continue
        version = versions[0].upper()
        if not version.startswith("RC-"):
            version = f"RC-{version}"
        rows.append((release_date, version))
    if not rows:
        raise JiraValidationError("No release versions found on the Digital Release Calendar")
    today = date.today()
    past = sorted((row for row in rows if row[0] <= today), reverse=True)
    future = sorted(row for row in rows if row[0] > today)
    if not past or not future:
        raise JiraValidationError("Release Calendar did not provide both current and upcoming versions")
    return {
        "current": past[0][1],
        "upcoming": future[0][1],
        "source_page_id": RELEASE_CALENDAR_PAGE_ID,
    }


def resolve_fields_by_name(client: JiraClient, names: List[str]) -> Dict[str, str]:
    fields = client._request("GET", "/rest/api/3/field")
    wanted = {name.lower(): name for name in names}
    return {
        wanted[str(item.get("name") or "").strip().lower()]: str(item.get("id"))
        for item in fields if isinstance(item, dict)
        and str(item.get("name") or "").strip().lower() in wanted
        and item.get("id")
    }


def version_fields(client: JiraClient, project: str, issue_type: str, current: str, upcoming: str) -> Dict[str, Any]:
    field_ids = resolve_fields_by_name(client, ["Affected version"])
    metadata = client.get_create_meta(project_key=project, issue_type=issue_type).get("fields", {})
    result: Dict[str, Any] = {"fixVersions": [{"name": upcoming}]}
    affected_id = field_ids.get("Affected version")
    if affected_id:
        result[affected_id] = [{"name": current}]
    return result


def find_existing(client: JiraClient, *, project: str, issue_type: str, summary: str, days: int) -> Optional[Dict[str, Any]]:
    if days <= 0:
        raise JiraValidationError("idempotency-days must be greater than zero")
    escaped = summary.replace("\\", "\\\\").replace('"', '\\"')
    issues = client.search_issues(
        jql=(f'project = "{project}" AND issuetype = "{issue_type}" '
             f'AND summary = "{escaped}" AND created >= "-{days}d" ORDER BY created DESC'),
        limit=20,
        fields=["summary", "issuetype", "created", "key"],
    )
    return issues[0] if issues else None


def build_fields(client: JiraClient, current_release: str, upcoming_release: str) -> Dict[str, Any]:
    field_ids = resolve_fields(client, ["Banner", "Root cause", "Team", "ServiceNow Priority"])
    metadata = client.get_create_meta(project_key="DDL", issue_type="Problem").get("fields", {})
    banner_meta = metadata.get(field_ids["Banner"], {})
    root_cause_meta = metadata.get(field_ids["Root cause"], {})
    sn_priority_meta = metadata.get(field_ids["ServiceNow Priority"], {})
    banner_ids = [option_id(banner_meta, value) for value in DDL_BANNER]
    return {
        field_ids["Banner"]: multi_select_values(banner_meta, banner_ids),
        field_ids["Root cause"]: select_value(root_cause_meta, option_id(root_cause_meta, DDL_ROOT_CAUSE)),
        field_ids["ServiceNow Priority"]: select_value(sn_priority_meta, option_id(sn_priority_meta, "P3")),
        "components": [component_payload(client, project="DDL", issue_type="Problem")],
        "labels": DDL_LABELS,
        "priority": {"name": DDL_PRIORITY},
        **version_fields(client, "DDL", "Problem", current_release, upcoming_release),
    }


def create_or_reuse(client: JiraClient, args: argparse.Namespace) -> Dict[str, Any]:
    releases = resolve_release_versions()
    current_release = args.current_release or releases["current"]
    upcoming_release = args.upcoming_release or releases["upcoming"]
    extra_fields = build_fields(client, current_release, upcoming_release)
    bet_component = component_payload(client, project="BET", issue_type="Task")
    bet_versions = version_fields(client, "BET", "Task", current_release, upcoming_release)
    if args.dry_run:
        return {
            "dry_run": True,
            "ddl": {
                "project": "DDL",
                "issue_type": "Problem",
                "summary": args.summary,
                "labels": DDL_LABELS,
                "banner": DDL_BANNER,
                "root_cause": DDL_ROOT_CAUSE,
                "priority": DDL_PRIORITY,
                "service_now_priority": "P3",
                "affected_version": current_release,
                "fix_version": upcoming_release,
                "components": [DDL_COMPONENT],
                "component_payload": extra_fields["components"],
                "team": DDL_TEAM,
            },
            "bet": {
                "project": "BET",
                "issue_type": "Task",
                "summary": args.summary,
                "labels": BET_LABELS,
                "components": [DDL_COMPONENT],
                "component_payload": [bet_component],
                "affected_version": current_release,
                "fix_version": upcoming_release,
                "team": BET_TEAM,
            },
        }

    ddl = find_existing(client, project="DDL", issue_type="Problem", summary=args.summary, days=args.idempotency_days)
    ddl_action = "reused_existing" if ddl else "created"
    if not ddl:
        ddl = client.create_issue(
            project_key="DDL", issue_type="Problem", summary=args.summary,
            description=text_to_adf(args.description), priority=DDL_PRIORITY,
            labels=DDL_LABELS, extra_fields=extra_fields,
            verify_issue_type_available=True,
        )
    ddl_key = str(ddl.get("key") or "").strip()
    if not ddl_key:
        raise JiraValidationError("DDL creation did not return an issue key")
    client.update_issue(ddl_key, fields=extra_fields)
    ddl_team = client.set_issue_team(issue_key=ddl_key, team_name=DDL_TEAM, project_key="DDL", verify=True)
    servicenow_client = ServiceNowClient.from_env()
    incident = servicenow_client._find_incident(incident_number=args.incident_number, sys_id=None)  # pylint: disable=protected-access
    if servicenow_client.is_resolved_state(incident.get("state")):
        updated_incident = incident
    else:
        updated_incident = servicenow_client.update_incident_fields(
            incident_number=args.incident_number,
            fields={"u_vendor_ticket": ddl_key},
            require_active=True,
            forbid_resolved=True,
        )

    bet = find_existing(client, project="BET", issue_type="Task", summary=args.summary, days=args.idempotency_days)
    bet_action = "reused_existing" if bet else "created"
    if not bet:
        bet = client.create_issue(
            project_key="BET", issue_type="Task", summary=args.summary,
            description=text_to_adf(args.description), labels=BET_LABELS,
            extra_fields={"components": [bet_component], **bet_versions},
            verify_issue_type_available=True,
        )
    bet_key = str(bet.get("key") or "").strip()
    if not bet_key:
        raise JiraValidationError("BET creation did not return an issue key")
    client.update_issue(
        bet_key,
        fields={
            "labels": BET_LABELS,
            "components": [bet_component],
            "priority": {"name": DDL_PRIORITY},
            **bet_versions,
        },
    )
    bet_team = client.set_issue_team(issue_key=bet_key, team_name=BET_TEAM, project_key="BET", verify=True)
    client.link_issues(inward_issue_key=ddl_key, outward_issue_key=bet_key, link_type="Relates")
    if servicenow_client.is_resolved_state(incident.get("state")):
        resolved_incident = incident
    else:
        resolved_incident = servicenow_client.resolve_incident_with_updates(
            incident_number=args.incident_number,
            close_code="Fixed",
            close_notes=(
                "Secret rotation task has been assigned to Operational Squad. "
                f"{bet_key} is for tracking."
            ),
            vendor_ticket=ddl_key,
            work_note=f"Resolved after Jira DDL/BET chain verification; tracking task: {bet_key}.",
        )

    return {
        "ddl_key": ddl_key,
        "ddl_action": ddl_action,
        "ddl_team": ddl_team,
        "service_now_incident": updated_incident.get("number") or args.incident_number,
        "vendor_ticket": ddl_key,
        "bet_key": bet_key,
        "bet_action": bet_action,
        "bet_team": bet_team,
        "linked": True,
        "resolved_incident": resolved_incident.get("number") or args.incident_number,
        "resolution_code": "Fixed",
        "resolution_notes": f"Secret rotation task has been assigned to Operational Squad. {bet_key} is for tracking.",
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        client = JiraClient.from_env()
        result = create_or_reuse(client, args)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except (JiraAPIError, JiraValidationError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
