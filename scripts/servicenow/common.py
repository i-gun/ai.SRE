#!/usr/bin/env python3
"""Shared bootstrap helpers for ServiceNow operational scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INCIDENT_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-incident-operations"
AUTH_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-authentication"


def _load_env_raw(env_path: Path) -> None:
    """Load .env without python-dotenv to preserve special characters.

    python-dotenv silently strips trailing '#' characters (treating them as
    inline comments) from unquoted values.  This causes authentication failures
    when the password ends with '#'.  Reading the file directly and calling
    os.environ avoids that pitfall.
    """
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            # Strip surrounding double or single quotes (dotenv-style quoting).
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            os.environ.setdefault(key, value)


def bootstrap(*, include_auth: bool = False) -> Path:
    """Load .env and register skill import paths for local script execution."""
    _load_env_raw(PROJECT_ROOT / ".env")

    skill_paths = [INCIDENT_SKILL_PATH]
    if include_auth:
        skill_paths.append(AUTH_SKILL_PATH)

    for path in skill_paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    return PROJECT_ROOT
