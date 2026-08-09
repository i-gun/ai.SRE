#!/usr/bin/env python3
"""Build dry-run ServiceNow incident/problem payloads from New Relic CVE data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from bootstrap_shared import bootstrap_paths

NEWRELIC_LOG_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "newrelic-log-operations"


def _bootstrap() -> None:
    bootstrap_paths(skill_paths=[NEWRELIC_LOG_SKILL_PATH], override_env=True)


def _build_grouped_nrql(severities: List[str], since: str, until: str) -> str:
    severity_list = ", ".join(f"'{s}'" for s in severities)
    return (
        "FROM Vulnerability "
        "SELECT latest(loglevel) AS severity, "
        "uniques(entityLookupValue) AS affectedServices, "
        "uniqueCount(entityLookupValue) AS affectedServiceCount, "
        "uniques(disclosureUrl) AS disclosureUrl, "
        "uniques(title) AS title, "
        "uniques(package) AS package, "
        "uniques(package.version) AS packageVersion, "
        "uniques(remediation.upgradeAction) AS remediationUpgradeAction "
        f"WHERE loglevel IN ({severity_list}) AND cve IS NOT NULL "
        "FACET cve, CASES("
        "WHERE entityLookupValue LIKE '%PROD-Atlas-SAPI%' OR entityLookupValue LIKE 'Prod-AutoSearch%' AS 'Search', "
        "WHERE entityLookupValue LIKE 'cds.%' OR entityLookupValue LIKE '%vector%' OR entityLookupValue LIKE '%-costar-%' AS 'CDS', "
        "WHERE entityLookupValue LIKE '%DMT-%PPE%' AS 'PPE', "
        "WHERE entityLookupValue = 'P-DMT-MDTE' OR entityLookupValue = 'Prod-Enterprise Services-Inventory Service' AS 'DTE, Inventory', "
        "WHERE entityLookupValue IN ('hos-prod','sfsc-prod','ioms-prod') AS 'SFSc'"
        ") "
        f"SINCE {since} UNTIL {until} LIMIT MAX"
    )


def _build_detail_nrql(cve_id: str, severities: List[str], since: str, until: str) -> str:
    severity_list = ", ".join(f"'{s}'" for s in severities)
    safe_cve = cve_id.replace("'", "''")
    return (
        "FROM Vulnerability "
        "SELECT latest(loglevel) AS severity, latest(package) AS package, "
        "latest(package.version) AS packageVersion, "
        "latest(remediation.upgradeAction) AS remediationUpgradeAction, "
        "latest(disclosureUrl) AS disclosureUrl, latest(title) AS title "
        f"WHERE loglevel IN ({severity_list}) AND cve = '{safe_cve}' "
        "FACET entityLookupValue "
        f"SINCE {since} UNTIL {until} LIMIT MAX"
    )


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dry-run ServiceNow CVE payload previews")
    parser.add_argument("--account-id", type=int, default=1679802)
    parser.add_argument("--cve", required=True, help="CVE or GHSA identifier")
    parser.add_argument("--kind", required=True, help="Kind label used in short_description")
    parser.add_argument("--since", default="2 days ago")
    parser.add_argument("--until", default="1 day ago")
    parser.add_argument("--severities", default="CRITICAL,HIGH")
    parser.add_argument(
        "--newrelic-url",
        default=None,
        help="Preferred New Relic deep-link URL (onenr/one.newrelic). Falls back to disclosureUrl.",
    )
    return parser.parse_args(argv)


def build_payload_preview(
    *,
    account_id: int,
    cve: str,
    kind: str,
    since: str,
    until: str,
    severities: Sequence[str],
    newrelic_url: str | None = None,
) -> Dict[str, Any]:
    _bootstrap()

    from newrelic_client import NewRelicClient  # pylint: disable=import-error

    normalized_severities = [str(s).strip().upper() for s in severities if str(s).strip()]
    client = NewRelicClient.from_env()

    grouped_rows = client.run_nrql(
        account_id=account_id,
        nrql=_build_grouped_nrql(severities=normalized_severities, since=since, until=until),
    )
    detail_rows = client.run_nrql(
        account_id=account_id,
        nrql=_build_detail_nrql(cve_id=cve, severities=normalized_severities, since=since, until=until),
    )

    grouped_match = None
    for row in grouped_rows:
        facet = row.get("facet") or []
        if not isinstance(facet, list) or len(facet) < 2:
            continue
        if str(facet[0]) == cve and str(facet[1]) == kind:
            grouped_match = row
            break

    if grouped_match is None:
        grouped_match = {
            "severity": "HIGH",
            "title": [],
            "disclosureUrl": [],
            "remediationUpgradeAction": [],
        }

    severity = str(grouped_match.get("severity") or "HIGH")
    title = _as_list(grouped_match.get("title"))
    disclosure = _as_list(grouped_match.get("disclosureUrl"))

    summary_details = title[0] if title else f"Vulnerability detected for {cve}"
    effective_newrelic_url = newrelic_url or (disclosure[0] if disclosure else "")

    service_lines: List[str] = []
    for row in sorted(detail_rows, key=lambda r: str(r.get("facet") or "")):
        service = str(row.get("facet") or "")
        package = str(row.get("package") or "")
        version = str(row.get("packageVersion") or "")
        remediation = str(row.get("remediationUpgradeAction") or "")
        service_lines.append(f"{service} | {package} | {version} | {remediation}")

    description_lines = [
        f"Vulnerability in NR - {effective_newrelic_url}",
        "Summary:",
        f"  {summary_details}",
        "Affected services:",
    ]
    if service_lines:
        for line in service_lines:
            description_lines.append(f"  {line}")
    else:
        description_lines.append("  [no detail rows found]")

    description_lines.extend([
        "Additional information:",
        f"  {disclosure[0] if disclosure else ''}",
    ])

    short_description = f"[{kind}] {severity} vulnerability found {cve}"

    output = {
        "input": {
            "account_id": account_id,
            "cve": cve,
            "kind": kind,
            "since": since,
            "until": until,
            "newrelic_url": newrelic_url,
        },
        "servicenow": {
            "incident": {
                "short_description": short_description,
                "description": "\n".join(description_lines),
            },
            "problem": {
                "short_description": short_description,
                "description": "\n".join(description_lines),
            },
        },
        "source": {
            "grouped_match": grouped_match,
            "detail_rows": detail_rows,
        },
    }

    return output


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    severities = [s.strip().upper() for s in args.severities.split(",") if s.strip()]

    output = build_payload_preview(
        account_id=args.account_id,
        cve=args.cve,
        kind=args.kind,
        since=args.since,
        until=args.until,
        severities=severities,
        newrelic_url=args.newrelic_url,
    )

    print(json.dumps(output, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
