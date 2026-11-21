"""Bounded Azure resource discovery and metadata operations."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from azureportal_env import (
    AzurePortalAuthConfig,
    AzurePortalAuthConfigError,
    AzureWorkspaceScope,
    parse_resource_id,
)
from azureportal_transport import AzurePortalTransport, AzurePortalValidationError
from azureportal_transport import AzurePortalAPIError


_SENSITIVE_KEY = re.compile(
    r"(secret|token|password|credential|connection.?string|access.?key|private.?key|webhook)",
    re.I,
)
_SENSITIVE_VALUE = re.compile(
    r"(password|passwd|secret|token|access[_-]?key|client[_-]?secret)"
    r"(\s*[:=]\s*)[^\s,;]+|"
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    re.I,
)


class AzurePortalResourceClient:
    """Resolve and describe resources inside the configured subscription scope."""

    def __init__(
        self, config: AzurePortalAuthConfig, transport: AzurePortalTransport
    ) -> None:
        self.config = config
        self.transport = transport

    @classmethod
    def from_env(cls) -> "AzurePortalResourceClient":
        from azureportal_env import (
            create_azure_credential,
            load_project_environment,
            load_azureportal_auth_config_from_env,
        )

        load_project_environment()
        config = load_azureportal_auth_config_from_env()
        return cls(config, AzurePortalTransport(config, create_azure_credential(config)))

    def list_resources(
        self, *, resource_group: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        top = self._limit(limit)
        self._validate_resource_group(resource_group)
        resource_group_filter = resource_group.strip() if resource_group else None
        return self._run_paged_query(
            graph_operation="list_resources",
            graph_parameters={"resource_group": resource_group_filter},
            top=top,
            source="Azure Resource Graph",
            operation="list_resources",
            query_parameters={"resource_group": resource_group},
        )

    def resolve_resource(self, *, name_or_id: str, limit: int | None = None) -> dict[str, Any]:
        target = name_or_id.strip()
        if not target:
            raise AzurePortalValidationError("Resource name or ID must not be empty.")
        if target.startswith("/"):
            safe_id = self.config.authorize_resource_id(target)
            graph_operation = "get_resource_metadata"
            graph_parameters = {"resource_id": safe_id}
            params = {"resource_id": _redact_identifier(safe_id)}
        else:
            if len(target) > 256 or any(ord(char) < 32 for char in target):
                raise AzurePortalValidationError("Resource name is invalid.")
            graph_operation = "resolve_resource_name"
            graph_parameters = {"name": target}
            params = {"name": _redact_identifier(target)}
        result = self._run_paged_query(
            graph_operation=graph_operation,
            graph_parameters=graph_parameters,
            top=self._limit(limit),
            source="Azure Resource Graph",
            operation="resolve_resource",
            query_parameters=params,
        )
        resources = result["records"]
        unresolved_page = result["completeness"]["truncated"]
        result["resolution"] = (
            "not_found"
            if not resources
            else "ambiguous"
            if len(resources) > 1 or unresolved_page
            else "resolved"
        )
        if len(resources) == 1 and not unresolved_page:
            result["resource"] = resources[0]
        elif resources:
            result["matches"] = resources
        return result

    def get_resource_metadata(self, *, resource_id: str) -> dict[str, Any]:
        safe_id = self.config.authorize_resource_id(resource_id)
        result = self._run_paged_query(
            graph_operation="get_resource_metadata",
            graph_parameters={"resource_id": safe_id},
            top=2,
            source="Azure Resource Graph",
            operation="get_resource_metadata",
            query_parameters={"resource_id": _redact_identifier(safe_id)},
        )
        if len(result["records"]) > 1:
            raise AzurePortalAPIError(
                "ambiguous_resource",
                "Azure Resource Graph returned more than one resource for an exact resource ID.",
            )
        result["resource"] = result["records"][0] if result["records"] else None
        result["resolution"] = "resolved" if result["records"] else "not_found"
        return result

    def resolve_workspace_for_application(
        self, *, application_resource_id: str
    ) -> AzureWorkspaceScope:
        safe_id = self.config.authorize_resource_id(application_resource_id)
        parsed = parse_resource_id(safe_id)
        if (
            parsed["provider"].lower() != "microsoft.insights"
            or parsed["resource_type"].lower() != "components"
        ):
            raise AzurePortalValidationError(
                "Application Insights target must be a Microsoft.Insights/components resource ID."
            )
        result = self._run_paged_query(
            graph_operation="resolve_application_workspace",
            graph_parameters={"resource_id": safe_id},
            top=2,
            source="Azure Resource Graph",
            operation="resolve_application_workspace",
            query_parameters={
                "application_resource_id": _redact_identifier(safe_id)
            },
        )
        records = result["records"]
        if len(records) != 1:
            raise AzurePortalValidationError(
                "Application Insights resource must resolve to exactly one workspace-based component."
            )
        workspace_resource_id = records[0].get("workspaceResourceId")
        if not isinstance(workspace_resource_id, str) or not workspace_resource_id:
            raise AzurePortalValidationError(
                "Application Insights component has no workspace mapping; classic "
                "Application Insights resources are not supported."
            )
        normalized = "/" + workspace_resource_id.strip().strip("/").lower()
        for scope in self.config.workspace_scopes.values():
            if normalized == "/" + scope.resource_id.strip().strip("/").lower():
                return self.config.authorize_workspace(scope.workspace_id)
        raise AzurePortalAuthConfigError(
            "Application Insights workspace is not mapped in AZUREPORTAL_WORKSPACE_MAP."
        )

    def _run_paged_query(
        self,
        *,
        graph_operation: str,
        graph_parameters: dict[str, Any],
        top: int,
        source: str,
        operation: str,
        query_parameters: dict[str, Any],
    ) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        warnings: list[str] = []
        continuation: str | None = None
        request_id: str | None = None
        pages = 0
        while pages < self.config.max_pages and len(records) < top:
            page_size = min(top - len(records), self.config.max_rows)
            response = self.transport.query_resource_graph(
                operation=graph_operation,
                top=page_size,
                skip_token=continuation,
                **graph_parameters,
            )
            pages += 1
            request_id = response.request_id or request_id
            warnings.extend(response.warnings)
            page_records = response.payload.get("data", [])
            if not isinstance(page_records, list):
                raise AzurePortalAPIError(
                    "malformed_response",
                    "Azure Resource Graph returned an unexpected data shape.",
                    status_code=response.status_code,
                    request_id=response.request_id,
                )
            for record in page_records:
                if isinstance(record, dict):
                    records.append(_redact_resource(record))
            continuation_value = (
                response.payload.get("$skipToken")
                or response.payload.get("skipToken")
            )
            continuation = (
                continuation_value if isinstance(continuation_value, str) else None
            )
            if not continuation or not page_records:
                break

        truncated = bool(continuation)
        return {
            "evidence_id": str(uuid.uuid4()),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "scope": {
                "subscription_ids": list(self.config.subscription_ids),
                "resource_groups": list(self.config.resource_group_allowlist),
                "resource_ids": [
                    _redact_identifier(value)
                    for value in self.config.resource_id_allowlist
                ],
            },
            "source": source,
            "operation": operation,
            "query": _redact_query(response.query or ""),
            "query_parameters": query_parameters,
            "returned_count": len(records),
            "records": records,
            "completeness": {
                "partial": bool(warnings),
                "truncated": truncated,
                "pages": pages,
                "warnings": list(dict.fromkeys(warnings)),
                "request_id": request_id,
            },
        }

    def _limit(self, limit: int | None) -> int:
        value = self.config.max_rows if limit is None else limit
        if not isinstance(value, int) or value < 1:
            raise AzurePortalValidationError("Resource limit must be a positive integer.")
        return min(value, self.config.max_rows)

    def _validate_resource_group(self, requested: str | None) -> None:
        if requested is not None:
            value = requested.strip()
            if (
                not value
                or len(value) > 90
                or any(ord(char) < 32 for char in value)
            ):
                raise AzurePortalValidationError("Resource group filter is invalid.")
            if self.config.resource_group_allowlist and value.lower() not in {
                item.lower() for item in self.config.resource_group_allowlist
            }:
                raise AzurePortalAuthConfigError(
                    f"Resource group '{value}' is outside the configured allowlist."
                )
        elif not self.config.resource_group_allowlist:
            return


def _redact_identifier(value: str) -> str:
    if _SENSITIVE_KEY.search(value) or _SENSITIVE_VALUE.search(value):
        return "[REDACTED]"
    return _SENSITIVE_VALUE.sub("[REDACTED]", value)


def _redact_query(query: str) -> str:
    return re.sub(r"'(?:''|[^'])*'", "'[REDACTED]'", query)


def _redact_resource(record: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in record.items():
        if key.lower() == "tags" and isinstance(value, dict):
            result[key] = {
                tag: (
                    "[REDACTED]"
                    if _SENSITIVE_KEY.search(tag)
                    else _redact_tag_value(tag_value)
                )
                for tag, tag_value in value.items()
            }
        elif _SENSITIVE_KEY.search(key):
            result[key] = "[REDACTED]"
        else:
            result[key] = value
    return result


def _redact_tag_value(value: Any) -> Any:
    if isinstance(value, str):
        return _SENSITIVE_VALUE.sub("[REDACTED]", value)[:1000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return "[REDACTED]"
