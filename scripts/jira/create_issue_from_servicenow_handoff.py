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
BANNER_DEFAULT_VALUES = ["CanadianTire", "SportChek"]
TEAM_NAME = "Site Reliability Engineering"
TEAM_UUID = "472b84df-0340-44a7-91ee-fc748691daa7"
DDL_LABELS = ["L2toL3", "ODP", "SRE"]
DDL_PRIORITY = "Major"

INC_PATTERN = re.compile(r"^INC\d+$", re.IGNORECASE)
PRB_PATTERN = re.compile(r"^PRB\d{7}$", re.IGNORECASE)
JIRA_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


def normalize_kind(kind: str) -> str:
    value = (kind or "").strip()
    if not value:
        return ""
    up = value.upper()
    if up in {"SFSC", "SFSC-LIKE", "SFSC LIKE"}:
        return "SFSC"
    if up in {"DTE, INVENTORY", "DTE/INVENTORY", "DTE INVENTORY"}:
        return "DTE, Inventory"
    if up == "SEARCH":
        return "Search"
    if up == "CDS":
        return "CDS"
    if up == "PPE":
        return "PPE"
    return value


def infer_kind_from_summary(summary: str) -> str:
    match = re.match(r"^\s*\[([^\]]+)\]", summary or "")
    if not match:
        return ""
    return normalize_kind(match.group(1))


def kind_labels(kind: str) -> List[str]:
    normalized = normalize_kind(kind)
    if normalized == "DTE, Inventory":
        return ["DTE", "Inventory"]
    if normalized:
        return [normalized]
    return []


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
    parser.add_argument("--kind", default=None, help="Service group kind, e.g. CDS, SFSC, DTE, Inventory")
    parser.add_argument("--current-release", default=None, help="Current release version for affected version field")
    parser.add_argument("--upcoming-release", default=None, help="Upcoming release version for fix versions field")
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


def build_select_payload(field_meta: Dict[str, Any], option_id: str) -> Any:
    schema = field_meta.get("schema") if isinstance(field_meta, dict) else {}
    schema_type = str((schema or {}).get("type") or "").lower() if isinstance(schema, dict) else ""
    if schema_type == "array":
        return [{"id": option_id}]
    return {"id": option_id}


def build_multi_select_payload(field_meta: Dict[str, Any], option_ids: List[str]) -> Any:
    schema = field_meta.get("schema") if isinstance(field_meta, dict) else {}
    schema_type = str((schema or {}).get("type") or "").lower() if isinstance(schema, dict) else ""
    if schema_type == "array":
        return [{"id": oid} for oid in option_ids]
    return {"id": option_ids[0]} if option_ids else {}


def to_adf(text: str) -> Dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def make_summary(incident_summary: str) -> str:
    return (incident_summary or "").strip()


def make_description(incident_description: str) -> str:
    return (incident_description or "").strip()


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
        field_name_to_id.update(resolve_fields_by_name(client, ["Parent Link", "Root cause", "Affected version"], required=False))

        banner_field = field_name_to_id["Banner"]
        team_field = field_name_to_id["Team"]
        sn_priority_field = field_name_to_id["ServiceNow Priority"]
        sn_number_field = field_name_to_id["ServiceNow #"]
        root_cause_field = field_name_to_id.get("Root cause")
        affected_version_field = field_name_to_id.get("Affected version")

        editmeta = client.get_create_meta(project_key=routing_project, issue_type=required_issue_type)
        fields_meta = editmeta.get("fields", {}) if isinstance(editmeta, dict) else {}
        if not isinstance(fields_meta, dict):
            return _fail("Unable to read createmeta fields for strict mapping.")

        banner_meta = fields_meta.get(banner_field) if isinstance(fields_meta.get(banner_field), dict) else {}
        sn_priority_meta = fields_meta.get(sn_priority_field) if isinstance(fields_meta.get(sn_priority_field), dict) else {}
        components_meta = fields_meta.get("components") if isinstance(fields_meta.get("components"), dict) else {}
        fix_versions_meta = fields_meta.get("fixVersions") if isinstance(fields_meta.get("fixVersions"), dict) else {}
        root_cause_meta = fields_meta.get(root_cause_field) if root_cause_field and isinstance(fields_meta.get(root_cause_field), dict) else {}
        affected_version_meta = fields_meta.get(affected_version_field) if affected_version_field and isinstance(fields_meta.get(affected_version_field), dict) else {}

        banner_options: List[Dict[str, str]] = []
        for candidate in BANNER_DEFAULT_VALUES:
            option_id = extract_option_id(banner_meta.get("allowedValues"), candidate)
            if option_id:
                banner_options.append({"name": candidate, "id": option_id})

        if not banner_options:
            return _fail(
                "Strict mapping failed: Banner option not available. "
                f"Tried: {', '.join(BANNER_DEFAULT_VALUES)}"
            )

        banner_option_ids = [item["id"] for item in banner_options]
        banner_selected_names = [item["name"] for item in banner_options]
        banner_is_array = str(((banner_meta.get("schema") or {}).get("type") or "")).lower() == "array"
        banner_manual_followup = None
        if len(banner_option_ids) > 1 and not banner_is_array:
            banner_manual_followup = (
                "Banner field is single-select on this project; applied first available default and "
                "requires manual live check to ensure both CanadianTire and SportChek intent is addressed."
            )

        sn_priority_short = normalize_priority_to_short(args.incident_priority)
        sn_priority_option_id = extract_option_id(sn_priority_meta.get("allowedValues"), sn_priority_short)
        if not sn_priority_option_id:
            return _fail(f"Strict mapping failed: ServiceNow Priority option '{sn_priority_short}' not available.")

        kind = normalize_kind(args.kind or infer_kind_from_summary(args.incident_summary))
        labels = sorted(set(DDL_LABELS + kind_labels(kind)))

        components_payload: List[Dict[str, str]] = []
        if kind_labels(kind):
            components_payload = [{"name": comp} for comp in kind_labels(kind)]

        root_cause_option_id = None
        if root_cause_field and root_cause_meta:
            root_cause_option_id = extract_option_id(root_cause_meta.get("allowedValues"), "Code")

        summary = make_summary(args.incident_summary)
        description = make_description(args.incident_description)
        extra_fields = {
            banner_field: build_multi_select_payload(banner_meta, banner_option_ids),
            sn_priority_field: {"id": sn_priority_option_id},
            sn_number_field: [problem_number, incident_number],
        }
        if components_payload:
            extra_fields["components"] = components_payload
        if args.upcoming_release:
            extra_fields["fixVersions"] = [{"name": args.upcoming_release.strip()}]
        if affected_version_field and args.current_release:
            extra_fields[affected_version_field] = [{"name": args.current_release.strip()}]
        if root_cause_field and root_cause_option_id:
            extra_fields[root_cause_field] = build_select_payload(root_cause_meta, root_cause_option_id)

        if args.dry_run:
            print(json.dumps({
                "dry_run": True,
                "project": routing_project,
                "issue_type": required_issue_type,
                "summary": summary,
                "kind": kind,
                "priority": DDL_PRIORITY,
                "labels": labels,
                "components": components_payload,
                "banner_selected": banner_selected_names,
                "banner_option_ids": banner_option_ids,
                "banner_field_is_multi_select": banner_is_array,
                "banner_manual_followup": banner_manual_followup,
                "sn_priority_short": sn_priority_short,
                "sn_priority_option_id": sn_priority_option_id,
                "root_cause_option_id": root_cause_option_id,
                "current_release": args.current_release,
                "upcoming_release": args.upcoming_release,
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
            labels=labels,
            extra_fields=extra_fields,
            verify_issue_type_available=False,  # already verified above
            recovery_window_minutes=30,
        )

        issue_key = str(created.get("key") or "").strip()
        if not issue_key:
            return _fail("Issue creation did not return issue key.")

        field_mapping_applied = [
            f"labels={','.join(labels)}",
            f"priority={DDL_PRIORITY}",
            f"Banner={','.join(banner_selected_names)}",
            f"ServiceNow Priority={sn_priority_short}",
            f"ServiceNow #={problem_number},{incident_number}",
        ]
        if banner_manual_followup:
            field_mapping_applied.append("BannerManualFollowup=required")
        if components_payload:
            field_mapping_applied.append(
                "Components=" + ",".join(item.get("name", "") for item in components_payload)
            )
        if args.upcoming_release:
            field_mapping_applied.append(f"FixVersions={args.upcoming_release.strip()}")
        if args.current_release:
            field_mapping_applied.append(f"AffectedVersion={args.current_release.strip()}")
        if root_cause_field and root_cause_option_id:
            field_mapping_applied.append("RootCause=Code")

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
