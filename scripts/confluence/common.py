#!/usr/bin/env python3
"""Shared bootstrap helpers for Confluence operational scripts."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
scripts_root_str = str(SCRIPTS_ROOT)
if scripts_root_str not in sys.path:
    sys.path.insert(0, scripts_root_str)

from bootstrap_shared import bootstrap_paths


KNOWLEDGE_SKILL_PATH = (
    PROJECT_ROOT / ".github" / "skills" / "confluence-knowledge-operations"
)
AUTH_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "confluence-authentication"


def bootstrap(*, include_auth: bool = False) -> Path:
    """Load .env and register skill import paths for local script execution."""
    skill_paths = [KNOWLEDGE_SKILL_PATH]
    if include_auth:
        skill_paths.append(AUTH_SKILL_PATH)
    return bootstrap_paths(skill_paths=skill_paths)
