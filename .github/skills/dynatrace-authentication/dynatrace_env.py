"""Dynatrace environment configuration loader and validator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class DynatraceAuthConfigError(Exception):
    """Raised when Dynatrace authentication configuration is invalid."""


@dataclass
class DynatraceAuthConfig:
    environment_url: str
    api_token: str
    username: str


def load_dynatrace_auth_config_from_env() -> DynatraceAuthConfig:
    environment_url = os.getenv("DYNATRACE_ENVIRONMENT_URL", "").strip().rstrip("/")
    api_token = os.getenv("DYNATRACE_API_TOKEN", "").strip()
    username = os.getenv("DYNATRACE_USERNAME", "").strip()

    missing = [
        name
        for name, value in [
            ("DYNATRACE_ENVIRONMENT_URL", environment_url),
            ("DYNATRACE_API_TOKEN", api_token),
            ("DYNATRACE_USERNAME", username),
        ]
        if not value
    ]

    if missing:
        raise DynatraceAuthConfigError(
            "Missing required Dynatrace environment variables: " + ", ".join(missing)
        )

    parsed = urlparse(environment_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise DynatraceAuthConfigError(
            "DYNATRACE_ENVIRONMENT_URL must be an https:// URL with a valid host, "
            f"got: '{environment_url}'"
        )

    return DynatraceAuthConfig(
        environment_url=environment_url,
        api_token=api_token,
        username=username,
    )
