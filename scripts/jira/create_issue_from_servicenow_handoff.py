#!/usr/bin/env python3
"""
Jira issue creation from a ServiceNow INC→PRB strict handoff.

Creates a Jira issue linked to a ServiceNow incident and problem record,
applying DDL project field mappings (Banner, Team, ServiceNow Priority,
ServiceNow #) and establishing a parent relationship.

Idempotent: re-running with the same incident/problem numbers will reuse an
existing issue created within the last 30 minutes rather than creating a
duplicate.

Usage examples
--------------
# Dry-run: validate fields and show what would be created, no writes.
python create_issue_from_servicenow_handoff.py \\
    --incident-number INC0094423 \\
    --incident-priority "3 - Moderate (P3)" \\
    --problem-number PRB0040546 \\
    --incident-summary "HIGH Vulnerability found CVE-2016-7051" \\
    --incident-description "https://onenr.io/… details" \\
    --parent-jira-ticket DDL-28477 \\
    --dry-run

# Execute:
python create_issue_from_servicenow_handoff.py \\
    --incident-number INC0094423 \\
    --incident-priority "3 - Moderate (P3)" \\
    --problem-number PRB0040546 \\
    --incident-summary "HIGH Vulnerability found CVE-2016-7051" \\
    --incident-description "https://onenr.io/… details" \\
    --parent-jira-ticket DDL-28477
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from bootstrap_shared import bootstrap_paths

JIRA_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "jira-issue-operations"
bootstrap_paths(skill_paths=[JIRA_SKILL_PATH], override_env=True)

from jira_client import JiraAPIError, JiraClient, JiraValidationError

# ---------------------------------------------------------------------------
# Organisation-level constants (stable across all DDL handoffs)
# ---------------------------------------------------------------------------
BANNER_VALUE = "CanadianTire"
TEAM_NAME = "Site Reliability Engineering"
TEAM_UUID = "472b84df-0340-44a7-91ee-fc748691daa7"
DDL_LABELS = ["L2toL3", "ODP", "SRE"]
DDL_PRIORITY = "Major"

INC_PATTERN = re.compile(r"^INC\d+$", re.IGNORECASE)
PRB_PATTERN = re.compile(r"^PRB\d{7}$", re.IGNORECASE)
JIRA_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Jira issue from a ServiceNow INC→PRB strict handoff.",
    )
    parser.add_argument("--incident-number", required=True, help="e.g. INC0094423")
    parser.add_argument(
        "--incident-priority",
        required=True,
        help='ServiceNow priority string, e.g. "3 - Moderate (P3)"',
    )
    parser.add_argument("--problem-number", required=True, help="e.g. PRB0040546")
    parser.add_argument("--incident-summary", required=True, help="Short description of the incident")
    parser.add_argument("--incident-description", default="", help="Full incident description or URL")
    parser.add_argument(
        "--routing-project",
        default="DDL",
        help="Jira project key to route the issue to (default: DDL)",
    )
    parser.add_argument(
        "--required-issue-type",
        default="Problem",
        help="Jira issue type to create (default: Problem)",
    )
    parser.add_argument("--parent-jira-ticket", default=None, help="Parent Jira issue key, e.g. DDL-28477")
    parser.add_argument(
        "--issue-type-override",
        default=None,
        help="Override issue type (requires --issue-type-override-approved)",
    )
    parser.add_argument(
        "--issue-type-override-approved",
        action="store_true",
        help="Confirm the issue type override is intentional",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate fields and show resolved metadata; do not create the issue",
    )

    args = parser.parse_args(argv)

    if not INC_PATTERN.fullmatch(args.incident_number.strip()):
        parser.error("--incident-number must start with INC followed by digits.")
    if not PRB_PATTERN.fullmatch(args.problem_number.strip()):
        parser.error("--problem-number must match PRB followed by 7 digits.")
    if args.parent_jira_ticket and not JIRA_KEY_PATTERN.fullmatch(args.parent_jira_ticket.strip()):
        parser.error("--parent-jira-ticket must be a valid Jira issue key, e.g. DDL-28477.")
    if args.issue_type_override and not args.issue_type_override_approved:
        parser.error("--issue-type-override requires --issue-type-override-approved.")

    return args


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fail_payload(reason: str, *, routing_project: str, required_issue_type: str, parent_jira_ticket: Optional[str]) -> Dict[str, Any]:
    return {
        "issue_key": None,
        "issue_url": None,
        "creation_action": None,
        "project": routing_project,
        "issue_type_requested": required_issue_type,
        "issue_type_created": None,
        "issue_type_verified": False,
        "parent_requested": parent_jira_ticket,
        "parent_link_applied": False,
        "parent_link_mode": "not_supported",
        "labels_after": [],
        "field_mapping_applied": [],
        "status": "failed",
        "failure_reason": reason,
    }


def normalize_priority_to_short(value: str) -> str:
    text = (value or "").strip().lower()
    for label in ("p1", "p2", "p3", "p4", "p5"):
        if label in text:
            return label.upper()
    return (value or "").strip()


def resolve_fields_by_name(
    client: JiraClient,
    names: List[str],
    *,
    required: bool = True,
) -> Dict[str, str]:
    payload = client._request("GET", "/rest/api/3/field")
    if not isinstance(payload, list):
        raise JiraValidationError("Unexpected /field response shape.")
    wanted = {n.lower(): n for n in names}
    resolved: Dict[str, str] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        field_id = str(item.get("id") or "").strip()
        if name.lower() in wanted and field_id:
            resolved[wanted[name.lower()]] = field_id
    missing = [n for n in names if n not in resolved]
    if required and missing:
        raise JiraValidationError("Required Jira fields missing for strict route: " + ", ".join(missing))
    return resolved


def extract_option_id(allowed_values: Any, target_name: str) -> Optional[str]:
    if not isinstance(allowed_values, list):
        return None
    target = target_name.strip().lower()
    for entry in allowed_values:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("value") or entry.get("name") or "").strip()
        opt_id = str(entry.get("id") or "").strip()
        if name.lower() == target and opt_id:
            return opt_id
    return None


def to_adf(text: str) -> Dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def make_summary(incident_number: str, problem_number: str, incident_summary: str) -> str:
    return f"[{incident_number}/{problem_number}] {incident_summary}"


def make_description(
    incident_number: str,
    problem_number: str,
    incident_priority: str,
    incident_summary: str,
    incident_description: str,
) -> str:
    lines = [
        "ServiceNow strict handoff context:",
        f"- Incident: {incident_number}",
        f"- Problem: {problem_number}",
        f"- Incident Priority: {incident_priority}",
        f"- Incident Summary: {incident_summary}",
        f"- Incident Description: {incident_description}",
        "",
        "Remediation ownership: DDL SRE to triage and drive vulnerability remediation to closure.",
    ]
    return "\n".join(lines)


def verify_issue_type(issue: Dict[str, Any], expected: str) -> Tuple[Optional[str], bool]:
    fields = issue.get("fields", {}) if isinstance(issue, dict) else {}
    issuetype = fields.get("issuetype", {}) if isinstance(fields, dict) else {}
    created = str(issuetype.get("name") or "").strip() or None
    ok = bool(created and created.lower() == expected.strip().lower())
    return created, ok


def apply_parent_linkage(
    client: JiraClient,
    issue_key: str,
    parent_key: str,
    field_name_to_id: Dict[str, str],
) -> Tuple[bool, str, Optional[str]]:
    # Mode 1: native parent field.
    try:
        client.update_issue(issue_key, fields={"parent": {"key": parent_key}})
        return True, "parent_field", None
    except Exception:
        pass

    # Mode 2: Parent Link custom field when present in this project.
    parent_link_field_id = next(
        (fid for name, fid in field_name_to_id.items() if name.strip().lower() == "parent link"),
        None,
    )
    if parent_link_field_id:
        try:
            client.update_issue(issue_key, fields={parent_link_field_id: parent_key})
            return True, "parent_link", None
        except Exception:
            pass

    # Mode 3: generic issue link fallback.
    try:
        client.link_issues(
            inward_issue_key=issue_key,
            outward_issue_key=parent_key,
            link_type="Relates",
            comment=f"Strict handoff linkage fallback: associated with requested parent ticket {parent_key}.",
        )
        return True, "issue_link", None
    except Exception as exc:
        return False, "not_supported", str(exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    incident_number = args.incident_number.strip().upper()
    problem_number = args.problem_number.strip().upper()
    routing_project = args.routing_project.strip().upper()
    required_issue_type = (args.issue_type_override or args.required_issue_type).strip()
    parent_jira_ticket = args.parent_jira_ticket.strip() if args.parent_jira_ticket else None

    def _fail(reason: str) -> None:
        print(json.dumps(
            fail_payload(reason, routing_project=routing_project, required_issue_type=required_issue_type, parent_jira_ticket=parent_jira_ticket),
            ensure_ascii=True,
        ))

    try:
        client = JiraClient.from_env()
        client.ensure_issue_type_available(project_key=routing_project, issue_type=required_issue_type)

        base_required = ["Banner", "Team", "ServiceNow Priority", "ServiceNow #"]
        field_name_to_id = resolve_fields_by_name(client, base_required, required=True)
        field_name_to_id.update(resolve_fields_by_name(client, ["Parent Link"], required=False))

        banner_field = field_name_to_id["Banner"]
        team_field = field_name_to_id["Team"]
        sn_priority_field = field_name_to_id["ServiceNow Priority"]
        sn_number_field = field_name_to_id["ServiceNow #"]

        editmeta = client.get_create_meta(project_key=routing_project, issue_type=required_issue_type)
        fields_meta = editmeta.get("fields", {}) if isinstance(editmeta, dict) else {}
        if not isinstance(fields_meta, dict):
            return _fail("Unable to read createmeta fields for strict mapping.")

        banner_meta = fields_meta.get(banner_field) if isinstance(fields_meta.get(banner_field), dict) else {}
        sn_priority_meta = fields_meta.get(sn_priority_field) if isinstance(fields_meta.get(sn_priority_field), dict) else {}

        banner_option_id = extract_option_id(banner_meta.get("allowedValues"), BANNER_VALUE)
        if not banner_option_id:
            return _fail(f"Strict mapping failed: Banner option '{BANNER_VALUE}' not available.")

        sn_priority_short = normalize_priority_to_short(args.incident_priority)
        sn_priority_option_id = extract_option_id(sn_priority_meta.get("allowedValues"), sn_priority_short)
        if not sn_priority_option_id:
            return _fail(f"Strict mapping failed: ServiceNow Priority option '{sn_priority_short}' not available.")

        summary = make_summary(incident_number, problem_number, args.incident_summary)
        description = make_description(
            incident_number, problem_number, args.incident_priority,
            args.incident_summary, args.incident_description,
        )
        extra_fields = {
            banner_field: [{"id": banner_option_id}],
            sn_priority_field: {"id": sn_priority_option_id},
            sn_number_field: [problem_number, incident_number],
        }

        if args.dry_run:
            print(json.dumps({
                "dry_run": True,
                "project": routing_project,
                "issue_type": required_issue_type,
                "summary": summary,
                "priority": DDL_PRIORITY,
                "labels": DDL_LABELS,
                "banner_option_id": banner_option_id,
                "sn_priority_short": sn_priority_short,
                "sn_priority_option_id": sn_priority_option_id,
                "parent_jira_ticket": parent_jira_ticket,
                "extra_fields_keys": list(extra_fields.keys()),
            }, indent=2, ensure_ascii=True))
            return

        created, creation_action = client.idempotent_create_issue(
            project_key=routing_project,
            issue_type=required_issue_type,
            summary=summary,
            description=to_adf(description),
            priority=DDL_PRIORITY,
            labels=DDL_LABELS,
            extra_fields=extra_fields,
            verify_issue_type_available=False,  # already verified above
            recovery_window_minutes=30,
        )

        issue_key = str(created.get("key") or "").strip()
        if not issue_key:
            return _fail("Issue creation did not return issue key.")

        field_mapping_applied = [
            f"labels={','.join(DDL_LABELS)}",
            f"priority={DDL_PRIORITY}",
            f"Banner={BANNER_VALUE}",
            f"ServiceNow Priority={sn_priority_short}",
            f"ServiceNow #={problem_number},{incident_number}",
        ]

        team_verified = False
        try:
            team_result = client.set_issue_team(issue_key=issue_key, team_id=TEAM_UUID, verify=True)
            if team_result.get("team_id") == TEAM_UUID and team_result.get("team_name"):
                team_verified = True
                field_mapping_applied.append(f"Team={TEAM_NAME}")
        except Exception:
            pass

        parent_applied, parent_mode, parent_failure = (False, "not_supported", None)
        if parent_jira_ticket:
            parent_applied, parent_mode, parent_failure = apply_parent_linkage(
                client=client,
                issue_key=issue_key,
                parent_key=parent_jira_ticket,
                field_name_to_id=field_name_to_id,
            )

        verify_fields = ["issuetype", "labels", "priority", banner_field, sn_priority_field, sn_number_field, team_field]
        final_issue = client.get_issue(issue_key, fields=verify_fields)
        issue_type_created, issue_type_verified = verify_issue_type(final_issue, required_issue_type)

        labels_after: List[str] = []
        final_fields = final_issue.get("fields", {}) if isinstance(final_issue, dict) else {}
        if isinstance(final_fields, dict):
            raw_labels = final_fields.get("labels")
            if isinstance(raw_labels, list):
                labels_after = [str(item) for item in raw_labels]

        status = "success"
        failure_reason = None
        if not issue_type_verified:
            status = "failed"
            failure_reason = f"Issue type verification failed: expected {required_issue_type}, got {issue_type_created or 'N/A'}."
        elif not team_verified:
            status = "partial_success"
            failure_reason = "Team mapping could not be fully verified (id + name/title)."
        elif parent_jira_ticket and not parent_applied:
            status = "partial_success"
            failure_reason = f"Parent linkage could not be applied: {parent_failure or 'unsupported'}"

        print(json.dumps({
            "issue_key": issue_key,
            "issue_url": f"{client.config.host}/browse/{issue_key}",
            "creation_action": creation_action,
            "project": routing_project,
            "issue_type_requested": required_issue_type,
            "issue_type_created": issue_type_created,
            "issue_type_verified": issue_type_verified,
            "parent_requested": parent_jira_ticket,
            "parent_link_applied": bool(parent_applied),
            "parent_link_mode": parent_mode,
            "labels_after": labels_after,
            "field_mapping_applied": field_mapping_applied,
            "status": status,
            "failure_reason": failure_reason,
        }, ensure_ascii=True))

    except (JiraValidationError, JiraAPIError) as exc:
        _fail(str(exc))
    except Exception as exc:
        _fail(f"Unexpected error: {exc}")


if __name__ == "__main__":
    main()
