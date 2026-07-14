#!/usr/bin/env python3
"""Search Confluence content with CQL inside the configured space."""

from __future__ import annotations

import argparse
import json

from common import bootstrap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Confluence content with CQL")
    parser.add_argument("--cql", required=True, help="Confluence CQL expression")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of results")
    parser.add_argument("--start", type=int, default=0, help="Pagination start offset")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap()

    from confluence_client import ConfluenceClient  # pylint: disable=import-error

    client = ConfluenceClient.from_env()
    results = client.search_content(cql=args.cql, limit=args.limit, start=args.start)

    summaries = []
    for row in results:
        content = row.get("content") or {}
        summaries.append(
            {
                "result_type": row.get("resultType"),
                "id": content.get("id"),
                "title": content.get("title"),
                "space": ((content.get("space") or {}).get("key")),
                "version": ((content.get("version") or {}).get("number")),
            }
        )

    print(json.dumps({"space_keys": client.config.space_keys, "results": summaries}, indent=2))


if __name__ == "__main__":
    main()
