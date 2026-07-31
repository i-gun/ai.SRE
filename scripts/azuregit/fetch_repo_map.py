#!/usr/bin/env python3
"""Fetch and cache Azure DevOps project/repository mapping."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from common import bootstrap


def parse_args() -> argparse.Namespace:
    env_default_max_age = os.getenv("AZURE_REPO_MAP_MAX_AGE_HOURS", "24").strip()
    try:
        default_max_age = float(env_default_max_age)
    except ValueError:
        default_max_age = 24.0

    parser = argparse.ArgumentParser(
        description=(
            "Fetch Azure DevOps repositories for configured projects and persist "
            "artifacts/azuregit_repo_map.json"
        )
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path. Defaults to artifacts/azuregit_repo_map.json",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Always call Azure DevOps API and overwrite existing mapping.",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=default_max_age,
        help=(
            "Refresh when existing mapping is older than this threshold "
            "(default: AZURE_REPO_MAP_MAX_AGE_HOURS or 24)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print resulting mapping JSON to stdout after write.",
    )
    return parser.parse_args()


def _resolve_output_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    return Path(raw_path).expanduser().resolve()


def _count_repositories(mapping: dict) -> int:
    projects = mapping.get("projects", {})
    if not isinstance(projects, dict):
        return 0
    total = 0
    for repos in projects.values():
        if isinstance(repos, list):
            total += len(repos)
    return total


def main() -> None:
    bootstrap()

    from azuregit_client import AzureGitClient  # pylint: disable=import-error

    args = parse_args()
    output_path = _resolve_output_path(args.output)
    client = AzureGitClient.from_env()
    mapping = client.ensure_repository_map(
        output_file=output_path,
        force_refresh=args.force_refresh,
        max_age_hours=args.max_age_hours,
    )

    target_path = output_path or client.default_repo_map_path()
    project_count = len(mapping.get("projects", {}))
    repository_count = _count_repositories(mapping)

    print(f"Organization: {mapping.get('organization', '')}")
    print(f"Generated At: {mapping.get('generated_at', '')}")
    print(f"Projects: {project_count}")
    print(f"Repositories: {repository_count}")
    print(f"Output: {target_path}")

    if args.json:
        print(json.dumps(mapping, indent=2))


if __name__ == "__main__":
    main()
