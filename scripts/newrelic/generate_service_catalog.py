#!/usr/bin/env python3
"""Generate local New Relic APM service catalog files for mapping workflows."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

from common import bootstrap


DEFAULT_ACCOUNT_ID = 1679802
DEFAULT_SINCE = "30 days ago"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate local New Relic service catalog files under data/ for "
            "AzureGit and Confluence mapping workflows."
        )
    )
    parser.add_argument(
        "--account-id",
        type=int,
        default=DEFAULT_ACCOUNT_ID,
        help=(
            "New Relic account ID to query (default: 1679802). "
            "Must be included in NEWRELIC_ACCOUNT_IDS."
        ),
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        help=(
            "NRQL SINCE clause value for source queries "
            "(default: '30 days ago')."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Output directory for generated files (default: data)",
    )
    parser.add_argument(
        "--pretty-json",
        action="store_true",
        help="Write JSON output with indentation for readability.",
    )
    return parser.parse_args(argv)


def _extract_strings_from_rows(rows: List[Dict[str, Any]]) -> Set[str]:
    names: Set[str] = set()

    for row in rows:
        for value in row.values():
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    names.add(cleaned)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        cleaned = item.strip()
                        if cleaned:
                            names.add(cleaned)

    return names


def collect_service_names(client: Any, account_id: int, since: str) -> Tuple[List[str], Dict[str, int]]:
    """Collect and merge service names from multiple NRQL sources."""
    source_queries = {
        "transaction_entity_name": (
            "SELECT uniques(entity.name) "
            f"FROM Transaction SINCE {since} LIMIT MAX"
        ),
        "log_service_name": (
            "SELECT uniques(service.name) "
            f"FROM Log SINCE {since} LIMIT MAX"
        ),
    }

    merged: Set[str] = set()
    source_counts: Dict[str, int] = {}

    for source_name, nrql in source_queries.items():
        rows = client.run_nrql(account_id=account_id, nrql=nrql)
        names = _extract_strings_from_rows(rows)
        source_counts[source_name] = len(names)
        merged.update(names)

    merged_list = sorted(merged, key=lambda item: item.lower())
    return merged_list, source_counts


def write_txt(path: Path, services: List[str]) -> None:
    path.write_text("\n".join(services) + ("\n" if services else ""), encoding="utf-8")


def write_csv(path: Path, services: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["service_name"])
        for service in services:
            writer.writerow([service])


def write_json(
    path: Path,
    *,
    account_id: int,
    since: str,
    services: List[str],
    source_counts: Dict[str, int],
    pretty: bool,
) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_id": account_id,
        "since": since,
        "service_count": len(services),
        "source_counts": source_counts,
        "services": services,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)
        f.write("\n")


def main() -> None:
    args = parse_args()
    bootstrap()

    from newrelic_client import NewRelicClient  # pylint: disable=import-error

    client = NewRelicClient.from_env()

    if args.account_id not in client.config.account_ids:
        allowed = ", ".join(str(item) for item in client.config.account_ids)
        raise ValueError(
            "--account-id must be present in NEWRELIC_ACCOUNT_IDS. "
            f"Received {args.account_id}; configured accounts: {allowed}"
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    services, source_counts = collect_service_names(
        client=client,
        account_id=args.account_id,
        since=args.since,
    )

    txt_path = output_dir / f"newrelic_apm_service_names_{args.account_id}.txt"
    csv_path = output_dir / f"newrelic_apm_service_names_{args.account_id}.csv"
    json_path = output_dir / f"newrelic_apm_services_{args.account_id}.json"

    write_txt(txt_path, services)
    write_csv(csv_path, services)
    write_json(
        json_path,
        account_id=args.account_id,
        since=args.since,
        services=services,
        source_counts=source_counts,
        pretty=args.pretty_json,
    )

    summary = {
        "preferred_path": "@NewRelic agent delegation",
        "fallback_path": "scripts/newrelic/generate_service_catalog.py",
        "account_id": args.account_id,
        "since": args.since,
        "service_count": len(services),
        "files": {
            "txt": str(txt_path),
            "csv": str(csv_path),
            "json": str(json_path),
        },
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
