#!/usr/bin/env python3
"""Shared bootstrap helpers for Confluence operational scripts."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_SKILL_PATH = (
    PROJECT_ROOT / ".github" / "skills" / "confluence-knowledge-operations"
)
AUTH_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "confluence-authentication"


def bootstrap(*, include_auth: bool = False) -> Path:
    """Load .env and register skill import paths for local script execution."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    skill_paths = [KNOWLEDGE_SKILL_PATH]
    if include_auth:
        skill_paths.append(AUTH_SKILL_PATH)

    for path in skill_paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    return PROJECT_ROOT
