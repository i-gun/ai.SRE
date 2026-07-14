#!/usr/bin/env python3
"""Analyze New Relic log volume trends with optional faceting."""

from __future__ import annotations

import argparse
import json

from common import bootstrap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze New Relic log trends over time")
    parser.add_argument("--message", default="", help="Filter: message contains this text")
    parser.add_argument("--service", default=None, help="Filter: service.name attribute")
    parser.add_argument("--since", default="24 hours ago", help="NRQL SINCE clause (default: '24 hours ago')")
    parser.add_argument("--timeseries", default="10 minutes", help="TIMESERIES bucket size (default: '10 minutes')")
    parser.add_argument("--facet", default=None, help="FACET dimension (e.g. level, service.name)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap()

    from newrelic_client import NewRelicClient  # pylint: disable=import-error

    client = NewRelicClient.from_env()
    trends_by_account = client.analyze_log_trends(
        message_contains=args.message,
        service=args.service,
        since=args.since,
        timeseries=args.timeseries,
        facet=args.facet,
    )

    output = {
        "account_ids": client.config.account_ids,
        "since": args.since,
        "timeseries": args.timeseries,
        "facet": args.facet,
        "trends": {
            str(account_id): rows
            for account_id, rows in trends_by_account.items()
        },
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
