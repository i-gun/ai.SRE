#!/usr/bin/env python3
"""Report Azure Key Vault expiring secrets affecting Digital business unit via New Relic AzureKeyVaultSecretExpiration log partition."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from common import bootstrap


DEFAULT_ACCOUNT_ID = 1679802
DEFAULT_BUSINESS_UNIT = "Digital"


def _build_summary_nrql(business_unit: str) -> str:
    """Build NRQL query to summarize expiring secrets grouped by urgency."""
    safe_bu = business_unit.replace("'", "''")
    return (
        f"FROM AzureKeyVaultSecretExpiration "
        f"SELECT count(*) AS secretCount "
        f"WHERE businessUnit = '{safe_bu}' "
        f"LIMIT 1"
    )


def _build_detail_nrql(business_unit: str, include_new_version_check: bool = False) -> str:
    """Build NRQL query for detailed secret expiration records."""
    safe_bu = business_unit.replace("'", "''")
    base = (
        f"FROM AzureKeyVaultSecretExpiration "
        f"SELECT latest(daysUntilExpiry) AS daysUntilExpiry, "
        f"latest(expiryTime) AS expiryTime, "
        f"latest(lastModified) AS lastModified "
        f"WHERE businessUnit = '{safe_bu}' "
        f"FACET objectName, vaultName "
        f"LIMIT 1000"
    )
    return base


def _classify_urgency(days_remaining: int) -> str:
    """Classify urgency based on days remaining until expiry."""
    if days_remaining < 0:
        return "critical"
    elif days_remaining < 7:
        return "urgent"
    elif days_remaining < 30:
        return "moderate"
    else:
        return "ok"


def _build_version_check_nrql(
    object_name: str, vault_name: str, since: str = "30 days ago"
) -> str:
    """Build NRQL query to check for SecretNewVersionCreated events since expiration notification."""
    safe_name = object_name.replace("'", "''")
    safe_vault = vault_name.replace("'", "''")
    return (
        f"FROM AzureKeyVaultEvent "
        f"SELECT count(*) AS newVersionEventCount "
        f"WHERE objectName = '{safe_name}' "
        f"AND vaultName = '{safe_vault}' "
        f"AND eventType = 'Microsoft.KeyVault.SecretNewVersionCreated' "
        f"SINCE {since} "
        f"LIMIT 1"
    )


def _extract_facet_str(facet: Any) -> str:
    """Extract facet value, handling both string and list formats."""
    if isinstance(facet, list):
        return facet[0] if facet else ""
    return str(facet) if facet is not None else ""


def _render_summary_table(rows: List[Dict[str, Any]]) -> None:
    """Render grouped summary table for expiring secrets."""
    if not rows:
        print("No expiring secrets found in the specified business unit.")
        return

    col_count = len("Count")

    header = (
        f"{'Count':>{col_count}}  "
        f"Total Secrets in Digital Business Unit"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    for row in rows:
        count = row.get("secretCount") or 0
        print(f"{count:>{col_count}}  secrets")

    print(sep)


def _render_detail_table(rows: List[Dict[str, Any]]) -> None:
    """Render detailed table for individual secrets."""
    if not rows:
        print("No secrets found.")
        return

    col_object = max(len("Secret"), max(len(_extract_facet_str((r.get("facet") or [])[0])) for r in rows))
    col_vault = max(len("Vault"), max(len(_extract_facet_str((r.get("facet") or [])[1])) for r in rows))
    col_days = len("Days Remaining")

    header = (
        f"{'Secret':<{col_object}}  "
        f"{'Vault':<{col_vault}}  "
        f"{'Days Remaining':>{col_days}}  "
        f"Urgency"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    for row in sorted(rows, key=lambda r: _extract_facet_str((r.get("facet") or [])[0])):
        facet = row.get("facet") or []
        object_name = facet[0] if len(facet) > 0 else ""
        vault_name = facet[1] if len(facet) > 1 else ""

        days_remaining = row.get("daysUntilExpiry") or 0
        urgency = _classify_urgency(days_remaining)

        print(
            f"{object_name:<{col_object}}  "
            f"{vault_name:<{col_vault}}  "
            f"{days_remaining:>{col_days}}  "
            f"{urgency:<8}"
        )

    print(sep)
    print(f"Total: {len(rows)} secrets")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report expiring Azure Key Vault secrets in Digital business unit.",
    )
    parser.add_argument(
        "--account-id", type=int, default=DEFAULT_ACCOUNT_ID,
        help=f"New Relic account ID (default: {DEFAULT_ACCOUNT_ID})"
    )
    parser.add_argument(
        "--business-unit", default=DEFAULT_BUSINESS_UNIT,
        help=f"Business unit filter (default: {DEFAULT_BUSINESS_UNIT})"
    )
    parser.add_argument(
        "--mode", choices=["summary", "detail"], default="summary",
        help="Output mode: summary (by urgency) or detail (per secret)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output machine-readable JSON format"
    )
    parser.add_argument(
        "--include-ok", action="store_true",
        help="Include secrets with >30 days remaining in detail mode"
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    # Ensure UTF-8 output on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    bootstrap(include_auth=True)

    from newrelic_client import NewRelicClient

    client = NewRelicClient.from_env()

    if args.mode == "summary":
        nrql = _build_summary_nrql(args.business_unit)
        rows = client.run_nrql(account_id=args.account_id, nrql=nrql)

        if args.json:
            output = {
                "mode": "summary",
                "business_unit": args.business_unit,
                "account_id": args.account_id,
                "rows": rows,
            }
            print(json.dumps(output, indent=2))
        else:
            _render_summary_table(rows)

    else:  # detail mode
        nrql = _build_detail_nrql(args.business_unit)
        rows = client.run_nrql(account_id=args.account_id, nrql=nrql)

        # Filter out "ok" status unless requested
        if not args.include_ok:
            filtered = []
            for row in rows:
                days = row.get("daysUntilExpiry") or 0
                if _classify_urgency(days) != "ok":
                    filtered.append(row)
            rows = filtered

        if args.json:
            output = {
                "mode": "detail",
                "business_unit": args.business_unit,
                "account_id": args.account_id,
                "rows": rows,
            }
            print(json.dumps(output, indent=2))
        else:
            _render_detail_table(rows)

    return 0


if __name__ == "__main__":
    sys.exit(main())
