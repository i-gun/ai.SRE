#!/usr/bin/env python3
"""Create or reuse ServiceNow INC/PRB for CVE triage from New Relic-derived payloads."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Sequence

from common import bootstrap
from cve_payload_preview import build_payload_preview
from reuse_common import extract_ref, find_incident_candidates, find_problem_candidates

bootstrap(override_env=True)

from servicenow_client import ServiceNowClient, ServiceNowValidationError


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create/reuse ServiceNow Incident and Problem for CVE impact records.",
    )
    parser.add_argument("--account-id", type=int, default=1679802)
    parser.add_argument("--cve", required=True, help="CVE or GHSA identifier")
    parser.add_argument("--kind", required=True, help="Service group kind (e.g., CDS, Search)")
    parser.add_argument("--since", default="2 days ago")
    parser.add_argument("--until", default="1 day ago")
    parser.add_argument("--severities", default="CRITICAL,HIGH")
    parser.add_argument("--newrelic-url", default=None)
    parser.add_argument("--caller-id", default=None, help="Required for --execute when creating a new incident")
    parser.add_argument("--assignment-group", default=None)
    parser.add_argument("--category", default="Application")
    parser.add_argument("--subcategory", default="E-Commerce")
    parser.add_argument("--service-offering", default=None)
    parser.add_argument("--cmdb-ci", default=None)
    parser.add_argument("--impact", default="2", help="ServiceNow impact value 1..3")
    parser.add_argument("--urgency", default="2", help="ServiceNow urgency value 1..3")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--approval-confirmed",
        action="store_true",
        help="Required in --execute mode when fallback/resolved reuse candidates trigger manual approval gate.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply writes in ServiceNow. Without this flag, script is dry-run only.",
    )
    return parser.parse_args(argv)


def _record_stub(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "number": extract_ref(row.get("number")),
        "sys_id": extract_ref(row.get("sys_id")),
        "short_description": extract_ref(row.get("short_description")),
        "state": extract_ref(row.get("state")),
    }


def _approval_gate(
    *,
    client: ServiceNowClient,
    best_incident: Optional[Dict[str, Any]],
    short_description: str,
    exact_count: int,
    fallback_count: int,
) -> Dict[str, Any]:
    reasons: List[str] = []
    selected = _record_stub(best_incident)
    if selected:
        selected_short = str(selected.get("short_description") or "").strip()
        if selected_short and selected_short.lower() != short_description.lower():
            reasons.append("selected_incident_summary_not_exact_template")
        if client.is_resolved_state(selected.get("state")):
            reasons.append("selected_incident_is_resolved")
        if exact_count == 0 and fallback_count > 0:
            reasons.append("selected_from_fallback_cve_match_only")

    required = bool(reasons)
    return {
        "required": required,
        "reasons": reasons,
        "reminder": (
            "Manual live verification required before execute: check ServiceNow and/or Jira platforms "
            "for record suitability, duplicates, and linkage strategy."
            if required
            else "no_manual_gate_required"
        ),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    severities = [s.strip().upper() for s in args.severities.split(",") if s.strip()]
    preview = build_payload_preview(
        account_id=args.account_id,
        cve=args.cve.strip(),
        kind=args.kind.strip(),
        since=args.since,
        until=args.until,
        severities=severities,
        newrelic_url=args.newrelic_url,
    )

    incident_payload = preview["servicenow"]["incident"]
    problem_payload = preview["servicenow"]["problem"]
    short_description = str(incident_payload.get("short_description") or "").strip()
    description = str(incident_payload.get("description") or "").strip()

    client = ServiceNowClient.from_env()

    incident_matches = find_incident_candidates(
        client,
        exact_short_description=short_description,
        fallback_terms=[args.cve.strip()],
        limit=args.limit,
    )
    best_incident = incident_matches.get("best")
    linked_problem_number = extract_ref((best_incident or {}).get("problem_id"))

    problem_matches = find_problem_candidates(
        client,
        exact_short_description=short_description,
        fallback_terms=[args.cve.strip()],
        linked_problem_number=linked_problem_number,
        limit=args.limit,
    )
    best_problem = problem_matches.get("best")

    result: Dict[str, Any] = {
        "mode": "execute" if args.execute else "dry-run",
        "input": {
            "cve": args.cve,
            "kind": args.kind,
            "account_id": args.account_id,
            "since": args.since,
            "until": args.until,
            "severities": severities,
        },
        "payload_preview": preview["servicenow"],
        "reuse_search": {
            "incident": {
                "exact_count": len(incident_matches["exact_matches"]),
                "fallback_count": len(incident_matches["fallback_matches"]),
                "selected": _record_stub(best_incident),
            },
            "problem": {
                "linked_count": len(problem_matches["linked_matches"]),
                "exact_count": len(problem_matches["exact_matches"]),
                "fallback_count": len(problem_matches["fallback_matches"]),
                "selected": _record_stub(best_problem),
            },
        },
        "actions": [],
        "created": {
            "incident": None,
            "problem": None,
        },
    }

    gate = _approval_gate(
        client=client,
        best_incident=best_incident,
        short_description=short_description,
        exact_count=len(incident_matches["exact_matches"]),
        fallback_count=len(incident_matches["fallback_matches"]),
    )
    result["approval_gate"] = gate

    if best_incident and best_problem:
        result["actions"].append("reuse_incident_and_problem")
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0

    if not args.execute:
        if best_incident and not best_problem:
            result["actions"].append("would_create_problem_from_existing_incident")
        elif not best_incident:
            result["actions"].append("would_create_incident")
            result["actions"].append("would_create_problem_from_new_incident")
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0

    if gate.get("required") and not args.approval_confirmed:
        raise ServiceNowValidationError(
            "Approval gate triggered. Re-run with --approval-confirmed only after manual live verification in "
            "ServiceNow and/or Jira."
        )

    if not best_incident:
        caller_id = (args.caller_id or "").strip()
        if not caller_id:
            raise ServiceNowValidationError("--caller-id is required when creating a new incident in --execute mode")

        created_incident = client.create_incident(
            short_description=short_description,
            description=description,
            caller_id=caller_id,
            assignment_group=args.assignment_group,
            category=args.category,
            subcategory=args.subcategory,
            service_offering=args.service_offering,
            cmdb_ci=args.cmdb_ci,
            impact=args.impact,
            urgency=args.urgency,
            work_note="Created by CVE create/reuse flow (execute mode).",
        )
        best_incident = created_incident
        result["created"]["incident"] = _record_stub(created_incident)
        result["actions"].append("created_incident")
    else:
        result["actions"].append("reused_incident")

    if not best_problem:
        created_problem_bundle = client.create_problem_from_incident(
            incident_number=extract_ref(best_incident.get("number")),
            problem_short_description=str(problem_payload.get("short_description") or short_description),
            problem_description=str(problem_payload.get("description") or description),
            work_note="Linked Problem created by CVE create/reuse flow (execute mode).",
        )
        created_problem = created_problem_bundle.get("problem") or {}
        result["created"]["problem"] = _record_stub(created_problem)
        result["actions"].append("created_problem")
    else:
        result["actions"].append("reused_problem")

    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pylint: disable=broad-except
        print(json.dumps({"error": str(exc)}, indent=2, ensure_ascii=True))
        sys.exit(1)
