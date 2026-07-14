#!/usr/bin/env python3
"""List Confluence pages from the configured space."""

from __future__ import annotations

import argparse
import json

from common import bootstrap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List Confluence pages in configured space")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of pages")
    parser.add_argument("--start", type=int, default=0, help="Pagination start offset")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap()

    from confluence_client import ConfluenceClient  # pylint: disable=import-error

    client = ConfluenceClient.from_env()
    pages = client.list_space_pages(limit=args.limit, start=args.start)

    summaries = []
    for page in pages:
        summaries.append(
            {
                "id": page.get("id"),
                "title": page.get("title"),
                "type": page.get("type"),
                "space": (page.get("space") or {}).get("key"),
                "version": ((page.get("version") or {}).get("number")),
            }
        )

    print(json.dumps({"space_keys": client.config.space_keys, "results": summaries}, indent=2))


if __name__ == "__main__":
    main()
