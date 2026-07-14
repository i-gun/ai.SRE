#!/usr/bin/env python3
"""Run automated root cause analysis for a service using New Relic log data."""

from __future__ import annotations

import argparse
import json

from common import bootstrap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run New Relic root cause analysis for a service")
    parser.add_argument("--service", required=True, help="Service name to analyze (matches service.name attribute)")
    parser.add_argument("--since", default="1 hour ago", help="NRQL SINCE clause (default: '1 hour ago')")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap()

    from newrelic_client import NewRelicClient  # pylint: disable=import-error

    client = NewRelicClient.from_env()
    rca = client.root_cause_analysis(
        service=args.service,
        since=args.since,
    )

    print(json.dumps(rca, indent=2, default=str))

    print("\n--- Root Cause ---")
    print(rca.get("root_cause", "N/A"))
    print("\n--- Recommendation ---")
    print(rca.get("recommendation", "N/A"))
    print("\n--- Escalation Points ---")
    for point in rca.get("escalation_points", []):
        print(f"  • {point}")


if __name__ == "__main__":
    main()
