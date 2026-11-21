#!/usr/bin/env python3
"""Shared bootstrap helpers for ServiceNow operational scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
scripts_root_str = str(SCRIPTS_ROOT)
if scripts_root_str not in sys.path:
    sys.path.insert(0, scripts_root_str)

from bootstrap_shared import bootstrap_paths


INCIDENT_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-incident-operations"
AUTH_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-authentication"
SERVICENOW_OVERRIDE_ENV_KEY = "SERVICENOW_OVERRIDE_ENV"
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


def _servicenow_override_env_enabled() -> bool:
    raw_value = _read_dotenv_value(SERVICENOW_OVERRIDE_ENV_KEY)
    if raw_value is None:
        raw_value = os.getenv(SERVICENOW_OVERRIDE_ENV_KEY, "")
    return raw_value.strip().lower() in TRUTHY_ENV_VALUES


def _read_dotenv_value(key_name: str) -> str | None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return None

    with env_path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            if key.strip() != key_name:
                continue

            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            return value

    return None


def bootstrap(*, include_auth: bool = False, override_env: bool = False) -> Path:
    """Load .env and register skill import paths for local script execution."""
    skill_paths = [INCIDENT_SKILL_PATH]
    if include_auth:
        skill_paths.append(AUTH_SKILL_PATH)
    effective_override_env = override_env or _servicenow_override_env_enabled()
    return bootstrap_paths(skill_paths=skill_paths, override_env=effective_override_env)
