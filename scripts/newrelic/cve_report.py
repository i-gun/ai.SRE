#!/usr/bin/env python3
"""Report CVE vulnerabilities affecting monitored service groups via New Relic Vulnerability events."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Sequence

from common import bootstrap


DEFAULT_ACCOUNT_ID = 1679802
DEFAULT_SINCE = "2 days ago"
DEFAULT_UNTIL = "1 day ago"
DEFAULT_SEVERITIES = "CRITICAL,HIGH"

# NRQL CASES groups and their matching conditions — extend here to add new service groups.
_SERVICE_GROUPS: List[Dict[str, str]] = [
    {
        "label": "Search",
        "condition": (
            "entityLookupValue LIKE '%PROD-Atlas-SAPI%' "
            "OR entityLookupValue LIKE 'Prod-AutoSearch%'"
        ),
    },
    {
        "label": "CDS",
        "condition": (
            "entityLookupValue LIKE 'cds.%' "
            "OR entityLookupValue LIKE '%vector%' "
            "OR entityLookupValue LIKE '%-costar-%'"
        ),
    },
    {
        "label": "PPE",
        "condition": "entityLookupValue LIKE '%DMT-%PPE%'",
    },
    {
        "label": "DTE, Inventory",
        "condition": (
            "entityLookupValue = 'P-DMT-MDTE' "
            "OR entityLookupValue = 'Prod-Enterprise Services-Inventory Service'"
        ),
    },
    {
        "label": "SFSc",
        "condition": "entityLookupValue IN ('hos-prod','sfsc-prod','ioms-prod')",
    },
]


def _build_detail_nrql(cve_id: str, severities: List[str], since: str, until: str) -> str:
    severity_list = ", ".join(f"'{s}'" for s in severities)
    service_filter = " OR ".join(f"({g['condition']})" for g in _SERVICE_GROUPS)
    # Single-quote escaping guards against NRQL injection from user-supplied CVE IDs.
    safe_cve = cve_id.replace("'", "''")
    return (
        f"FROM Vulnerability "
        f"SELECT latest(loglevel) AS severity, "
        f"latest(package) AS package, "
        f"latest(package.version) AS packageVersion, "
        f"latest(remediation.upgradeAction) AS remediationUpgradeAction, "
        f"latest(disclosureUrl) AS disclosureUrl, "
        f"latest(title) AS title "
        f"WHERE loglevel IN ({severity_list}) "
        f"AND cve = '{safe_cve}' "
        f"AND ({service_filter}) "
        f"FACET entityLookupValue "
        f"SINCE {since} UNTIL {until} "
        f"LIMIT MAX"
    )


def _facet_str(row: Dict[str, Any]) -> str:
    """Extract the first facet value whether NR returns a string or a list."""
    facet = row.get("facet")
    if isinstance(facet, list):
        return facet[0] if facet else ""
    return str(facet) if facet is not None else ""


def _render_detail_table(rows: List[Dict[str, Any]], cve_id: str) -> None:
    if not rows:
        print(f"No services found for {cve_id} in the specified window.")
        return

    # Print advisory header fields (same across all services for a given CVE).
    first = rows[0]
    title = first.get("title") or ""
    disclosure = first.get("disclosureUrl") or ""
    if title:
        print(f"  Title:      {title}")
    if disclosure:
        print(f"  Disclosure: {disclosure}")
    print()

    col_service = max(len("Service"), max(len(_facet_str(r)) for r in rows))
    col_sev = max(len("Severity"), max(len(r.get("severity") or "") for r in rows))
    col_pkg = max(len("Package"), max(len(r.get("package") or "") for r in rows))
    col_ver = max(len("Version"), max(len(r.get("packageVersion") or "") for r in rows))

    header = (
        f"{'Service':<{col_service}}  "
        f"{'Severity':<{col_sev}}  "
        f"{'Package':<{col_pkg}}  "
        f"{'Version':<{col_ver}}  "
        f"Remediation"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    for row in sorted(rows, key=lambda r: _facet_str(r)):
        service = _facet_str(row)
        print(
            f"{service:<{col_service}}  "
            f"{(row.get('severity') or ''):<{col_sev}}  "
            f"{(row.get('package') or ''):<{col_pkg}}  "
            f"{(row.get('packageVersion') or ''):<{col_ver}}  "
            f"{row.get('remediationUpgradeAction') or ''}"
        )

    print(sep)
    print(f"Total: {len(rows)} services")


def _build_nrql(severities: List[str], since: str, until: str) -> str:
    severity_list = ", ".join(f"'{s}'" for s in severities)
    service_filter = " OR ".join(f"({g['condition']})" for g in _SERVICE_GROUPS)
    cases_clauses = ", ".join(
        f"WHERE {g['condition']} AS '{g['label']}'" for g in _SERVICE_GROUPS
    )
    return (
        f"FROM Vulnerability "
        f"SELECT latest(loglevel) AS severity, "
        f"uniques(entityLookupValue) AS affectedServices, "
        f"uniqueCount(entityLookupValue) AS affectedServiceCount, "
        f"uniques(disclosureUrl) AS disclosureUrl, "
        f"uniques(title) AS title, "
        f"uniques(package) AS package, "
        f"uniques(package.version) AS packageVersion, "
        f"uniques(remediation.upgradeAction) AS remediationUpgradeAction "
        f"WHERE loglevel IN ({severity_list}) "
        f"AND cve IS NOT NULL "
        f"AND ({service_filter}) "
        f"FACET cve, "
        f"CASES({cases_clauses}) "
        f"SINCE {since} UNTIL {until} "
        f"LIMIT MAX"
    )


def _join_uniques(val: Any) -> str:
    """Flatten a uniques() array to a comma-separated string."""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val if v is not None)
    return str(val) if val is not None else ""


def _render_table(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        print("No CVE vulnerabilities found for the specified time window and severity filter.")
        return

    col_severity = max(len("CVE Severity"), max(len(r.get("severity", "") or "") for r in rows))
    col_cve = max(len("CVE / Vuln ID"), max(len((r.get("facet") or [""])[0]) for r in rows))
    col_group = max(len("Service Group"), max(len((r.get("facet") or ["", ""])[1]) for r in rows))
    col_count = len("Service Count")

    header = (
        f"{'CVE Severity':<{col_severity}}  "
        f"{'CVE / Vuln ID':<{col_cve}}  "
        f"{'Service Group':<{col_group}}  "
        f"{'Service Count':>{col_count}}  "
        f"Affected Services"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    for row in rows:
        facet = row.get("facet") or []
        cve_id = facet[0] if len(facet) > 0 else ""
        group = facet[1] if len(facet) > 1 else ""
        severity = row.get("severity") or ""
        count = row.get("affectedServiceCount") or 0
        services: List[str] = row.get("affectedServices") or []
        services_str = ", ".join(sorted(services))
        print(
            f"{severity:<{col_severity}}  "
            f"{cve_id:<{col_cve}}  "
            f"{group:<{col_group}}  "
            f"{count:>{col_count}}  "
            f"{services_str}"
        )

    print(sep)
    print(f"Total rows: {len(rows)}")

    # Advisory details block — one block per unique CVE, regardless of service group count.
    advisory: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cve_id = (row.get("facet") or [""])[0]
        if not cve_id or cve_id in advisory:
            continue
        advisory[cve_id] = {
            "title": _join_uniques(row.get("title")),
            "package": _join_uniques(row.get("package")),
            "packageVersion": _join_uniques(row.get("packageVersion")),
            "disclosureUrl": _join_uniques(row.get("disclosureUrl")),
            "remediationUpgradeAction": _join_uniques(row.get("remediationUpgradeAction")),
        }

    if advisory and any(any(v for v in d.values()) for d in advisory.values()):
        print("\nCVE Advisory Details")
        print(sep)
        for cve_id, det in advisory.items():
            print(cve_id)
            if det["title"]:
                print(f"  Title:       {det['title']}")
            pkg, ver = det["package"], det["packageVersion"]
            if pkg or ver:
                print(f"  Package:     {(pkg + ' @ ' + ver) if pkg and ver else pkg or ver}")
            if det["disclosureUrl"]:
                print(f"  Disclosure:  {det['disclosureUrl']}")
            if det["remediationUpgradeAction"]:
                print(f"  Remediation: {det['remediationUpgradeAction']}")
            print()
        print(sep)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report CVE/HIGH vulnerabilities affecting monitored service groups "
            "using New Relic Vulnerability events."
        )
    )
    parser.add_argument(
        "--account-id",
        type=int,
        default=DEFAULT_ACCOUNT_ID,
        help=f"New Relic account ID to query (default: {DEFAULT_ACCOUNT_ID}).",
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        help=f"NRQL SINCE clause (default: '{DEFAULT_SINCE}').",
    )
    parser.add_argument(
        "--until",
        default=DEFAULT_UNTIL,
        help=f"NRQL UNTIL clause (default: '{DEFAULT_UNTIL}').",
    )
    parser.add_argument(
        "--severities",
        default=DEFAULT_SEVERITIES,
        help=f"Comma-separated severity list (default: '{DEFAULT_SEVERITIES}').",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Emit raw JSON instead of a formatted table.",
    )
    parser.add_argument(
        "--detail-cve",
        default=None,
        metavar="CVE_ID",
        help="Per-service breakdown for a specific CVE ID (e.g. GHSA-5p4m-2wfm-xmqj).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    # Ensure UTF-8 output on Windows where the default console encoding is cp1252.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    bootstrap()

    from newrelic_client import NewRelicClient  # pylint: disable=import-error

    severities = [s.strip().upper() for s in args.severities.split(",") if s.strip()]
    client = NewRelicClient.from_env()

    if args.detail_cve:
        nrql = _build_detail_nrql(
            cve_id=args.detail_cve.strip(),
            severities=severities,
            since=args.since,
            until=args.until,
        )
        rows = client.run_nrql(account_id=args.account_id, nrql=nrql)
        if args.output_json:
            print(json.dumps({"account_id": args.account_id, "cve": args.detail_cve, "since": args.since, "until": args.until, "rows": rows}, indent=2))
        else:
            print(f"\nPer-Service CVE Detail -- {args.detail_cve} | account {args.account_id} | {args.since} -> {args.until}\n")
            _render_detail_table(rows, cve_id=args.detail_cve)
    else:
        nrql = _build_nrql(severities=severities, since=args.since, until=args.until)
        rows = client.run_nrql(account_id=args.account_id, nrql=nrql)
        if args.output_json:
            print(json.dumps({"account_id": args.account_id, "since": args.since, "until": args.until, "rows": rows}, indent=2))
        else:
            print(f"\nCVE Vulnerability Report -- account {args.account_id} | {args.since} -> {args.until}\n")
            _render_table(rows)


if __name__ == "__main__":
    main()
