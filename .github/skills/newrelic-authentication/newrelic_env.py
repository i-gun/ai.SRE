"""New Relic environment configuration loader and validator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


class NewRelicAuthConfigError(Exception):
    """Raised when New Relic authentication configuration is invalid."""


@dataclass
class NewRelicAuthConfig:
    api_key: str
    account_ids: List[int] = field(default_factory=list)


def load_newrelic_auth_config_from_env() -> NewRelicAuthConfig:
    api_key = os.getenv("NEWRELIC_API_KEY", "").strip()
    account_ids_raw = os.getenv("NEWRELIC_ACCOUNT_IDS", "").strip()

    missing = [
        name
        for name, value in [
            ("NEWRELIC_API_KEY", api_key),
            ("NEWRELIC_ACCOUNT_IDS", account_ids_raw),
        ]
        if not value
    ]

    if missing:
        raise NewRelicAuthConfigError(
            "Missing required New Relic environment variables: " + ", ".join(missing)
        )

    account_ids: List[int] = []
    for raw in account_ids_raw.split(","):
        token = raw.strip()
        if not token:
            continue
        if not token.lstrip("-").isdigit() or int(token) <= 0:
            raise NewRelicAuthConfigError(
                f"NEWRELIC_ACCOUNT_IDS contains an invalid account ID: '{token}'. "
                "Each ID must be a positive integer."
            )
        account_ids.append(int(token))

    if not account_ids:
        raise NewRelicAuthConfigError(
            "NEWRELIC_ACCOUNT_IDS must contain at least one positive integer account ID."
        )

    return NewRelicAuthConfig(
        api_key=api_key,
        account_ids=account_ids,
    )
