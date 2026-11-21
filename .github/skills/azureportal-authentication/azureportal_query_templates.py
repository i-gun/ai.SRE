"""Finite Resource Graph and Azure Monitor Logs query templates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from azureportal_errors import AzurePortalValidationError


_TELEMETRY = {
    "requests": (
        "AppRequests",
        "TimeGenerated, Name, ResultCode, Success, DurationMs, OperationId, AppRoleName",
    ),
    "exceptions": (
        "AppExceptions",
        "TimeGenerated, ExceptionType, ProblemId, OuterMessage, OperationId, AppRoleName",
    ),
    "dependencies": (
        "AppDependencies",
        "TimeGenerated, Name, Target, Type, Success, ResultCode, DurationMs, OperationId, AppRoleName",
    ),
    "traces": (
        "AppTraces",
        "TimeGenerated, SeverityLevel, Message, OperationId, AppRoleName",
    ),
    "availability": (
        "AppAvailabilityResults",
        "TimeGenerated, Name, Success, DurationMs, Location, OperationId",
    ),
}


def build_resource_graph_query(
    *,
    operation: str,
    resource_group_allowlist: tuple[str, ...],
    resource_id_allowlist: tuple[str, ...],
    resource_group: str | None = None,
    name: str | None = None,
    resource_id: str | None = None,
) -> str:
    conditions: list[str] = []
    if operation == "list_resources":
        if resource_group is not None:
            _validate_filter(resource_group, "resource group", 90)
            if resource_group_allowlist and resource_group.lower() not in {
                item.lower() for item in resource_group_allowlist
            }:
                raise AzurePortalValidationError(
                    "Resource group is outside the configured allowlist."
                )
            conditions.append(f"resourceGroup =~ '{_kusto_string(resource_group)}'")
        elif resource_group_allowlist:
            values = ", ".join(
                f"'{_kusto_string(group)}'" for group in resource_group_allowlist
            )
            conditions.append(f"resourceGroup in~ ({values})")
        if resource_id_allowlist:
            conditions.append(
                "id in~ ("
                + ", ".join(
                    f"'{_kusto_string(value)}'" for value in resource_id_allowlist
                )
                + ")"
            )
    elif operation == "resolve_resource_name":
        if not name or len(name) > 256 or any(ord(char) < 32 for char in name):
            raise AzurePortalValidationError("Resource name must not be empty.")
        conditions.append(f"name =~ '{_kusto_string(name)}'")
    elif operation in {"get_resource_metadata", "resolve_application_workspace"}:
        if not resource_id:
            raise AzurePortalValidationError("Resource ID must not be empty.")
        conditions.append(f"id =~ '{_kusto_string(resource_id)}'")
        if operation == "resolve_application_workspace":
            conditions.append("type =~ 'microsoft.insights/components'")
    else:
        raise AzurePortalValidationError("Unsupported Resource Graph query template.")

    if operation != "list_resources":
        if resource_group_allowlist:
            values = ", ".join(
                f"'{_kusto_string(group)}'" for group in resource_group_allowlist
            )
            conditions.append(f"resourceGroup in~ ({values})")
        if resource_id_allowlist and resource_id is None:
            conditions.append(
                "id in~ ("
                + ", ".join(
                    f"'{_kusto_string(value)}'" for value in resource_id_allowlist
                )
                + ")"
            )
    query = "Resources"
    if conditions:
        query += " | where " + " and ".join(conditions)
    if operation == "resolve_application_workspace":
        return (
            query
            + " | project id, workspaceResourceId=tostring(properties.WorkspaceResourceId)"
        )
    return (
        query
        + " | project id, name, type, location, resourceGroup, subscriptionId, tags"
        + (" | order by name asc" if operation == "list_resources" else " | order by id asc")
    )


def build_logs_query(
    *,
    operation: str,
    start: datetime,
    end: datetime,
    category: str | None = None,
    service_name: str | None = None,
    limit: int = 500,
    grain: str = "5m",
) -> str:
    window = (
        f"TimeGenerated between "
        f"(datetime({_utc_iso(start)}) .. datetime({_utc_iso(end)}))"
    )
    if operation == "application_telemetry":
        if category not in _TELEMETRY:
            raise AzurePortalValidationError(
                f"Unsupported Application Insights telemetry category '{category}'."
            )
        table, columns = _TELEMETRY[category]
        query = f"{table} | where {window}"
        if service_name:
            _validate_filter(service_name, "service name", 256)
            query += f" | where AppRoleName == '{_kusto_string(service_name)}'"
        return (
            query
            + f" | project {columns} | order by TimeGenerated desc | take {limit}"
        )
    if operation == "table_metadata":
        if category not in _TELEMETRY:
            raise AzurePortalValidationError(
                f"Unsupported Application Insights table category '{category}'."
            )
        return f"{_TELEMETRY[category][0]} | getschema | take 200"
    if operation == "request_error_trend":
        if grain not in {"1m", "5m", "15m", "1h"}:
            raise AzurePortalValidationError(
                "Trend grain must be one of 1m, 5m, 15m, or 1h."
            )
        query = f"AppRequests | where {window}"
        if service_name:
            _validate_filter(service_name, "service name", 256)
            query += f" | where AppRoleName == '{_kusto_string(service_name)}'"
        return (
            query
            + " | summarize Requests=count(), Failed=countif(Success == false) "
            + f"by bin(TimeGenerated, {grain}) | sort by TimeGenerated asc"
        )
    if operation == "exception_groups":
        return (
            f"AppExceptions | where {window}"
            " | summarize ExceptionCount=count(), FirstSeen=min(TimeGenerated), "
            "LastSeen=max(TimeGenerated) by ExceptionType, ProblemId, OuterMessage"
            f" | top {limit} by ExceptionCount desc"
        )
    raise AzurePortalValidationError("Unsupported Azure Monitor Logs query template.")


def telemetry_categories() -> Mapping[str, tuple[str, str]]:
    """Return a read-only view of supported category/table/column mappings."""
    return dict(_TELEMETRY)


def _kusto_string(value: str) -> str:
    return value.replace("'", "''")


def _validate_filter(value: str, label: str, maximum: int) -> None:
    if (
        not value
        or len(value) > maximum
        or any(ord(char) < 32 for char in value)
    ):
        raise AzurePortalValidationError(f"{label} filter is invalid.")


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
