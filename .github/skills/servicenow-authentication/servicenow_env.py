"""ServiceNow environment configuration loader and validator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Set
from urllib.parse import urlsplit


class ServiceNowAuthConfigError(Exception):
    """Raised when ServiceNow authentication configuration is invalid."""


@dataclass
class ServiceNowAuthConfig:
    host: str
    username: str
    password: str = field(repr=False)
    assignment_groups: List[str]
    auth_mode: str = "basic"
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    token_url: str = ""
    oauth_scope: str = ""
    oauth_client_auth_method: str = "client_secret_post"

    def __post_init__(self) -> None:
        if self.auth_mode not in {"basic", "oauth_client_credentials"}:
            raise ServiceNowAuthConfigError("Unsupported SERVICENOW_AUTH_MODE")
        if self.auth_mode == "basic":
            return
        if not self.client_id or not self.client_secret:
            raise ServiceNowAuthConfigError(
                "OAuth requires SERVICENOW_CLIENT_ID and SERVICENOW_CLIENT_SECRET"
            )
        if self.oauth_client_auth_method not in {
            "client_secret_post", "client_secret_basic"
        }:
            raise ServiceNowAuthConfigError("Unsupported SERVICENOW_OAUTH_CLIENT_AUTH_METHOD")
        self.token_url = self.token_url or f"{self.host.rstrip('/')}/oauth_token.do"
        host_parts = urlsplit(self.host)
        token_parts = urlsplit(self.token_url)
        if (
            host_parts.scheme != "https"
            or token_parts.scheme != "https"
            or not host_parts.netloc
            or host_parts.netloc != token_parts.netloc
            or host_parts.username is not None
            or token_parts.username is not None
            or token_parts.query or token_parts.fragment
        ):
            raise ServiceNowAuthConfigError("OAuth requires HTTPS and a same-origin token URL")


def load_servicenow_auth_config_from_env() -> ServiceNowAuthConfig:
    host = os.getenv("SERVICENOW_HOST", "").strip()
    username = os.getenv("SERVICENOW_USERNAME", "").strip()
    password = os.getenv("SERVICENOW_PASSWORD", "").strip()
    assignment_groups_raw = os.getenv("SERVICENOW_ASSIGNMENT_GROUPS", "").strip()
    assignment_groups = _parse_assignment_groups(assignment_groups_raw)
    auth_mode = os.getenv("SERVICENOW_AUTH_MODE", "basic").strip().lower()

    missing = [
        name
        for name, value in [
            ("SERVICENOW_HOST", host),
            ("SERVICENOW_USERNAME", username if auth_mode == "basic" else "unused"),
            ("SERVICENOW_PASSWORD", password if auth_mode == "basic" else "unused"),
            ("SERVICENOW_ASSIGNMENT_GROUPS", assignment_groups_raw),
        ]
        if not value
    ]

    if missing:
        raise ServiceNowAuthConfigError(
            "Missing required ServiceNow environment variables: " + ", ".join(missing)
        )

    if not (host.startswith("http://") or host.startswith("https://")):
        raise ServiceNowAuthConfigError(
            "SERVICENOW_HOST must start with http:// or https://"
        )

    if not assignment_groups:
        raise ServiceNowAuthConfigError(
            "SERVICENOW_ASSIGNMENT_GROUPS must include at least one assignment group."
        )

    return ServiceNowAuthConfig(
        host=host.rstrip("/"),
        username=username,
        password=password,
        assignment_groups=assignment_groups,
        auth_mode=auth_mode,
        client_id=os.getenv("SERVICENOW_CLIENT_ID", "").strip(),
        client_secret=os.getenv("SERVICENOW_CLIENT_SECRET", ""),
        token_url=os.getenv("SERVICENOW_TOKEN_URL", "").strip(),
        oauth_scope=os.getenv("SERVICENOW_OAUTH_SCOPE", "").strip(),
        oauth_client_auth_method=os.getenv(
            "SERVICENOW_OAUTH_CLIENT_AUTH_METHOD", "client_secret_post"
        ).strip().lower(),
    )


def _parse_assignment_groups(raw_value: str) -> List[str]:
    parsed: List[str] = []
    seen: Set[str] = set()
    for item in raw_value.split(","):
        value = item.strip()
        if not value or value in seen:
            continue
        parsed.append(value)
        seen.add(value)
    return parsed
