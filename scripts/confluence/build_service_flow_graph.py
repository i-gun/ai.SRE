#!/usr/bin/env python3
"""Build a service-flow graph from Confluence pages."""

from __future__ import annotations

import argparse
import json
from typing import List

from common import bootstrap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build service-flow graph from Confluence")
    parser.add_argument(
        "--page-id",
        action="append",
        dest="page_ids",
        default=[],
        help="Confluence page ID (can be repeated)",
    )
    parser.add_argument(
        "--cql",
        help="Optional CQL query to discover pages before graph generation",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum pages to use when --cql is provided",
    )
    return parser.parse_args()


def resolve_page_ids(client, args: argparse.Namespace) -> List[str]:
    if args.page_ids:
        return args.page_ids

    if not args.cql:
        raise ValueError("Provide at least one --page-id or use --cql for discovery")

    results = client.search_content(cql=args.cql, limit=args.limit, start=0)
    page_ids: List[str] = []
    for row in results:
        content = row.get("content") or {}
        page_id = content.get("id")
        if page_id:
            page_ids.append(str(page_id))

    if not page_ids:
        raise ValueError("No page IDs were resolved from the provided CQL query")

    return page_ids


def main() -> None:
    args = parse_args()
    bootstrap()

    from confluence_client import ConfluenceClient  # pylint: disable=import-error

    client = ConfluenceClient.from_env()
    page_ids = resolve_page_ids(client, args)

    graph = client.build_service_flow_graph(page_ids=page_ids)

    print(json.dumps({
        "space_keys": graph["space_keys"],
        "summary": graph["summary"],
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "adjacency": graph["adjacency"],
    }, indent=2))
    print("\n--- Mermaid ---")
    print(graph["mermaid"])


if __name__ == "__main__":
    main()
