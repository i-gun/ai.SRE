#!/usr/bin/env python3
"""Search New Relic Log events across configured accounts."""

from __future__ import annotations

import argparse
import json

from common import bootstrap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search New Relic logs across configured accounts")
    parser.add_argument("--message", default="", help="Filter: message contains this text")
    parser.add_argument("--severity", default=None, help="Filter: log level (e.g. ERROR, CRITICAL)")
    parser.add_argument("--service", default=None, help="Filter: service.name attribute")
    parser.add_argument("--since", default="1 hour ago", help="NRQL SINCE clause (default: '1 hour ago')")
    parser.add_argument("--limit", type=int, default=100, help="Maximum results per account")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap()

    from newrelic_client import NewRelicClient  # pylint: disable=import-error

    client = NewRelicClient.from_env()
    results_by_account = client.search_logs(
        message_contains=args.message,
        severity=args.severity,
        service=args.service,
        since=args.since,
        limit=args.limit,
    )

    output = {
        "account_ids": client.config.account_ids,
        "since": args.since,
        "results": {
            str(account_id): rows
            for account_id, rows in results_by_account.items()
        },
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
