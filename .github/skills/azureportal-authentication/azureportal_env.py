"""AzurePortal authentication and scope configuration."""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


class AzurePortalAuthConfigError(ValueError):
    """Raised when AzurePortal authentication or scope configuration is invalid."""


@dataclass(frozen=True)
class AzureWorkspaceScope:
    workspace_id: str
    resource_id: str
    subscription_id: str


@dataclass(frozen=True)
class AzurePortalAuthConfig:
    auth_mode: str
    tenant_id: str
    subscription_ids: tuple[str, ...]
    workspace_scopes: Mapping[str, AzureWorkspaceScope]
    resource_group_allowlist: tuple[str, ...] = ()
    resource_id_allowlist: tuple[str, ...] = ()
    managed_identity_client_id: str = ""
    service_principal_client_id: str = ""
    service_principal_secret: str = field(default="", repr=False)
    max_window_days: int = 30
    max_rows: int = 500
    max_pages: int = 5
    timeout_seconds: int = 30
    max_concurrent_requests: int = 3

    def authorize_subscription(self, subscription_id: str) -> str:
        normalized = _normalize_uuid(subscription_id, "subscription ID")
        if normalized not in self.subscription_ids:
            raise AzurePortalAuthConfigError(
                f"Subscription '{normalized}' is outside AZUREPORTAL_SUBSCRIPTION_IDS."
            )
        return normalized

    def authorize_workspace(self, workspace_id: str) -> AzureWorkspaceScope:
        normalized = _normalize_uuid(workspace_id, "workspace ID")
        scope = self.workspace_scopes.get(normalized)
        if scope is None:
            raise AzurePortalAuthConfigError(
                f"Workspace '{normalized}' is outside AZUREPORTAL_WORKSPACE_MAP."
            )
        self.authorize_subscription(scope.subscription_id)
        self.authorize_resource_id(scope.resource_id)
        return scope

    def authorize_resource_id(self, resource_id: str) -> str:
        parsed = parse_resource_id(resource_id)
        subscription_id = self.authorize_subscription(parsed["subscription_id"])
        resource_group = parsed["resource_group"]
        if self.resource_group_allowlist and resource_group.lower() not in {
            item.lower() for item in self.resource_group_allowlist
        }:
            raise AzurePortalAuthConfigError(
                f"Resource group '{resource_group}' is outside the configured allowlist."
            )
        normalized_id = "/" + resource_id.strip().strip("/").lower()
        if self.resource_id_allowlist and normalized_id not in {
            "/" + item.strip().strip("/").lower() for item in self.resource_id_allowlist
        }:
            raise AzurePortalAuthConfigError(
                "Resource ID is outside AZUREPORTAL_RESOURCE_IDS."
            )
        if parsed["subscription_id"] != subscription_id:
            raise AzurePortalAuthConfigError("Resource subscription scope is invalid.")
        return "/" + resource_id.strip().strip("/")


def load_azureportal_auth_config_from_env() -> AzurePortalAuthConfig:
    mode = os.getenv("AZUREPORTAL_AUTH_MODE", "").strip().lower()
    if mode not in {"azure_cli", "managed_identity", "service_principal"}:
        raise AzurePortalAuthConfigError(
            "AZUREPORTAL_AUTH_MODE must explicitly be azure_cli, managed_identity, "
            "or service_principal."
        )

    tenant_id = _normalize_uuid(
        os.getenv("AZUREPORTAL_TENANT_ID", "").strip(), "tenant ID"
    )
    subscription_ids = _parse_uuid_list(
        os.getenv("AZUREPORTAL_SUBSCRIPTION_IDS", ""), "AZUREPORTAL_SUBSCRIPTION_IDS"
    )
    if not subscription_ids:
        raise AzurePortalAuthConfigError(
            "AZUREPORTAL_SUBSCRIPTION_IDS must contain at least one subscription."
        )

    resource_groups = _parse_csv(os.getenv("AZUREPORTAL_RESOURCE_GROUPS", ""))
    resource_ids = _parse_csv(os.getenv("AZUREPORTAL_RESOURCE_IDS", ""))
    workspace_scopes = _parse_workspace_map(
        os.getenv("AZUREPORTAL_WORKSPACE_MAP", ""),
        subscription_ids,
        resource_groups,
    )
    for resource_id in resource_ids:
        parsed = parse_resource_id(resource_id)
        if parsed["subscription_id"] not in subscription_ids:
            raise AzurePortalAuthConfigError(
                "AZUREPORTAL_RESOURCE_IDS contains a resource outside "
                "AZUREPORTAL_SUBSCRIPTION_IDS."
            )
        if resource_groups and parsed["resource_group"].lower() not in {
            item.lower() for item in resource_groups
        }:
            raise AzurePortalAuthConfigError(
                "AZUREPORTAL_RESOURCE_IDS contains a resource outside "
                "AZUREPORTAL_RESOURCE_GROUPS."
            )

    managed_client_id = os.getenv(
        "AZUREPORTAL_MANAGED_IDENTITY_CLIENT_ID", ""
    ).strip()
    service_client_id = os.getenv("AZUREPORTAL_CLIENT_ID", "").strip()
    service_secret = os.getenv("AZUREPORTAL_CLIENT_SECRET", "").strip()
    if mode == "service_principal" and not service_client_id:
        raise AzurePortalAuthConfigError(
            "AZUREPORTAL_CLIENT_ID is required for service_principal mode."
        )
    if mode == "service_principal" and not service_secret:
        raise AzurePortalAuthConfigError(
            "AZUREPORTAL_CLIENT_SECRET is required for service_principal mode."
        )
    if mode != "managed_identity" and managed_client_id:
        raise AzurePortalAuthConfigError(
            "AZUREPORTAL_MANAGED_IDENTITY_CLIENT_ID is only valid in managed_identity mode."
        )
    if mode != "service_principal" and (service_client_id or service_secret):
        raise AzurePortalAuthConfigError(
            "AZUREPORTAL_CLIENT_ID and AZUREPORTAL_CLIENT_SECRET are only valid "
            "with service_principal mode."
        )

    return AzurePortalAuthConfig(
        auth_mode=mode,
        tenant_id=tenant_id,
        subscription_ids=tuple(subscription_ids),
        workspace_scopes=workspace_scopes,
        resource_group_allowlist=tuple(resource_groups),
        resource_id_allowlist=tuple(resource_ids),
        managed_identity_client_id=managed_client_id,
        service_principal_client_id=service_client_id,
        service_principal_secret=service_secret,
        max_window_days=_positive_int("AZUREPORTAL_MAX_WINDOW_DAYS", 30, maximum=365),
        max_rows=_positive_int("AZUREPORTAL_MAX_ROWS", 500, maximum=5000),
        max_pages=_positive_int("AZUREPORTAL_MAX_PAGES", 5, maximum=20),
        timeout_seconds=_positive_int(
            "AZUREPORTAL_TIMEOUT_SECONDS", 30, maximum=120
        ),
        max_concurrent_requests=_positive_int(
            "AZUREPORTAL_MAX_CONCURRENT_REQUESTS", 3, maximum=10
        ),
    )


def load_project_environment() -> None:
    """Load only the repository-root .env without overriding process values."""
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise AzurePortalAuthConfigError(
            "AzurePortal requires python-dotenv to load the repository-root .env."
        ) from exc
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env", override=False)


def create_azure_credential(config: AzurePortalAuthConfig):
    """Create exactly the explicitly selected Entra credential type."""
    try:
        from azure.identity import (
            AzureCliCredential,
            ClientSecretCredential,
            ManagedIdentityCredential,
        )
    except ImportError as exc:
        raise AzurePortalAuthConfigError(
            "AzurePortal requires the azure-identity package."
        ) from exc

    if config.auth_mode == "azure_cli":
        return AzureCliCredential(tenant_id=config.tenant_id)
    if config.auth_mode == "managed_identity":
        if config.managed_identity_client_id:
            return ManagedIdentityCredential(
                client_id=config.managed_identity_client_id
            )
        return ManagedIdentityCredential()
    if config.auth_mode == "service_principal":
        return ClientSecretCredential(
            tenant_id=config.tenant_id,
            client_id=config.service_principal_client_id,
            client_secret=config.service_principal_secret,
        )
    raise AzurePortalAuthConfigError(
        "AzurePortal authentication mode was not explicitly selected."
    )


def parse_resource_id(resource_id: str) -> dict[str, str]:
    """Validate a public-cloud Azure resource ID and extract its scope."""
    if not isinstance(resource_id, str) or not resource_id.startswith("/"):
        raise AzurePortalAuthConfigError("Azure resource ID must be an ARM path.")
    if (
        "?" in resource_id
        or "#" in resource_id
        or "\\" in resource_id
        or "%" in resource_id
        or any(ord(char) < 32 for char in resource_id)
    ):
        raise AzurePortalAuthConfigError("Azure resource ID contains invalid syntax.")
    parts = resource_id.strip("/").split("/")
    if (
        len(parts) < 8
        or parts[0].lower() != "subscriptions"
        or parts[2].lower() != "resourcegroups"
        or parts[4].lower() != "providers"
    ):
        raise AzurePortalAuthConfigError(
            "Resource ID must identify a resource under a subscription and resource group."
        )
    subscription_id = _normalize_uuid(parts[1], "resource subscription ID")
    if any(not part or part in {".", ".."} for part in parts):
        raise AzurePortalAuthConfigError("Azure resource ID contains invalid segments.")
    return {
        "subscription_id": subscription_id,
        "resource_group": parts[3],
        "provider": parts[5],
        "resource_type": "/".join(parts[6::2]),
    }


def _parse_workspace_map(
    raw: str, subscription_ids: list[str], resource_groups: list[str]
) -> dict[str, AzureWorkspaceScope]:
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AzurePortalAuthConfigError(
            "AZUREPORTAL_WORKSPACE_MAP must be a JSON object mapping workspace GUIDs "
            "to verified workspace ARM resource IDs."
        ) from exc
    if not isinstance(data, dict):
        raise AzurePortalAuthConfigError(
            "AZUREPORTAL_WORKSPACE_MAP must be a JSON object."
        )

    scopes: dict[str, AzureWorkspaceScope] = {}
    for workspace_id_raw, resource_id_raw in data.items():
        workspace_id = _normalize_uuid(str(workspace_id_raw), "workspace ID")
        if not isinstance(resource_id_raw, str):
            raise AzurePortalAuthConfigError(
                "Workspace map values must be workspace ARM resource IDs."
            )
        parsed = parse_resource_id(resource_id_raw)
        if (
            parsed["subscription_id"] not in subscription_ids
            or parsed["provider"].lower() != "microsoft.operationalinsights"
            or parsed["resource_type"].lower() != "workspaces"
        ):
            raise AzurePortalAuthConfigError(
                "Workspace map must identify an allowed "
                "Microsoft.OperationalInsights/workspaces resource."
            )
        if resource_groups and parsed["resource_group"].lower() not in {
            group.lower() for group in resource_groups
        }:
            raise AzurePortalAuthConfigError(
                "Workspace map contains a resource outside AZUREPORTAL_RESOURCE_GROUPS."
            )
        scopes[workspace_id] = AzureWorkspaceScope(
            workspace_id=workspace_id,
            resource_id="/" + resource_id_raw.strip().strip("/"),
            subscription_id=parsed["subscription_id"],
        )
    return scopes


def _parse_uuid_list(raw: str, name: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        if not item.strip():
            continue
        value = _normalize_uuid(item.strip(), name)
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _normalize_uuid(value: str, label: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise AzurePortalAuthConfigError(
            f"{label} must be a valid GUID."
        ) from exc


def _parse_csv(raw: str) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))


def _positive_int(name: str, default: int, *, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    if not re.fullmatch(r"[0-9]+", raw):
        raise AzurePortalAuthConfigError(f"{name} must be a positive integer.")
    value = int(raw)
    if value < 1 or value > maximum:
        raise AzurePortalAuthConfigError(
            f"{name} must be between 1 and {maximum}."
        )
    return value
