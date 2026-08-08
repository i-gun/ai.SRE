#!/usr/bin/env python3
"""Inspect and back up New Relic dashboard tabs for repeatable analyses."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from common import bootstrap

DASHBOARD_GUIDS = {
    "Checkout": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDE0MDgwOTQ0",
    "APIM": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDM3MzA2MDY3",
    "AZ Functions": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDE1OTc0NTQ0",
    "AZ Service Bus": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDE0ODc2MTE5",
    "Bots": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDI1OTcyNjM1",
    "CCv2": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDE3MDU5NTM1",
    "CCv2 RC": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDM2NDk3NTUy",
    "CDS": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDE1NTEzMDI0",
    "CTFS": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDM0NTQzNjY1",
    "geo": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDM1NjI3MTg1",
    "Gigya": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDM0NTA5MDEx",
    "Inventory": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDM3MTAxMzU2",
    "PPE/DTE": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDE0MDgwOTUw",
    "Search": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDI3NTAzODY1",
    "Sessions": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDE1MTg3Nzg5",
    "SFSC": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDM1MzUzOTI4",
    "Spoiled Pods": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDIzNjgyNzMy",
    "Vulnerabilities": "MTY3OTgwMnxWSVp8REFTSEJPQVJEfDQzNzE0Njg4",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Back up and inspect New Relic dashboard tabs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-tabs", help="List configured dashboard tab names")

    fetch = subparsers.add_parser("fetch-tab", help="Fetch a single tab from New Relic")
    fetch.add_argument("--tab", required=True, help="Tab name from configured list")
    fetch.add_argument("--raw", action="store_true", help="Print raw GraphQL payload")

    backup = subparsers.add_parser("backup", help="Back up all configured tabs to JSON")
    backup.add_argument(
        "--output-file",
        default=f"artifacts/nr_dashboard_backup_checkout_order_{date.today()}.json",
        help="Backup output path (default under artifacts/)",
    )

    show = subparsers.add_parser("show", help="Show widget details from a backup file")
    show.add_argument("--backup-file", required=True, help="Backup JSON file path")
    show.add_argument("--tab", required=True, help="Tab name to display")

    return parser.parse_args()


def get_api_key() -> str:
    bootstrap(include_auth=True)
    api_key = os.getenv("NEWRELIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing NEWRELIC_API_KEY in environment.")
    return api_key


def graphql_query(guid: str) -> str:
    return (
        "{"
        " actor {"
        f'  entity(guid: \"{guid}\") {{'
        "   ... on DashboardEntity {"
        "    name"
        "    description"
        "    pages {"
        "      name"
        "      description"
        "      widgets {"
        "        title"
        "        visualization { id }"
        "        rawConfiguration"
        "      }"
        "    }"
        "   }"
        "  }"
        " }"
        "}"
    )


def fetch_dashboard(guid: str, api_key: str) -> Dict[str, Any]:
    response = requests.post(
        "https://api.newrelic.com/graphql",
        headers={"API-Key": api_key, "Content-Type": "application/json"},
        json={"query": graphql_query(guid)},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def parse_nrql_preview(raw_configuration: Any) -> str:
    config = raw_configuration
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except Exception:  # pylint: disable=broad-except
            return ""

    if not isinstance(config, dict):
        return ""

    for query in config.get("nrqlQueries") or []:
        text = str(query.get("query") or "").strip()
        if text:
            return text[:160]
    return ""


def entity_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return (payload.get("data") or {}).get("actor", {}).get("entity") or {}


def command_list_tabs() -> None:
    print(json.dumps({"tabs": sorted(DASHBOARD_GUIDS.keys())}, indent=2))


def command_fetch_tab(args: argparse.Namespace) -> None:
    guid = DASHBOARD_GUIDS.get(args.tab)
    if not guid:
        raise RuntimeError(f"Unknown tab '{args.tab}'.")

    api_key = get_api_key()
    payload = fetch_dashboard(guid, api_key)
    entity = entity_from_payload(payload)

    if args.raw:
        print(json.dumps(payload, indent=2))
        return

    pages = entity.get("pages", []) or []
    out_pages: List[Dict[str, Any]] = []
    for page in pages:
        widgets = page.get("widgets", []) or []
        out_pages.append(
            {
                "name": page.get("name"),
                "widget_count": len(widgets),
                "widgets": [
                    {
                        "title": widget.get("title") or "(no title)",
                        "visualization": (widget.get("visualization") or {}).get("id"),
                        "nrql_preview": parse_nrql_preview(widget.get("rawConfiguration")),
                    }
                    for widget in widgets
                ],
            }
        )

    print(
        json.dumps(
            {
                "tab": args.tab,
                "guid": guid,
                "entity_name": entity.get("name"),
                "page_count": len(pages),
                "pages": out_pages,
            },
            indent=2,
        )
    )


def command_backup(args: argparse.Namespace) -> None:
    api_key = get_api_key()
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    backup: Dict[str, Any] = {
        "dashboard": "Checkout/Order",
        "generated_on": date.today().isoformat(),
        "tabs": {},
    }

    for tab_name, guid in DASHBOARD_GUIDS.items():
        payload = fetch_dashboard(guid, api_key)
        entity = entity_from_payload(payload)
        backup["tabs"][tab_name] = {
            "guid": guid,
            "entity_name": entity.get("name"),
            "pages": entity.get("pages", []) or [],
            "errors": payload.get("errors") or [],
        }

    output_path.write_text(json.dumps(backup, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "command": "backup",
                "output_file": str(output_path),
                "tab_count": len(backup["tabs"]),
            },
            indent=2,
        )
    )


def command_show(args: argparse.Namespace) -> None:
    backup_path = Path(args.backup_file)
    if not backup_path.exists():
        raise RuntimeError(f"Backup file not found: {backup_path}")

    payload = json.loads(backup_path.read_text(encoding="utf-8"))
    tabs = payload.get("tabs") or {}
    tab = tabs.get(args.tab)
    if not isinstance(tab, dict):
        raise RuntimeError(f"Tab '{args.tab}' not found in backup.")

    pages = tab.get("pages", []) or []
    out_pages: List[Dict[str, Any]] = []
    for page in pages:
        widgets = page.get("widgets", []) or []
        out_pages.append(
            {
                "name": page.get("name"),
                "widget_count": len(widgets),
                "widgets": [
                    {
                        "title": widget.get("title") or "(no title)",
                        "visualization": (widget.get("visualization") or {}).get("id"),
                        "nrql_preview": parse_nrql_preview(widget.get("rawConfiguration")),
                    }
                    for widget in widgets
                ],
            }
        )

    print(
        json.dumps(
            {
                "command": "show",
                "backup_file": str(backup_path),
                "tab": args.tab,
                "entity_name": tab.get("entity_name"),
                "page_count": len(pages),
                "pages": out_pages,
            },
            indent=2,
        )
    )


def main() -> None:
    args = parse_args()
    if args.command == "list-tabs":
        command_list_tabs()
    elif args.command == "fetch-tab":
        command_fetch_tab(args)
    elif args.command == "backup":
        command_backup(args)
    elif args.command == "show":
        command_show(args)
    else:
        raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
