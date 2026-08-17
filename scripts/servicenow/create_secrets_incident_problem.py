#!/usr/bin/env python3
"""Create or reuse ServiceNow INC/PRB for expiring Azure Key Vault secrets from New Relic events."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Sequence

from common import bootstrap

bootstrap(override_env=True)

from servicenow_client import ServiceNowClient, ServiceNowValidationError
from reuse_common import extract_ref, find_incident_candidates, find_problem_candidates


def _build_incident_description(
    *,
    urgency: str,
    vault_name: str,
    object_name: str,
    days_remaining: int,
    event_type: str,
    event_time: Optional[str] = None,
) -> str:
    """Build incident description for expiring secret."""
    description_lines = [
        f"Azure Key Vault Secret Expiration Alert",
        "",
        f"Secret:        {object_name}",
        f"Key Vault:     {vault_name}",
        f"Days Remaining: {days_remaining}",
        f"Urgency:       {urgency.upper()}",
        f"Event Type:    {event_type}",
    ]
    if event_time:
        description_lines.append(f"Event Time:    {event_time}")
    
    description_lines.extend([
        "",
        "Recommended Actions:",
        "1. Verify secret rotation schedule with owning team",
        "2. Coordinate renewal with dependent services",
        "3. Validate new version creation before expiration",
        "4. Update automation if using hardcoded expiration dates",
    ])
    
    return "\n".join(description_lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create/reuse ServiceNow Incident and Problem for expiring Key Vault secrets.",
    )
    parser.add_argument("--account-id", type=int, default=1679802)
    parser.add_argument("--vault", required=True, help="Key Vault name")
    parser.add_argument("--secret", required=True, help="Secret object name")
    parser.add_argument("--urgency", required=True, choices=["moderate", "urgent", "critical"],
                       help="Urgency tier based on days remaining")
    parser.add_argument("--days-remaining", type=int, required=True, help="Days until expiration")
    parser.add_argument("--event-type", default="Microsoft.KeyVault.SecretNearExpiry",
                       help="Event type from New Relic")
    parser.add_argument("--event-time", default=None, help="Event timestamp")
    parser.add_argument("--caller-id", default=None, help="Required for --execute when creating a new incident")
    parser.add_argument("--assignment-group", default=None)
    parser.add_argument("--category", default="Application")
    parser.add_argument("--subcategory", default="E-Commerce")
    parser.add_argument("--service-offering", default=None)
    parser.add_argument("--cmdb-ci", default=None)
    parser.add_argument("--impact", default="2", help="ServiceNow impact value 1..3 (P3 default)")
    parser.add_argument("--urgency-sn", default=None, help="ServiceNow urgency value (default: derived from tier)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--search-days", type=int, default=30,
                       help="Search window for existing incidents (days)")
    parser.add_argument(
        "--approval-confirmed",
        action="store_true",
        help="Confirm that pre-execution approval gates have been cleared.",
    )
    parser.add_argument("--execute", action="store_true", help="Execute creation (default: dry-run)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    client = ServiceNowClient.from_env()
    configured_user = (client.config.username or "").strip()
    if not configured_user:
        raise ServiceNowValidationError("Configured ServiceNow user is required for secret incident assignment")

    configuration_item = (args.cmdb_ci or "").strip() or "canadiantire.ca"
    service_offering = (args.service_offering or "").strip() or configuration_item
    assignment_group = (args.assignment_group or client.config.assignment_groups[0]).strip()

    # Standard incident short description template
    short_description = f"[Secret {args.urgency.capitalize()}] {args.secret} in {args.vault}"

    # Determine ServiceNow urgency from tier
    urgency_map = {"moderate": "3", "urgent": "2", "critical": "1"}
    urgency_value = args.urgency_sn or urgency_map.get(args.urgency, "2")

    try:
        # Phase 1: Search for existing incidents
        incident_result = find_incident_candidates(
            client,
            exact_short_description=short_description,
            fallback_terms=[args.secret, args.vault],
            limit=args.limit,
            max_age_days=args.search_days,
        )

        existing_incident = incident_result.get("best")
        incident_number = extract_ref(existing_incident.get("number")) if existing_incident else None
        linked_problem_number = (
            extract_ref(existing_incident.get("problem_id"))
            if existing_incident
            else ""
        )

        # Phase 2: Search for existing problems
        problem_result = find_problem_candidates(
            client,
            exact_short_description=short_description,
            fallback_terms=[args.secret, args.vault],
            linked_problem_number=linked_problem_number,
            limit=args.limit,
            max_age_days=args.search_days,
        )

        existing_problem = problem_result.get("best")
        problem_number = extract_ref(existing_problem.get("number")) if existing_problem else None

        # Build output
        output = {
            "mode": "execute" if args.execute else "dry-run",
            "short_description": short_description,
            "vault": args.vault,
            "secret": args.secret,
            "urgency_tier": args.urgency,
            "days_remaining": args.days_remaining,
            "event_type": args.event_type,
            "existing_incident": {
                "number": incident_number,
                "state": extract_ref(existing_incident.get("state")) if existing_incident else None,
                "sys_id": extract_ref(existing_incident.get("sys_id")) if existing_incident else None,
            } if existing_incident else None,
            "existing_problem": {
                "number": problem_number,
                "state": extract_ref(existing_problem.get("state")) if existing_problem else None,
                "sys_id": extract_ref(existing_problem.get("sys_id")) if existing_problem else None,
            } if existing_problem else None,
            "proposed_incident": {
                "short_description": short_description,
                "description": _build_incident_description(
                    urgency=args.urgency,
                    vault_name=args.vault,
                    object_name=args.secret,
                    days_remaining=args.days_remaining,
                    event_type=args.event_type,
                    event_time=args.event_time,
                ),
                "category": args.category,
                "subcategory": args.subcategory,
                "assigned_to": configured_user,
                "assignment_group": assignment_group,
                "service_offering": service_offering,
                "cmdb_ci": configuration_item,
                "impact": args.impact,
                "urgency": "2",
            } if not existing_incident else None,
            "actions": [],
            "created": {
                "incident": None,
                "problem": None,
            },
        }

        if existing_incident and existing_problem and not args.execute:
            output["actions"].append("reused_incident_and_problem")
        elif not args.execute:
            if existing_incident:
                output["actions"].append("would_create_problem_from_existing_incident")
            else:
                output["actions"].extend([
                    "would_create_incident",
                    "would_create_problem_from_new_incident",
                ])
        else:
            if existing_incident:
                existing_incident = client.update_incident_fields(
                    sys_id=extract_ref(existing_incident.get("sys_id")),
                    fields={
                        "assigned_to": configured_user,
                        "assignment_group": assignment_group,
                        "category": args.category,
                        "subcategory": args.subcategory,
                        "service_offering": service_offering,
                        "cmdb_ci": configuration_item,
                    },
                    require_active=True,
                    forbid_resolved=True,
                )
                existing_incident = client.set_priority_by_matrix(
                    sys_id=extract_ref(existing_incident.get("sys_id")),
                    target_priority="P3",
                    work_note="Normalized by expiring-secrets execute flow.",
                )

            if not existing_incident:
                caller_id = (args.caller_id or "").strip()
                if not caller_id:
                    raise ServiceNowValidationError(
                        "--caller-id is required when creating a new incident in --execute mode"
                    )
                existing_incident = client.create_incident(
                    short_description=short_description,
                    description=_build_incident_description(
                        urgency=args.urgency,
                        vault_name=args.vault,
                        object_name=args.secret,
                        days_remaining=args.days_remaining,
                        event_type=args.event_type,
                        event_time=args.event_time,
                    ),
                    caller_id=caller_id,
                    assignment_group=assignment_group,
                    category=args.category,
                    subcategory=args.subcategory,
                    assigned_to=configured_user,
                    service_offering=service_offering,
                    cmdb_ci=configuration_item,
                    impact="2",
                    urgency="2",
                    work_note="Created by expiring-secrets execute flow.",
                )
                output["created"]["incident"] = {
                    "number": extract_ref(existing_incident.get("number")),
                    "sys_id": extract_ref(existing_incident.get("sys_id")),
                }
                output["actions"].append("created_incident")
            else:
                output["actions"].append("reused_incident")

            if not existing_problem:
                problem_bundle = client.create_problem_from_incident(
                    incident_number=extract_ref(existing_incident.get("number")),
                    problem_short_description=short_description,
                    problem_description=_build_incident_description(
                        urgency=args.urgency,
                        vault_name=args.vault,
                        object_name=args.secret,
                        days_remaining=args.days_remaining,
                        event_type=args.event_type,
                        event_time=args.event_time,
                    ),
                    work_note="Linked Problem created by expiring-secrets execute flow.",
                )
                created_problem = problem_bundle.get("problem") or {}
                output["created"]["problem"] = {
                    "number": extract_ref(created_problem.get("number")),
                    "sys_id": extract_ref(created_problem.get("sys_id")),
                }
                output["actions"].append("created_problem")
            else:
                output["actions"].append("reused_problem")

        if args.json:
            print(json.dumps(output, indent=2))
        else:
            print(json.dumps(output, indent=2))

        return 0

    except ServiceNowValidationError as exc:
        print(f"ServiceNow validation error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
