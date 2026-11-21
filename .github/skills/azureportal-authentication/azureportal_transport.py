"""Restricted Azure public-cloud transport shared by AzurePortal operation clients."""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlparse

import requests
from azure.core.exceptions import AzureError

from azureportal_env import AzurePortalAuthConfig
from azureportal_errors import AzurePortalValidationError
from azureportal_query_templates import (
    build_logs_query,
    build_resource_graph_query,
)


ARM_SCOPE = "https://management.azure.com/.default"
LOGS_SCOPE = "https://api.loganalytics.azure.com/.default"
ARM_HOST = "management.azure.com"
LOGS_HOST = "api.loganalytics.azure.com"

_COLLECTIONS = {
    "fired_alerts": (
        "Microsoft.AlertsManagement/alerts",
        "2019-03-01",
    ),
    "metric_alert_rules": ("Microsoft.Insights/metricAlerts", "2018-03-01"),
    "scheduled_query_rules": (
        "Microsoft.Insights/scheduledQueryRules",
        "2021-08-01",
    ),
    "activity_log_alert_rules": (
        "Microsoft.Insights/activityLogAlerts",
        "2020-10-01",
    ),
    "action_groups": ("Microsoft.Insights/actionGroups", "2023-01-01"),
}
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_RESOURCE_ID_PATTERN = re.compile(
    r"^/subscriptions/[0-9a-f-]+/resourceGroups/[^/]+/providers/.+$", re.I
)


class AzurePortalAPIError(RuntimeError):
    """Credential-safe Azure API failure with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.request_id = request_id


@dataclass(frozen=True)
class AzureAPIResult:
    payload: Mapping[str, Any]
    status_code: int
    request_id: str | None
    warnings: tuple[str, ...] = ()
    query: str | None = None
    request_parameters: Mapping[str, str] | None = None


class AzurePortalTransport:
    """Permit only implemented Azure read/query endpoints and public-cloud hosts."""

    def __init__(
        self,
        config: AzurePortalAuthConfig,
        credential: Any,
        *,
        session: requests.Session | None = None,
        sleep=time.sleep,
    ) -> None:
        self.config = config
        self.credential = credential
        self.session = session or requests.Session()
        self._sleep = sleep
        self._slots = threading.BoundedSemaphore(config.max_concurrent_requests)

    def query_resource_graph(
        self,
        *,
        operation: str,
        top: int,
        skip_token: str | None = None,
        resource_group: str | None = None,
        name: str | None = None,
        resource_id: str | None = None,
    ) -> AzureAPIResult:
        if not 1 <= top <= self.config.max_rows:
            raise AzurePortalValidationError("Resource Graph row limit is out of bounds.")
        if skip_token is not None and (
            not skip_token
            or len(skip_token) > 8192
            or any(ord(char) < 32 for char in skip_token)
        ):
            raise AzurePortalValidationError("Resource Graph continuation token is invalid.")
        safe_resource_id = (
            self._authorize_resource_id(resource_id) if resource_id is not None else None
        )
        query = build_resource_graph_query(
            operation=operation,
            resource_group=resource_group,
            name=name,
            resource_id=safe_resource_id,
            resource_group_allowlist=self.config.resource_group_allowlist,
            resource_id_allowlist=self.config.resource_id_allowlist,
        )
        body: dict[str, Any] = {
            "subscriptions": list(self.config.subscription_ids),
            "query": query,
            "options": {"$top": top},
        }
        if skip_token:
            body["options"]["$skipToken"] = skip_token
        result = self._request(
            host=ARM_HOST,
            path="/providers/Microsoft.ResourceGraph/resources",
            api_version="2022-10-01",
            service="arm",
            operation="resource_graph_query",
            method="POST",
            json_body=body,
        )
        return AzureAPIResult(
            result.payload,
            result.status_code,
            result.request_id,
            result.warnings,
            query,
        )

    def query_application_telemetry(
        self,
        *,
        workspace_id: str,
        category: str,
        start: datetime,
        end: datetime,
        limit: int,
        service_name: str | None = None,
    ) -> AzureAPIResult:
        if not 1 <= limit <= self.config.max_rows:
            raise AzurePortalValidationError("Logs result limit is out of bounds.")
        query = build_logs_query(
            operation="application_telemetry",
            category=category,
            start=start,
            end=end,
            limit=limit,
            service_name=service_name,
        )
        return self._execute_logs_query(
            workspace_id=workspace_id, query=query, start=start, end=end
        )

    def query_table_metadata(
        self,
        *,
        workspace_id: str,
        category: str,
        start: datetime,
        end: datetime,
    ) -> AzureAPIResult:
        query = build_logs_query(
            operation="table_metadata",
            category=category,
            start=start,
            end=end,
        )
        return self._execute_logs_query(
            workspace_id=workspace_id, query=query, start=start, end=end
        )

    def query_request_error_trend(
        self,
        *,
        workspace_id: str,
        start: datetime,
        end: datetime,
        grain: str,
        service_name: str | None = None,
    ) -> AzureAPIResult:
        query = build_logs_query(
            operation="request_error_trend",
            start=start,
            end=end,
            grain=grain,
            service_name=service_name,
        )
        return self._execute_logs_query(
            workspace_id=workspace_id, query=query, start=start, end=end
        )

    def query_exception_groups(
        self,
        *,
        workspace_id: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> AzureAPIResult:
        if not 1 <= limit <= self.config.max_rows:
            raise AzurePortalValidationError("Logs result limit is out of bounds.")
        query = build_logs_query(
            operation="exception_groups",
            start=start,
            end=end,
            limit=limit,
        )
        return self._execute_logs_query(
            workspace_id=workspace_id, query=query, start=start, end=end
        )

    def _execute_logs_query(
        self, *, workspace_id: str, query: str, start: datetime, end: datetime
    ) -> AzureAPIResult:
        self.config.authorize_workspace(workspace_id)
        _validate_window(self.config, start, end)
        path = f"/v1/workspaces/{workspace_id}/query"
        result = self._request(
            host=LOGS_HOST,
            path=path,
            service="logs",
            operation="bounded_logs_query",
            method="POST",
            json_body={
                "query": query,
                "timespan": f"{_utc_iso(start)}/{_utc_iso(end)}",
            },
        )
        return AzureAPIResult(
            result.payload,
            result.status_code,
            result.request_id,
            result.warnings,
            query,
        )

    def get_metric_definitions(self, resource_id: str) -> AzureAPIResult:
        safe_id = self._authorize_resource_id(resource_id)
        return self._request(
            host=ARM_HOST,
            path=f"{safe_id}/providers/Microsoft.Insights/metricDefinitions",
            api_version="2018-01-01",
            service="arm",
            operation="metric_definitions",
            method="GET",
        )

    def get_metrics(
        self, *, resource_id: str, parameters: Mapping[str, str]
    ) -> AzureAPIResult:
        safe_id = self._authorize_resource_id(resource_id)
        allowed_parameters = {
            "timespan",
            "interval",
            "metricnames",
            "aggregation",
            "top",
            "$filter",
        }
        if set(parameters) - allowed_parameters:
            raise AzurePortalValidationError("Unsupported metric query parameter.")
        return self._request(
            host=ARM_HOST,
            path=f"{safe_id}/providers/Microsoft.Insights/metrics",
            api_version="2018-01-01",
            service="arm",
            operation="metric_series",
            method="GET",
            params=parameters,
        )

    def list_subscription_collection(
        self,
        *,
        subscription_id: str,
        collection: str,
        parameters: Mapping[str, str] | None = None,
    ) -> AzureAPIResult:
        subscription_id = self.config.authorize_subscription(subscription_id)
        spec = _COLLECTIONS.get(collection)
        if spec is None:
            raise AzurePortalValidationError("Unsupported Azure subscription collection.")
        collection_path, api_version = spec
        allowed_parameters = (
            {"customTimeRange", "monitorCondition"}
            if collection == "fired_alerts"
            else set()
        )
        supplied = dict(parameters or {})
        if set(supplied) - allowed_parameters:
            raise AzurePortalValidationError(
                f"Unsupported parameters for Azure collection '{collection}'."
            )
        return self._request(
            host=ARM_HOST,
            path=f"/subscriptions/{subscription_id}/providers/{collection_path}",
            api_version=api_version,
            service="arm",
            operation=collection,
            method="GET",
            params=supplied,
        )

    def get_activity_log(
        self,
        *,
        subscription_id: str,
        start: datetime,
        end: datetime,
        top: int,
        resource_group: str | None = None,
        resource_id: str | None = None,
    ) -> AzureAPIResult:
        subscription_id = self.config.authorize_subscription(subscription_id)
        _validate_window(self.config, start, end)
        if not 1 <= top <= self.config.max_rows:
            raise AzurePortalValidationError("Activity Log row limit is out of bounds.")
        if resource_group and resource_id:
            raise AzurePortalValidationError(
                "Activity Log scope must use either a resource group or resource ID."
            )
        scope_filter = ""
        if resource_group:
            if self.config.resource_group_allowlist and resource_group.lower() not in {
                item.lower() for item in self.config.resource_group_allowlist
            }:
                raise AzurePortalValidationError(
                    "Activity Log resource group is outside the configured allowlist."
                )
            scope_filter = f" and resourceGroupName eq '{_odata_string(resource_group)}'"
        elif resource_id:
            safe_id = self._authorize_resource_id(resource_id)
            if not safe_id.lower().startswith(
                f"/subscriptions/{subscription_id.lower()}/"
            ):
                raise AzurePortalValidationError(
                    "Activity Log resource ID is outside the requested subscription."
                )
            scope_filter = f" and resourceUri eq '{_odata_string(safe_id)}'"
        start_text = _utc_iso(start)
        end_text = _utc_iso(end)
        filter_text = (
            f"eventTimestamp ge '{start_text}' and eventTimestamp le '{end_text}'"
            + scope_filter
        )
        parameters = {"$filter": filter_text}
        result = self._request(
            host=ARM_HOST,
            path=(
                f"/subscriptions/{subscription_id}/providers/"
                "Microsoft.Insights/eventtypes/management/values"
            ),
            api_version="2015-04-01",
            service="arm",
            operation="activity_log",
            method="GET",
            params=parameters,
        )
        return AzureAPIResult(
            result.payload,
            result.status_code,
            result.request_id,
            result.warnings,
            request_parameters=parameters,
        )

    def get_diagnostic_settings(self, resource_id: str) -> AzureAPIResult:
        safe_id = self._authorize_resource_id(resource_id)
        return self._request(
            host=ARM_HOST,
            path=f"{safe_id}/providers/Microsoft.Insights/diagnosticSettings",
            api_version="2021-05-01-preview",
            service="arm",
            operation="diagnostic_settings",
            method="GET",
        )

    def get_arm_continuation(
        self,
        *,
        url: str,
        expected_path: str,
        subscription_id: str,
        operation: str,
        expected_parameters: Mapping[str, str] | None = None,
    ) -> AzureAPIResult:
        """Follow only same-origin, same-operation ARM continuation links."""
        self.config.authorize_subscription(subscription_id)
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != ARM_HOST
            or parsed.port not in (None, 443)
            or parsed.username
            or parsed.password
            or parsed.fragment
            or parsed.path != expected_path
        ):
            raise AzurePortalValidationError(
                "Azure continuation URL is not an allowed ARM endpoint."
            )
        allowed_operations = set(_COLLECTIONS) | {"activity_log"}
        if operation not in allowed_operations:
            raise AzurePortalValidationError("Unsupported continuation operation.")
        if not _path_contains_subscription(parsed.path, subscription_id):
            raise AzurePortalValidationError(
                "Azure continuation URL left the authorized subscription."
            )
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if len({key.lower() for key, _ in query_pairs}) != len(query_pairs):
            raise AzurePortalValidationError(
                "Azure continuation URL contains duplicate query parameters."
            )
        expected = dict(expected_parameters or {})
        allowed_parameters = {
            "api-version",
            "$skiptoken",
            "skiptoken",
            "$top",
            *[key.lower() for key in expected],
        }
        if any(key.lower() not in allowed_parameters for key, _ in query_pairs):
            raise AzurePortalValidationError(
                "Azure continuation URL contains unsupported query parameters."
            )
        params = dict(query_pairs)
        if not params.get("api-version"):
            raise AzurePortalValidationError(
                "Azure continuation URL omitted its API version."
            )
        expected_version = (
            _COLLECTIONS[operation][1]
            if operation in _COLLECTIONS
            else "2015-04-01"
        )
        if params["api-version"] != expected_version:
            raise AzurePortalValidationError(
                "Azure continuation URL changed the API version."
            )
        for key, value in expected.items():
            if params.get(key) != value:
                raise AzurePortalValidationError(
                    "Azure continuation URL changed the authorized query scope."
                )
        result = self._request(
            host=ARM_HOST,
            path=expected_path,
            service="arm",
            operation=f"{operation}_continuation",
            method="GET",
            params=params,
        )
        return AzureAPIResult(
            result.payload,
            result.status_code,
            result.request_id,
            result.warnings,
            request_parameters=expected,
        )

    def _authorize_resource_id(self, resource_id: str) -> str:
        authorized = self.config.authorize_resource_id(resource_id)
        if not _RESOURCE_ID_PATTERN.fullmatch(authorized):
            raise AzurePortalValidationError("Resource ID is not a valid ARM resource path.")
        return authorized

    def _request(
        self,
        *,
        host: str,
        path: str,
        service: str,
        operation: str,
        method: str,
        api_version: str | None = None,
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> AzureAPIResult:
        if service not in {"arm", "logs"} or host != (
            ARM_HOST if service == "arm" else LOGS_HOST
        ):
            raise AzurePortalValidationError("Azure API host is not allowlisted.")
        if method not in {"GET", "POST"} or not path.startswith("/"):
            raise AzurePortalValidationError("Azure API operation is not allowlisted.")
        self._validate_endpoint(service, path, operation, method)
        query_params = dict(params or {})
        if api_version:
            query_params["api-version"] = api_version
        url = f"https://{host}{path}"
        scope = ARM_SCOPE if service == "arm" else LOGS_SCOPE

        with self._slots:
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    token = self.credential.get_token(scope).token
                except AzureError:
                    # Credential library errors can contain tenant or credential details.
                    raise AzurePortalAPIError(
                        "authentication_failed",
                        "Azure identity could not acquire a token for the selected API audience.",
                    ) from None
                try:
                    response = self.session.request(
                        method,
                        url,
                        params=query_params,
                        json=json_body,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                        },
                        timeout=self.config.timeout_seconds,
                        allow_redirects=False,
                    )
                except requests.Timeout:
                    if attempt < _MAX_RETRIES:
                        self._sleep(min(2**attempt, 4))
                        continue
                    raise AzurePortalAPIError(
                        "timeout", f"Azure {operation} timed out."
                    ) from None
                except requests.RequestException:
                    if attempt < _MAX_RETRIES:
                        self._sleep(min(2**attempt, 4))
                        continue
                    raise AzurePortalAPIError(
                        "network_error", f"Azure {operation} request failed."
                    ) from None

                request_id = (
                    response.headers.get("x-ms-request-id")
                    or response.headers.get("x-ms-correlation-request-id")
                )
                if 300 <= response.status_code < 400:
                    raise AzurePortalAPIError(
                        "redirect_rejected",
                        f"Azure {operation} returned a redirect; redirects are not followed.",
                        status_code=response.status_code,
                        request_id=request_id,
                    )
                if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                    self._sleep(_retry_delay(response.headers.get("Retry-After"), attempt))
                    continue
                if response.status_code == 403:
                    raise AzurePortalAPIError(
                        "forbidden",
                        f"Access denied for Azure {operation}. Check the identity's read permissions.",
                        status_code=403,
                        request_id=request_id,
                    )
                if response.status_code == 401:
                    raise AzurePortalAPIError(
                        "unauthorized",
                        f"Azure rejected the selected identity for {operation}.",
                        status_code=401,
                        request_id=request_id,
                    )
                if response.status_code == 429:
                    raise AzurePortalAPIError(
                        "throttled",
                        f"Azure throttled {operation} after bounded retries.",
                        status_code=429,
                        request_id=request_id,
                    )
                if response.status_code == 404:
                    raise AzurePortalAPIError(
                        "unavailable",
                        f"Azure {operation} target or data source is unavailable.",
                        status_code=404,
                        request_id=request_id,
                    )
                if response.status_code == 400 and service == "logs":
                    raise AzurePortalAPIError(
                        "invalid_query",
                        "Azure Monitor rejected the generated Logs query.",
                        status_code=400,
                        request_id=request_id,
                    )
                if response.status_code >= 400:
                    raise AzurePortalAPIError(
                        "api_error",
                        f"Azure {operation} failed with HTTP {response.status_code}.",
                        status_code=response.status_code,
                        request_id=request_id,
                    )
                try:
                    payload = response.json()
                except (ValueError, json.JSONDecodeError):
                    raise AzurePortalAPIError(
                        "malformed_response",
                        f"Azure {operation} returned malformed JSON.",
                        status_code=response.status_code,
                        request_id=request_id,
                    ) from None
                if not isinstance(payload, dict):
                    raise AzurePortalAPIError(
                        "malformed_response",
                        f"Azure {operation} returned an unexpected response shape.",
                        status_code=response.status_code,
                        request_id=request_id,
                    )
                warnings: list[str] = []
                if response.status_code == 206:
                    warnings.append("Azure returned a partial response (HTTP 206).")
                if payload.get("error"):
                    warnings.append("Azure response includes an API warning or partial-result error.")
                return AzureAPIResult(
                    payload=payload,
                    status_code=response.status_code,
                    request_id=request_id,
                    warnings=tuple(warnings),
                )
        raise AzurePortalAPIError(
            "retry_exhausted", f"Azure {operation} exceeded its retry limit."
        )

    @staticmethod
    def _validate_endpoint(
        service: str, path: str, operation: str, method: str
    ) -> None:
        if service == "logs":
            if (
                method != "POST"
                or operation != "bounded_logs_query"
                or not re.fullmatch(
                    r"/v1/workspaces/[0-9a-fA-F-]{36}/query", path
                )
            ):
                raise AzurePortalValidationError("Logs endpoint is not allowlisted.")
            return
        if operation == "resource_graph_query":
            if path != "/providers/Microsoft.ResourceGraph/resources" or method != "POST":
                raise AzurePortalValidationError("Resource Graph endpoint is not allowlisted.")
            return
        if operation in {"metric_definitions", "metric_series"}:
            suffix = (
                "/providers/Microsoft.Insights/metricDefinitions"
                if operation == "metric_definitions"
                else "/providers/Microsoft.Insights/metrics"
            )
            if method != "GET" or not path.endswith(suffix):
                raise AzurePortalValidationError("Metric endpoint is not allowlisted.")
            resource_path = path[: -len(suffix)]
            if not _RESOURCE_ID_PATTERN.fullmatch(resource_path):
                raise AzurePortalValidationError("Metric target resource path is invalid.")
            return
        if operation == "diagnostic_settings":
            suffix = "/providers/Microsoft.Insights/diagnosticSettings"
            if method != "GET" or not path.endswith(suffix):
                raise AzurePortalValidationError("Diagnostic settings endpoint is not allowlisted.")
            if not _RESOURCE_ID_PATTERN.fullmatch(path[: -len(suffix)]):
                raise AzurePortalValidationError("Diagnostic settings target is invalid.")
            return
        collection = operation.removesuffix("_continuation")
        if collection in _COLLECTIONS:
            expected = _COLLECTIONS[collection][0]
            if (
                method != "GET"
                or not re.fullmatch(
                    rf"/subscriptions/[0-9a-f-]+/providers/{re.escape(expected)}",
                    path,
                    re.I,
                )
            ):
                raise AzurePortalValidationError("Azure collection endpoint is not allowlisted.")
            return
        if operation in {"activity_log", "activity_log_continuation"}:
            expected_path = (
                r"/subscriptions/[0-9a-f-]+/providers/"
                r"Microsoft\.Insights/eventtypes/management/values"
            )
            if method != "GET" or not re.fullmatch(expected_path, path, re.I):
                raise AzurePortalValidationError("Activity Log endpoint is not allowlisted.")
            return
        if operation.endswith("_continuation"):
            raise AzurePortalValidationError("Azure continuation operation is not allowlisted.")
        raise AzurePortalValidationError("Azure operation is not allowlisted.")


def _validate_window(
    config: AzurePortalAuthConfig, start: datetime, end: datetime
) -> None:
    if start.tzinfo is None or end.tzinfo is None:
        raise AzurePortalValidationError("Time-window values must be timezone-aware.")
    if end <= start:
        raise AzurePortalValidationError("Time-window end must be after its start.")
    duration = end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    if duration.total_seconds() > config.max_window_days * 86400:
        raise AzurePortalValidationError(
            f"Time window exceeds AZUREPORTAL_MAX_WINDOW_DAYS ({config.max_window_days})."
        )


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _odata_string(value: str) -> str:
    return value.replace("'", "''")


def _retry_delay(value: str | None, attempt: int) -> float:
    if value:
        try:
            return min(max(float(value), 0.0), 30.0)
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                return min(
                    max((date - datetime.now(timezone.utc)).total_seconds(), 0.0),
                    30.0,
                )
            except (TypeError, ValueError, OverflowError):
                pass
    return min(2**attempt, 4)


def _path_contains_subscription(path: str, subscription_id: str) -> bool:
    parts = path.strip("/").split("/")
    return (
        len(parts) >= 2
        and parts[0].lower() == "subscriptions"
        and parts[1].lower() == subscription_id.lower()
    )
