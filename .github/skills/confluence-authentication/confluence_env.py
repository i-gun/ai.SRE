"""Confluence Cloud environment configuration loader and validator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


class ConfluenceAuthConfigError(Exception):
    """Raised when Confluence authentication configuration is invalid."""


@dataclass
class ConfluenceAuthConfig:
    host: str
    username: str
    api_token: str
    space_keys: List[str] = field(default_factory=list)


def load_confluence_auth_config_from_env() -> ConfluenceAuthConfig:
    host = os.getenv("JIRA_HOST", "").strip()
    username = os.getenv("JIRA_USERNAME", "").strip()
    api_token = os.getenv("JIRA_API_TOKEN", "").strip()
    space_keys_raw = os.getenv("CONFLUENCE_SPACE_KEY", "").strip()

    missing = [
        name
        for name, value in [
            ("JIRA_HOST", host),
            ("JIRA_USERNAME", username),
            ("JIRA_API_TOKEN", api_token),
            ("CONFLUENCE_SPACE_KEY", space_keys_raw),
        ]
        if not value
    ]

    if missing:
        raise ConfluenceAuthConfigError(
            "Missing required Confluence environment variables: " + ", ".join(missing)
        )

    if not (host.startswith("http://") or host.startswith("https://")):
        raise ConfluenceAuthConfigError("JIRA_HOST must start with http:// or https://")

    space_keys = [k.strip().upper() for k in space_keys_raw.split(",") if k.strip()]
    if not space_keys:
        raise ConfluenceAuthConfigError(
            "CONFLUENCE_SPACE_KEY must contain at least one non-empty space key."
        )

    return ConfluenceAuthConfig(
        host=host.rstrip("/"),
        username=username,
        api_token=api_token,
        space_keys=space_keys,
    )
