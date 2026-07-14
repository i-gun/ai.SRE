"""Azure DevOps Git environment configuration loader and validator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Set


class AzureGitAuthConfigError(Exception):
    """Raised when AzureGit authentication configuration is invalid."""


@dataclass
class AzureGitAuthConfig:
    organization: str
    projects: List[str] = field(default_factory=list)
    pat: str = ""
    api_version: str = "7.1"


def load_azuregit_auth_config_from_env() -> AzureGitAuthConfig:
    organization = os.getenv("AZURE_ORG", "").strip()
    projects_raw = os.getenv("AZURE_PROJECT", "").strip()
    pat = os.getenv("AZURE_PAT", "").strip()
    api_version = _normalize_api_version(os.getenv("AZURE_API_VERSION", ""))

    missing = [
        name
        for name, value in [
            ("AZURE_ORG", organization),
            ("AZURE_PROJECT", projects_raw),
            ("AZURE_PAT", pat),
        ]
        if not value
    ]
    if missing:
        raise AzureGitAuthConfigError(
            "Missing required AzureGit environment variables: " + ", ".join(missing)
        )

    projects = _parse_projects(projects_raw)
    if not projects:
        raise AzureGitAuthConfigError(
            "AZURE_PROJECT must include at least one project name."
        )

    return AzureGitAuthConfig(
        organization=organization,
        projects=projects,
        pat=pat,
        api_version=api_version,
    )


def _parse_projects(raw_value: str) -> List[str]:
    parsed: List[str] = []
    seen: Set[str] = set()
    for item in raw_value.split(","):
        value = item.strip()
        if not value or value in seen:
            continue
        parsed.append(value)
        seen.add(value)
    return parsed


def _normalize_api_version(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return "7.1"
    return value
