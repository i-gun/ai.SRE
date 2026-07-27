#!/usr/bin/env python3
"""Shared bootstrap helpers for operational scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_raw(env_path: Path, *, override_existing: bool = False) -> None:
    """Load .env without python-dotenv to preserve special characters."""
    if not env_path.exists():
        return

    with env_path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]

            if override_existing:
                os.environ[key] = value
            else:
                os.environ.setdefault(key, value)


def bootstrap_paths(
    *,
    skill_paths: Iterable[Path],
    override_env: bool = False,
) -> Path:
    """Load .env and register import paths for operational scripts."""
    load_env_raw(PROJECT_ROOT / ".env", override_existing=override_env)

    for path in skill_paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    return PROJECT_ROOT