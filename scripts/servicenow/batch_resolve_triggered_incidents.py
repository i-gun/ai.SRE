#!/usr/bin/env python3
"""
Batch resolve ServiceNow incidents matching a short-description prefix.

GOVERNANCE NOTE:
  For operational use, prefer the @ServiceNow agent with prepared prompts.
  This script remains useful for repeatable local execution and automation.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List

from common import bootstrap

bootstrap(override_env=True)

from servicenow_client import ServiceNowAPIError, ServiceNowClient, ServiceNowValidationError


DEFAULT_SHORT_DESC_PREFIX = "Triggered : "
DEFAULT_CATEGORY = "Application"
DEFAULT_SUBCATEGORY = "E-Commerce"
DEFAULT_CLOSE_CODE = "Fixed"
DEFAULT_QUERY_LIMIT = 500
DEFAULT_MAX_INCIDENTS = 25


def _reference_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("display_value") or value.get("value") or "").strip()
    return str(value or "").strip()


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List or resolve scoped active incidents by short-description prefix.",
    )
    parser.add_argument(
        "--short-description-prefix",
        default=DEFAULT_SHORT_DESC_PREFIX,
        help="Filter incidents whose short description starts with this prefix.",
    )
    parser.add_argument("--service-offering", required=True, help="Target service offering.")
    parser.add_argument("--vendor-ticket", required=True, help="Vendor/Jira ticket reference.")
    parser.add_argument("--close-notes", required=True, help="Close notes applied during resolution.")
    parser.add_argument("--category", default=DEFAULT_CATEGORY, help="Incident category.")
    parser.add_argument("--subcategory", default=DEFAULT_SUBCATEGORY, help="Incident subcategory.")
    parser.add_argument("--close-code", default=DEFAULT_CLOSE_CODE, help="Resolution close code.")
    parser.add_argument(
        "--assignment-user",
        default=None,
        help="Optional assignment username override. Defaults to SERVICENOW_USERNAME.",
    )
    parser.add_argument(
        "--query-limit",
        type=int,
        default=DEFAULT_QUERY_LIMIT,
        help="Maximum incidents to query from ServiceNow.",
    )
    parser.add_argument(
        "--max-incidents",
        type=int,
        default=DEFAULT_MAX_INCIDENTS,
        help="Maximum incidents allowed for a write run unless --force-large-batch is set.",
    )
    parser.add_argument(
        "--force-large-batch",
        action="store_true",
        help="Allow execution when matches exceed --max-incidents.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform assignments and resolution updates. Without this flag the script is read-only.",
    )
    args = parser.parse_args(argv)

    if not args.short_description_prefix.strip():
        parser.error("--short-description-prefix must not be empty.")
    if not args.service_offering.strip():
        parser.error("--service-offering must not be empty.")
    if not args.vendor_ticket.strip():
        parser.error("--vendor-ticket must not be empty.")
    if not args.close_notes.strip():
        parser.error("--close-notes must not be empty.")
    if args.query_limit <= 0:
        parser.error("--query-limit must be greater than zero.")
    if args.max_incidents <= 0:
        parser.error("--max-incidents must be greater than zero.")
    return args


def _build_update_config(args: argparse.Namespace) -> Dict[str, str]:
    return {
        "category": args.category.strip(),
        "subcategory": args.subcategory.strip(),
        "service_offering": args.service_offering.strip(),
        "u_vendor_ticket": args.vendor_ticket.strip(),
        "vendor_ticket": args.vendor_ticket.strip(),
        "close_code": args.close_code.strip(),
        "close_notes": args.close_notes.strip(),
    }


def _fetch_matching_incidents(client: ServiceNowClient, prefix: str, limit: int) -> List[Dict[str, Any]]:
    all_incidents = client.list_incidents(active_only=True, exclude_resolved=True, limit=limit)
    return [
        inc for inc in all_incidents
        if str(inc.get("short_description") or "").startswith(prefix)
        and not client.is_resolved_state(inc.get("state"))
    ]


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)

    print("=" * 100)
    print("BATCH RESOLVE TRIGGERED INCIDENTS")
    print("=" * 100 + "\n")

    print("[INIT] Initializing ServiceNow client...")
    try:
        client = ServiceNowClient.from_env()
        print("[OK] ServiceNow client initialized\n")
    except Exception as exc:
        print(f"[ERROR] Failed to initialize client: {exc}")
        return 1

    configured_user = (args.assignment_user or os.getenv("SERVICENOW_USERNAME", "")).strip()
    if not configured_user:
        print("[ERROR] SERVICENOW_USERNAME not configured in .env")
        return 1

    print(f"[CONFIG] Configured assignment user: {configured_user}")
    print(f"[CONFIG] Read-only mode: {'no' if args.execute else 'yes'}")
    print(f"[CONFIG] Prefix filter: {args.short_description_prefix}")
    print(f"[CONFIG] Query limit: {args.query_limit}")
    print(f"[CONFIG] Execution threshold: {args.max_incidents}\n")

    print("=" * 100)
    print("STEP 1: FETCHING INCIDENTS")
    print("=" * 100 + "\n")
    print(
        "[FETCH] Retrieving active unresolved incidents with short_description starting with "
        f"'{args.short_description_prefix}'..."
    )

    try:
        matching_incidents = _fetch_matching_incidents(client, args.short_description_prefix, args.query_limit)
        print(f"[OK] Found {len(matching_incidents)} matching incident(s)\n")
    except Exception as exc:
        print(f"[ERROR] Failed to fetch incidents: {exc}")
        return 1

    if not matching_incidents:
        print("[INFO] No incidents match the criteria.")
        print("[DONE] Process complete.\n")
        return 0

    print("=" * 100)
    print("STEP 2: MATCHING INCIDENTS SUMMARY")
    print("=" * 100 + "\n")
    print(
        f"{'#':<3} {'Number':<12} {'Priority':<12} {'State':<14} {'Assignment Group':<30} "
        f"{'Assigned To':<28} {'sys_id':<34} {'Short Description':<40}"
    )
    print("-" * 190)
    for idx, inc in enumerate(matching_incidents, 1):
        print(
            f"{idx:<3} {inc.get('number', 'N/A'):<12} {str(inc.get('priority', 'N/A')):<12} "
            f"{_reference_text(inc.get('state')) or 'N/A':<14} "
            f"{_reference_text(inc.get('assignment_group')) or 'N/A':<30} "
            f"{_reference_text(inc.get('assigned_to')) or '(unassigned)':<28} "
            f"{str(inc.get('sys_id', 'N/A')):<34} {str(inc.get('short_description', 'N/A'))[:38]:<40}"
        )

    print(f"\n[CONFIRM] Total incidents to process: {len(matching_incidents)}\n")

    if not args.execute:
        print("[SAFE MODE] No changes were applied. Re-run with --execute to assign and resolve incidents.\n")
        return 0

    if len(matching_incidents) > args.max_incidents and not args.force_large_batch:
        print(
            "[GATE] Refusing to update incidents because match count exceeds the allowed threshold. "
            f"Matched={len(matching_incidents)}, threshold={args.max_incidents}. "
            "Use --force-large-batch to override after review.\n"
        )
        return 2

    print("=" * 100)
    print("STEP 3: ASSIGNING UNASSIGNED INCIDENTS")
    print("=" * 100 + "\n")

    assignment_results = {"assigned": [], "already_assigned": [], "failed": []}
    for inc in [item for item in matching_incidents if not _reference_text(item.get("assigned_to"))]:
        number = inc.get("number", "N/A")
        sys_id = inc.get("sys_id")
        try:
            print(f"[ASSIGN] {number}: Assigning to {configured_user}...")
            client.assign_incident(sys_id=sys_id, assigned_to=configured_user, allow_reassign=False)
            assignment_results["assigned"].append(number)
            print(f"[OK] {number}: Assigned successfully")
        except ServiceNowValidationError as exc:
            if "already has an assignee" in str(exc):
                assignment_results["already_assigned"].append(number)
                print(f"[INFO] {number}: Already assigned")
            else:
                assignment_results["failed"].append((number, str(exc)))
                print(f"[WARN] {number}: {exc}")
        except Exception as exc:
            assignment_results["failed"].append((number, str(exc)))
            print(f"[ERROR] {number}: {exc}")

    print("\n[SUMMARY] Assignment Results:")
    print(f"  - Assigned: {len(assignment_results['assigned'])}")
    print(f"  - Already assigned: {len(assignment_results['already_assigned'])}")
    print(f"  - Failed: {len(assignment_results['failed'])}")
    for num, err in assignment_results["failed"]:
        print(f"    - {num}: {err}")
    print()

    print("=" * 100)
    print("STEP 4: UPDATING AND RESOLVING INCIDENTS")
    print("=" * 100 + "\n")

    update_config = _build_update_config(args)
    resolution_results = {"resolved": [], "skipped": [], "failed": []}

    for inc in matching_incidents:
        number = inc.get("number", "N/A")
        sys_id = inc.get("sys_id")
        current_state = _reference_text(inc.get("state"))
        if client.is_resolved_state(current_state):
            resolution_results["skipped"].append((number, f"Already resolved before update: {current_state}"))
            print(f"[SKIP] {number}: already resolved before update ({current_state})")
            continue

        print(f"[UPDATE] {number}: Updating fields and resolving...")
        try:
            refreshed = client._find_incident(incident_number=None, sys_id=sys_id)
            refreshed_state = _reference_text(refreshed.get("state"))
            if client.is_resolved_state(refreshed_state):
                resolution_results["skipped"].append((number, f"Became resolved before update: {refreshed_state}"))
                print(f"[SKIP] {number}: became resolved before update ({refreshed_state})")
                continue

            work_note = (
                f"[BULK RESOLUTION] Updated from batch operation: category='{update_config['category']}', "
                f"subcategory='{update_config['subcategory']}', "
                f"service_offering='{update_config['service_offering']}', "
                f"vendor_ticket='{update_config['u_vendor_ticket']}'"
            )
            updated_incident = client.resolve_incident_with_updates(
                sys_id=sys_id,
                category=update_config["category"],
                subcategory=update_config["subcategory"],
                service_offering=update_config["service_offering"],
                vendor_ticket=update_config["u_vendor_ticket"],
                close_code=update_config["close_code"],
                close_notes=update_config["close_notes"],
                work_note=work_note,
            )

            resolution_results["resolved"].append(number)
            print(
                f"[OK] {number}: Resolved (State: {_reference_text(updated_incident.get('state'))}, "
                f"Priority: {updated_incident.get('priority')})"
            )
        except ServiceNowAPIError as exc:
            resolution_results["failed"].append((number, str(exc)))
            print(f"[ERROR] {number}: API Error - {exc}")
        except Exception as exc:
            resolution_results["failed"].append((number, str(exc)))
            print(f"[ERROR] {number}: {exc}")

    print("\n[RESULTS] Resolution Summary:")
    print(f"  - Successfully resolved: {len(resolution_results['resolved'])}")
    print(f"  - Skipped: {len(resolution_results['skipped'])}")
    print(f"  - Failed resolutions: {len(resolution_results['failed'])}")
    if resolution_results["resolved"]:
        print("\n[RESOLVED INCIDENTS]:")
        for num in resolution_results["resolved"]:
            print(f"  ✓ {num}")
    if resolution_results["skipped"]:
        print("\n[SKIPPED INCIDENTS]:")
        for num, reason in resolution_results["skipped"]:
            print(f"  - {num}: {reason}")
    if resolution_results["failed"]:
        print("\n[FAILED INCIDENTS]:")
        for num, error in resolution_results["failed"]:
            print(f"  ✗ {num}: {error}")

    print("\n[FINAL CHECK] Verifying incident states...")
    try:
        remaining = client.list_incidents(active_only=True, exclude_resolved=True, limit=args.query_limit)
        remaining_matching = [
            inc for inc in remaining
            if str(inc.get("short_description") or "").startswith(args.short_description_prefix)
            and not client.is_resolved_state(inc.get("state"))
        ]
        print(f"  - Remaining active matching incidents: {len(remaining_matching)}")
        if remaining_matching:
            print("    (These may have been created after initial fetch)")
            for inc in remaining_matching[:5]:
                print(f"      - {inc.get('number')}: {str(inc.get('short_description', ''))[:50]}")
    except Exception as exc:
        print(f"  - Final check error: {exc}")

    print("\n[DONE] Batch operation complete.\n")
    return 0 if not resolution_results["failed"] else 2


if __name__ == "__main__":
    sys.exit(main())
