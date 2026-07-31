#!/usr/bin/env python3
"""Shared bootstrap helpers for AzureGit operational scripts."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from bootstrap_shared import bootstrap_paths


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AZUREGIT_REPOSITORY_SKILL_PATH = (
    PROJECT_ROOT / ".github" / "skills" / "azuregit-repository-operations"
)


def bootstrap() -> Path:
    """Load .env and register AzureGit skill import path."""
    return bootstrap_paths(skill_paths=[AZUREGIT_REPOSITORY_SKILL_PATH])
