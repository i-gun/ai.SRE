#!/usr/bin/env python3
"""Build a comprehensive JSON mapping of email folders in the user's Outlook mailbox."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bootstrap_shared import PROJECT_ROOT, bootstrap_paths  # noqa: E402

bootstrap_paths(
    skill_paths=[
        PROJECT_ROOT / ".github" / "skills" / "emailer-mail-operations",
        PROJECT_ROOT / ".github" / "skills" / "emailer-connection",
    ]
)

from outlook_client import OutlookClient  # noqa: E402


def parse_folder_tree(folder: Any, store_name: str, parent_path: str = "") -> List[Dict[str, Any]]:
    folder_name = folder.Name
    if parent_path:
        relative_path = f"{parent_path}/{folder_name}"
    else:
        relative_path = folder_name

    full_path = f"{store_name}/{relative_path}"

    items = getattr(folder, "Items", None)
    item_count = len(items) if items is not None else 0
    unread_count = getattr(folder, "UnReadItemCount", 0)

    subfolders = getattr(folder, "Folders", [])
    subfolder_names = [sf.Name for sf in subfolders]

    folder_entry: Dict[str, Any] = {
        "name": folder_name,
        "relative_path": relative_path,
        "full_path": full_path,
        "store_name": store_name,
        "item_count": item_count,
        "unread_count": unread_count,
        "subfolders": subfolder_names,
    }

    results = [folder_entry]

    for subfolder in subfolders:
        try:
            results.extend(parse_folder_tree(subfolder, store_name, relative_path))
        except Exception as exc:
            print(f"Warning: Failed to process subfolder {subfolder.Name} in {relative_path}: {exc}", file=sys.stderr)

    return results


def build_mailbox_folder_map(output_path: Path, include_all_stores: bool = True) -> Dict[str, Any]:
    client = OutlookClient.from_env()
    primary_mailbox = client.signed_in_address

    stores_info = []
    all_folders: List[Dict[str, Any]] = []

    for store in client._namespace.Stores:
        store_name = store.DisplayName
        is_primary = store_name.lower() == primary_mailbox.lower()

        if not include_all_stores and not is_primary:
            continue

        try:
            root_folder = store.GetRootFolder()
        except Exception as exc:
            print(f"Warning: Could not access root folder for store '{store_name}': {exc}", file=sys.stderr)
            continue

        store_folders: List[Dict[str, Any]] = []
        for subfolder in root_folder.Folders:
            try:
                store_folders.extend(parse_folder_tree(subfolder, store_name, ""))
            except Exception as exc:
                print(f"Warning: Failed processing top-level folder {subfolder.Name} in store {store_name}: {exc}", file=sys.stderr)

        stores_info.append(
            {
                "store_name": store_name,
                "is_primary": is_primary,
                "folder_count": len(store_folders),
                "total_items": sum(f["item_count"] for f in store_folders),
                "total_unread": sum(f["unread_count"] for f in store_folders),
            }
        )
        all_folders.extend(store_folders)

    primary_folders = [f for f in all_folders if f["store_name"].lower() == primary_mailbox.lower()]

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_mailbox": primary_mailbox,
        "summary": {
            "primary_mailbox_folder_count": len(primary_folders),
            "primary_mailbox_item_count": sum(f["item_count"] for f in primary_folders),
            "primary_mailbox_unread_count": sum(f["unread_count"] for f in primary_folders),
            "total_stores_scanned": len(stores_info),
            "total_folders_scanned": len(all_folders),
        },
        "stores": stores_info,
        "folders": all_folders,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "emailer_folder_map.json",
        help="Target output file path for the folder map JSON",
    )
    parser.add_argument(
        "--primary-only",
        action="store_true",
        help="Scan primary mailbox store only, excluding archive or public stores",
    )
    args = parser.parse_args()

    print(f"Scanning Outlook mailbox stores...")
    folder_map = build_mailbox_folder_map(args.output, include_all_stores=not args.primary_only)

    print(f"Successfully generated folder map at: {args.output}")
    print(f"Primary Mailbox: {folder_map['primary_mailbox']}")
    print(f"Primary Folders Scanned: {folder_map['summary']['primary_mailbox_folder_count']}")
    print(f"Primary Total Items: {folder_map['summary']['primary_mailbox_item_count']}")
    print(f"Primary Unread Items: {folder_map['summary']['primary_mailbox_unread_count']}")
    print(f"Total Folders (all stores): {folder_map['summary']['total_folders_scanned']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
