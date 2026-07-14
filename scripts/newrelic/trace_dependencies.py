#!/usr/bin/env python3
"""Trace upstream and downstream service dependencies for a named service."""

from __future__ import annotations

import argparse
import json

from common import bootstrap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace New Relic service dependencies")
    parser.add_argument("--service", required=True, help="Service name to trace (matches service.name attribute)")
    parser.add_argument("--since", default="1 hour ago", help="NRQL SINCE clause (default: '1 hour ago')")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap()

    from newrelic_client import NewRelicClient  # pylint: disable=import-error

    client = NewRelicClient.from_env()
    deps = client.trace_service_dependencies(
        service=args.service,
        since=args.since,
    )

    print(json.dumps(deps, indent=2, default=str))


if __name__ == "__main__":
    main()
