"""ServiceNow environment configuration loader and validator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Set


class ServiceNowAuthConfigError(Exception):
    """Raised when ServiceNow authentication configuration is invalid."""


@dataclass
class ServiceNowAuthConfig:
    host: str
    username: str
    password: str
    assignment_groups: List[str]


def load_servicenow_auth_config_from_env() -> ServiceNowAuthConfig:
    host = os.getenv("SERVICENOW_HOST", "").strip()
    username = os.getenv("SERVICENOW_USERNAME", "").strip()
    password = os.getenv("SERVICENOW_PASSWORD", "").strip()
    assignment_groups_raw = os.getenv("SERVICENOW_ASSIGNMENT_GROUPS", "").strip()
    assignment_groups = _parse_assignment_groups(assignment_groups_raw)

    missing = [
        name
        for name, value in [
            ("SERVICENOW_HOST", host),
            ("SERVICENOW_USERNAME", username),
            ("SERVICENOW_PASSWORD", password),
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
