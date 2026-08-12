#!/usr/bin/env python3
"""Shared Jira auth/bootstrap and HTTP JSON request helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth

from bootstrap_shared import bootstrap_paths


PROJECT_ROOT = Path(__file__).resolve().parents[2]
JIRA_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "jira-issue-operations"


def load_config() -> Tuple[str, HTTPBasicAuth]:
    bootstrap_paths(skill_paths=[JIRA_SKILL_PATH], override_env=True)

    host = os.getenv("JIRA_HOST", "").strip().rstrip("/")
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
        raise RuntimeError(f"Missing Jira credentials: {', '.join(missing)}")

    return host, HTTPBasicAuth(username, api_token)


def request_json(
    method: str,
    host: str,
    auth: HTTPBasicAuth,
    path: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"

    response = requests.request(
        method,
        f"{host}{path}",
        auth=auth,
        headers=headers,
        json=payload,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    if not response.text:
        return {}
    return response.json()
