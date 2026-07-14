"""Jira Cloud environment configuration loader and validator."""

from __future__ import annotations

import os
from dataclasses import dataclass


class JiraAuthConfigError(Exception):
    """Raised when Jira authentication configuration is invalid."""


@dataclass
class JiraAuthConfig:
    host: str
    username: str
    api_token: str


def load_jira_auth_config_from_env() -> JiraAuthConfig:
    host = os.getenv("JIRA_HOST", "").strip()
    username = os.getenv("JIRA_USERNAME", "").strip()
    api_token = os.getenv("JIRA_API_TOKEN", "").strip()

    missing = [
        name
        for name, value in [
            ("JIRA_HOST", host),
            ("JIRA_USERNAME", username),
            ("JIRA_API_TOKEN", api_token),
        ]
        if not value
    ]

    if missing:
        raise JiraAuthConfigError(
            "Missing required Jira environment variables: " + ", ".join(missing)
        )

    if not (host.startswith("http://") or host.startswith("https://")):
        raise JiraAuthConfigError("JIRA_HOST must start with http:// or https://")

    return JiraAuthConfig(
        host=host.rstrip("/"),
        username=username,
        api_token=api_token,
    )