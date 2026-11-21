"""Bounded Azure Monitor Logs, Application Insights, metrics, and alert queries."""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from azureportal_env import AzurePortalAuthConfig
from azureportal_transport import (
    AzureAPIResult,
    AzurePortalAPIError,
    AzurePortalTransport,
    AzurePortalValidationError,
)


_SENSITIVE_VALUE = re.compile(
    r"(bearer\s+)[A-Za-z0-9._~+/-]+=*|"
    r"(password|passwd|secret|token|access[_-]?key|client[_-]?secret)"
    r"(\s*[:=]\s*)[^\s,;]+|"
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    re.I,
)
_SENSITIVE_FIELD = re.compile(
    r"(secret|token|password|credential|connection.?string|access.?key|"
    r"private.?key|webhook|serviceuri|callbackurl|sharedkey|receiver)",
    re.I,
)
_ISO_DURATION = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)
_AGGREGATIONS = {"Average", "Count", "Minimum", "Maximum", "Total"}


class AzurePortalMonitoringClient:
    """Execute only fixed KQL templates and documented Azure Monitor GET operations."""

    def __init__(
        self,
        config: AzurePortalAuthConfig,
        transport: AzurePortalTransport,
        resource_client: Any | None = None,
    ) -> None:
        self.config = config
        self.transport = transport
        self.resource_client = resource_client

    @classmethod
    def from_env(cls) -> "AzurePortalMonitoringClient":
        from azureportal_env import (
            create_azure_credential,
            load_project_environment,
            load_azureportal_auth_config_from_env,
        )
        from azureportal_resource_client import AzurePortalResourceClient

        load_project_environment()
        config = load_azureportal_auth_config_from_env()
        transport = AzurePortalTransport(config, create_azure_credential(config))
        return cls(
            config,
            transport,
            AzurePortalResourceClient(config, transport),
        )

    def query_telemetry(
        self,
        *,
        workspace_id: str | None = None,
        application_resource_id: str | None = None,
        category: str,
        start: datetime,
        end: datetime,
        limit: int | None = None,
        service_name: str | None = None,
    ) -> dict[str, Any]:
        target_workspace = self._resolve_workspace(
            workspace_id=workspace_id,
            application_resource_id=application_resource_id,
        )
        row_limit = self._limit(limit)
        _validate_window(self.config, start, end)
        if service_name:
            if len(service_name) > 256 or any(ord(char) < 32 for char in service_name):
                raise AzurePortalValidationError("Service-name filter is invalid.")
        response = self.transport.query_application_telemetry(
            workspace_id=target_workspace,
            category=category,
            start=start,
            end=end,
            limit=row_limit,
            service_name=service_name,
        )
        rows, result_warnings = _table_rows(response.payload)
        records = [_redact_record(row) for row in rows[:row_limit]]
        warnings = list(response.warnings) + result_warnings
        truncated = len(rows) >= row_limit and row_limit < self.config.max_rows
        evidence = self._evidence(
            response=response,
            source="Azure Monitor Logs",
            operation=f"application_insights_{category}",
            scope={"workspace_id": target_workspace},
            start=start,
            end=end,
            query=response.query or "",
            query_parameters={
                "category": category,
                "application_resource_id": (
                    _redact_identifier(application_resource_id)
                    if application_resource_id
                    else None
                ),
                "service_name": _redact_identifier(service_name) if service_name else None,
                "limit": row_limit,
            },
            records=records,
            warnings=warnings,
            truncated=truncated,
        )
        evidence["data_status"] = (
            "records_returned"
            if records
            else "zero_matching_records"
            if response.payload.get("tables")
            else "no_table_returned_instrumentation_or_retention_unverified"
        )
        return evidence

    def get_table_metadata(
        self,
        *,
        workspace_id: str,
        category: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        workspace = self.config.authorize_workspace(workspace_id).workspace_id
        _validate_window(self.config, start, end)
        response = self.transport.query_table_metadata(
            workspace_id=workspace,
            category=category,
            start=start,
            end=end,
        )
        rows, table_warnings = _table_rows(response.payload)
        columns = [_redact_record(row) for row in rows[:200]]
        return self._evidence(
            response=response,
            source="Azure Monitor Logs schema query",
            operation="table_metadata",
            scope={"workspace_id": workspace},
            start=start,
            end=end,
            query=response.query or "",
            query_parameters={"category": category},
            records=columns,
            warnings=list(response.warnings) + table_warnings,
            truncated=len(rows) > 200,
        )

    def analyze_request_error_trend(
        self,
        *,
        workspace_id: str | None = None,
        application_resource_id: str | None = None,
        start: datetime,
        end: datetime,
        grain: str = "5m",
        service_name: str | None = None,
    ) -> dict[str, Any]:
        workspace = self._resolve_workspace(
            workspace_id=workspace_id,
            application_resource_id=application_resource_id,
        )
        _validate_window(self.config, start, end)
        if service_name:
            if len(service_name) > 256 or any(ord(char) < 32 for char in service_name):
                raise AzurePortalValidationError("Service-name filter is invalid.")
        response = self.transport.query_request_error_trend(
            workspace_id=workspace,
            start=start,
            end=end,
            grain=grain,
            service_name=service_name,
        )
        rows, table_warnings = _table_rows(response.payload)
        records = [_redact_record(row) for row in rows[: self.config.max_rows]]
        return self._evidence(
            response=response,
            source="Azure Monitor Logs",
            operation="application_insights_request_error_trend",
            scope={"workspace_id": workspace},
            start=start,
            end=end,
            query=response.query or "",
            query_parameters={"grain": grain, "service_name": service_name},
            records=records,
            warnings=list(response.warnings) + table_warnings,
            truncated=len(rows) > self.config.max_rows,
        )

    def group_application_exceptions(
        self,
        *,
        workspace_id: str | None = None,
        application_resource_id: str | None = None,
        start: datetime,
        end: datetime,
        limit: int | None = None,
    ) -> dict[str, Any]:
        workspace = self._resolve_workspace(
            workspace_id=workspace_id,
            application_resource_id=application_resource_id,
        )
        _validate_window(self.config, start, end)
        row_limit = self._limit(limit)
        response = self.transport.query_exception_groups(
            workspace_id=workspace,
            start=start,
            end=end,
            limit=row_limit,
        )
        rows, table_warnings = _table_rows(response.payload)
        records = [_redact_record(row) for row in rows[:row_limit]]
        evidence = self._evidence(
            response=response,
            source="Azure Monitor Logs",
            operation="application_insights_exception_groups",
            scope={"workspace_id": workspace},
            start=start,
            end=end,
            query=response.query or "",
            query_parameters={"limit": row_limit},
            records=records,
            warnings=list(response.warnings) + table_warnings,
            truncated=len(rows) >= row_limit and row_limit < self.config.max_rows,
        )
        evidence["data_status"] = (
            "groups_returned"
            if records
            else "zero_matching_records"
            if response.payload.get("tables")
            else "no_table_returned_instrumentation_or_retention_unverified"
        )
        return evidence

    def list_metric_definitions(self, *, resource_id: str) -> dict[str, Any]:
        safe_resource_id = self.config.authorize_resource_id(resource_id)
        response = self.transport.get_metric_definitions(safe_resource_id)
        values = response.payload.get("value", [])
        if not isinstance(values, list):
            raise AzurePortalAPIError(
                "malformed_response",
                "Azure Monitor returned an unexpected metric-definition response.",
                status_code=response.status_code,
                request_id=response.request_id,
            )
        definitions = []
        for item in values[: self.config.max_rows]:
            if not isinstance(item, dict):
                continue
            definitions.append(
                {
                    "namespace": item.get("namespace"),
                    "id": item.get("id"),
                    "name": _nested_value(item, "name", "value"),
                    "display_name": _nested_value(item, "name", "localizedValue"),
                    "unit": item.get("unit"),
                    "primary_aggregation": item.get("primaryAggregationType"),
                    "supported_aggregations": item.get("supportedAggregationTypes", []),
                    "dimensions": [
                        {
                            "name": dimension.get("value"),
                            "display_name": dimension.get("localizedValue"),
                        }
                        for dimension in item.get("dimensions", [])
                        if isinstance(dimension, dict)
                    ],
                    "time_grains": _time_grains(item),
                }
            )
        return {
            "evidence_id": str(uuid.uuid4()),
            "retrieved_at": _now_utc(),
            "scope": {"resource_id": _redact_identifier(safe_resource_id)},
            "source": "Azure Monitor metric definitions",
            "operation": "list_metric_definitions",
            "returned_count": len(definitions),
            "definitions": definitions,
            "completeness": {
                "partial": bool(response.warnings),
                "truncated": len(values) > self.config.max_rows,
                "warnings": list(response.warnings),
                "request_id": response.request_id,
            },
        }

    def query_metric(
        self,
        *,
        resource_id: str,
        metric_name: str,
        aggregation: str,
        interval: str,
        start: datetime,
        end: datetime,
        dimensions: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        safe_resource_id = self.config.authorize_resource_id(resource_id)
        _validate_window(self.config, start, end)
        definition_response = self.transport.get_metric_definitions(safe_resource_id)
        definition = self._find_metric_definition(
            definition_response.payload, metric_name
        )
        if aggregation not in definition["supported_aggregations"]:
            raise AzurePortalValidationError(
                f"Aggregation '{aggregation}' is not supported for metric '{metric_name}'."
            )
        if aggregation not in _AGGREGATIONS:
            raise AzurePortalValidationError(
                "Only Azure's Average, Count, Minimum, Maximum, and Total aggregations are supported."
            )
        if interval not in definition["time_grains"]:
            raise AzurePortalValidationError(
                f"Time grain '{interval}' is not available for metric '{metric_name}'."
            )
        _validate_metric_volume(
            start=start,
            end=end,
            interval=interval,
            max_points=self.config.max_rows,
        )
        filter_clause = _metric_dimension_filter(
            dimensions or {}, definition["dimensions"]
        )
        parameters = {
            "timespan": f"{_utc_iso(start)}/{_utc_iso(end)}",
            "interval": interval,
            "metricnames": metric_name,
            "aggregation": (
                "Average,Count"
                if aggregation == "Average"
                and "Count" in definition["supported_aggregations"]
                else aggregation
            ),
            "top": str(self.config.max_rows),
        }
        if filter_clause:
            parameters["$filter"] = filter_clause
        response = self.transport.get_metrics(
            resource_id=safe_resource_id,
            parameters=parameters,
        )
        series, truncated = _metric_series(
            response.payload, max_series=self.config.max_rows
        )
        return {
            "evidence_id": str(uuid.uuid4()),
            "retrieved_at": _now_utc(),
            "scope": {"resource_id": _redact_identifier(safe_resource_id)},
            "source": "Azure Monitor metrics",
            "operation": "query_metric",
            "query_parameters": {
                **{
                    key: _redact_value(value) for key, value in parameters.items()
                },
                "dimensions": {
                    key: _redact_value(value)
                    for key, value in (dimensions or {}).items()
                },
            },
            "window": {"start_utc": _utc_iso(start), "end_utc": _utc_iso(end)},
            "metric": {
                "name": metric_name,
                "unit": definition["unit"],
                "aggregation": aggregation,
                "time_grain": interval,
                "dimensions": {
                    key: _redact_value(value)
                    for key, value in (dimensions or {}).items()
                },
            },
            "returned_count": sum(len(item["data"]) for item in series),
            "series": series,
            "completeness": {
                "partial": bool(response.warnings),
                "truncated": truncated,
                "warnings": list(response.warnings),
                "request_id": response.request_id,
            },
            "data_status": "series_returned" if series else "no_series_returned",
        }

    def compare_metric_windows(
        self,
        *,
        resource_id: str,
        metric_name: str,
        aggregation: str,
        interval: str,
        current_start: datetime,
        current_end: datetime,
        baseline_start: datetime,
        baseline_end: datetime,
        dimensions: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        _validate_window(self.config, current_start, current_end)
        _validate_window(self.config, baseline_start, baseline_end)
        if current_end - current_start != baseline_end - baseline_start:
            raise AzurePortalValidationError(
                "Metric comparison windows must have equal durations."
            )
        current = self.query_metric(
            resource_id=resource_id,
            metric_name=metric_name,
            aggregation=aggregation,
            interval=interval,
            start=current_start,
            end=current_end,
            dimensions=dimensions,
        )
        baseline = self.query_metric(
            resource_id=resource_id,
            metric_name=metric_name,
            aggregation=aggregation,
            interval=interval,
            start=baseline_start,
            end=baseline_end,
            dimensions=dimensions,
        )
        current_value, current_samples, current_buckets = _aggregate_metric(
            current["series"], aggregation
        )
        baseline_value, baseline_samples, baseline_buckets = _aggregate_metric(
            baseline["series"], aggregation
        )
        change = (
            (current_value - baseline_value) / abs(baseline_value) * 100
            if current_value is not None
            and baseline_value is not None
            and baseline_value != 0
            else None
        )
        return {
            "evidence_id": str(uuid.uuid4()),
            "retrieved_at": _now_utc(),
            "source": "Azure Monitor metrics",
            "operation": "compare_metric_windows",
            "scope": current["scope"],
            "metric": current["metric"],
            "comparison": {
                "current_window": current["window"],
                "baseline_window": baseline["window"],
                "window_alignment": "equal duration; exact UTC windows provided",
                "current_value": current_value,
                "current_sample_count": current_samples,
                "current_bucket_count": current_buckets,
                "baseline_value": baseline_value,
                "baseline_sample_count": baseline_samples,
                "baseline_bucket_count": baseline_buckets,
                "change_percent": change,
                "change_percent_note": (
                    "Undefined because one or both windows contain no metric samples."
                    if current_value is None or baseline_value is None
                    else "Undefined because the baseline is zero."
                    if baseline_value == 0
                    else "Relative change uses (current - baseline) / abs(baseline) * 100."
                ),
                "aggregation_method": _comparison_method(aggregation),
            },
            "completeness": {
                "partial": (
                    current["completeness"]["partial"]
                    or baseline["completeness"]["partial"]
                ),
                "truncated": (
                    current["completeness"]["truncated"]
                    or baseline["completeness"]["truncated"]
                ),
                "warnings": current["completeness"]["warnings"]
                + baseline["completeness"]["warnings"],
                "current_evidence_id": current["evidence_id"],
                "baseline_evidence_id": baseline["evidence_id"],
            },
        }

    def list_fired_alerts(
        self,
        *,
        subscription_id: str,
        start: datetime,
        end: datetime,
        limit: int | None = None,
    ) -> dict[str, Any]:
        self._authorize_subscription_wide_monitoring()
        _validate_alert_window(self.config, start, end)
        row_limit = self._limit(limit)
        parameters = {
            "customTimeRange": f"{_utc_iso(start)}/{_utc_iso(end)}",
            "monitorCondition": "Fired",
        }
        return self._collect_arm_pages(
            subscription_id=subscription_id,
            collection="fired_alerts",
            parameters=parameters,
            start=start,
            end=end,
            limit=row_limit,
            source="Azure Monitor fired alerts",
            operation="list_fired_alerts",
        )

    def list_monitoring_definitions(
        self, *, subscription_id: str, category: str
    ) -> dict[str, Any]:
        self._authorize_subscription_wide_monitoring()
        if category not in {
            "metric_alert_rules",
            "scheduled_query_rules",
            "activity_log_alert_rules",
            "action_groups",
        }:
            raise AzurePortalValidationError(
                "Unsupported monitoring definition category."
            )
        return self._collect_arm_pages(
            subscription_id=subscription_id,
            collection=category,
            parameters={},
            start=None,
            end=None,
            limit=self.config.max_rows,
            source="Azure Monitor definition",
            operation=f"list_{category}",
        )

    def get_activity_log(
        self,
        *,
        subscription_id: str,
        start: datetime,
        end: datetime,
        limit: int | None = None,
    ) -> dict[str, Any]:
        _validate_window(self.config, start, end)
        subscription = self.config.authorize_subscription(subscription_id)
        row_limit = self._limit(limit)
        records: list[dict[str, Any]] = []
        warnings: list[str] = []
        request_id: str | None = None
        pages = 0
        next_url: str | None = None
        expected_parameters: Mapping[str, str] | None = None
        if self.config.resource_id_allowlist:
            scopes = [
                {"resource_id": item}
                for item in self.config.resource_id_allowlist
                if item.lower().startswith(f"/subscriptions/{subscription.lower()}/")
            ]
            if not scopes:
                raise AzurePortalValidationError(
                    "No configured resource IDs are in the requested subscription."
                )
        elif self.config.resource_group_allowlist:
            scopes = [
                {"resource_group": group}
                for group in self.config.resource_group_allowlist
            ]
        else:
            scopes = [{}]
        expected_path = (
            f"/subscriptions/{subscription}/providers/"
            "Microsoft.Insights/eventtypes/management/values"
        )
        truncated = False
        for scope_index, scope_filter in enumerate(scopes):
            next_url = None
            expected_parameters = None
            while pages < self.config.max_pages and len(records) < row_limit:
                if next_url:
                    response = self.transport.get_arm_continuation(
                        url=next_url,
                        expected_path=expected_path,
                        subscription_id=subscription,
                        operation="activity_log",
                        expected_parameters=expected_parameters,
                    )
                else:
                    response = self.transport.get_activity_log(
                        subscription_id=subscription,
                        start=start,
                        end=end,
                        top=row_limit - len(records),
                        **scope_filter,
                    )
                    expected_parameters = response.request_parameters
                pages += 1
                request_id = response.request_id or request_id
                warnings.extend(response.warnings)
                page_records = _value_records(response.payload)
                records.extend(
                    _redact_records(page_records)[: max(0, row_limit - len(records))]
                )
                link = response.payload.get("nextLink")
                next_url = link if isinstance(link, str) and link else None
                if not next_url or not page_records:
                    break
            if next_url or len(records) >= row_limit:
                truncated = bool(next_url) or scope_index < len(scopes) - 1
                break
            if pages >= self.config.max_pages and scope_index < len(scopes) - 1:
                truncated = True
                break
        return {
            "evidence_id": str(uuid.uuid4()),
            "retrieved_at": _now_utc(),
            "scope": {
                "subscription_id": subscription,
                "resource_groups": list(self.config.resource_group_allowlist),
                "resource_ids": [
                    _redact_identifier(item)
                    for item in self.config.resource_id_allowlist
                    if item.lower().startswith(f"/subscriptions/{subscription.lower()}/")
                ],
            },
            "source": "Azure Activity Log",
            "operation": "get_activity_log",
            "window": {"start_utc": _utc_iso(start), "end_utc": _utc_iso(end)},
            "query_parameters": {
                "limit": row_limit,
                "resource_groups": list(self.config.resource_group_allowlist),
                "resource_ids": [
                    _redact_identifier(item)
                    for item in self.config.resource_id_allowlist
                    if item.lower().startswith(f"/subscriptions/{subscription.lower()}/")
                ],
            },
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

    def get_diagnostic_settings(self, *, resource_id: str) -> dict[str, Any]:
        safe_id = self.config.authorize_resource_id(resource_id)
        response = self.transport.get_diagnostic_settings(safe_id)
        records = _redact_records(_value_records(response.payload))[
            : self.config.max_rows
        ]
        return {
            "evidence_id": str(uuid.uuid4()),
            "retrieved_at": _now_utc(),
            "scope": {"resource_id": _redact_identifier(safe_id)},
            "source": "Azure Monitor diagnostic settings definition",
            "operation": "get_diagnostic_settings",
            "returned_count": len(records),
            "records": records,
            "completeness": {
                "partial": bool(response.warnings),
                "truncated": len(_value_records(response.payload)) > self.config.max_rows,
                "warnings": list(response.warnings),
                "request_id": response.request_id,
            },
        }

    def _collect_arm_pages(
        self,
        *,
        subscription_id: str,
        collection: str,
        parameters: Mapping[str, str],
        start: datetime | None,
        end: datetime | None,
        limit: int,
        source: str,
        operation: str,
    ) -> dict[str, Any]:
        subscription = self.config.authorize_subscription(subscription_id)
        records: list[dict[str, Any]] = []
        warnings: list[str] = []
        pages = 0
        request_id: str | None = None
        next_url: str | None = None
        expected_path = ""
        while pages < self.config.max_pages and len(records) < limit:
            if next_url:
                response = self.transport.get_arm_continuation(
                    url=next_url,
                    expected_path=expected_path,
                    subscription_id=subscription,
                    operation=collection,
                    expected_parameters=parameters,
                )
            else:
                response = self.transport.list_subscription_collection(
                    subscription_id=subscription,
                    collection=collection,
                    parameters=parameters,
                )
                expected_path = _collection_path(subscription, collection)
            pages += 1
            request_id = response.request_id or request_id
            warnings.extend(response.warnings)
            page_records = _value_records(response.payload)
            records.extend(_redact_records(page_records)[: max(0, limit - len(records))])
            link = response.payload.get("nextLink")
            next_url = link if isinstance(link, str) and link else None
            if not next_url or not page_records:
                break
        return {
            "evidence_id": str(uuid.uuid4()),
            "retrieved_at": _now_utc(),
            "scope": {"subscription_id": subscription},
            "source": source,
            "operation": operation,
            "window": (
                {"start_utc": _utc_iso(start), "end_utc": _utc_iso(end)}
                if start is not None and end is not None
                else None
            ),
            "query_parameters": dict(parameters),
            "returned_count": len(records),
            "records": records,
            "completeness": {
                "partial": bool(warnings),
                "truncated": bool(next_url),
                "pages": pages,
                "warnings": list(dict.fromkeys(warnings)),
                "request_id": request_id,
            },
        }

    def _resolve_workspace(
        self, *, workspace_id: str | None, application_resource_id: str | None
    ) -> str:
        if (workspace_id is None) == (application_resource_id is None):
            raise AzurePortalValidationError(
                "Specify exactly one authorized workspace ID or Application Insights resource ID."
            )
        if workspace_id is not None:
            return self.config.authorize_workspace(workspace_id).workspace_id
        if self.resource_client is None:
            raise AzurePortalValidationError(
                "Application Insights workspace mapping client is unavailable."
            )
        scope = self.resource_client.resolve_workspace_for_application(
            application_resource_id=application_resource_id
        )
        return self.config.authorize_workspace(scope.workspace_id).workspace_id

    def _authorize_subscription_wide_monitoring(self) -> None:
        if (
            self.config.resource_group_allowlist
            or self.config.resource_id_allowlist
        ):
            raise AzurePortalValidationError(
                "Subscription-wide monitoring inventory is disabled when a narrower "
                "resource or resource-group allowlist is configured."
            )

    def _limit(self, limit: int | None) -> int:
        value = self.config.max_rows if limit is None else limit
        if not isinstance(value, int) or value < 1:
            raise AzurePortalValidationError("Result limit must be a positive integer.")
        return min(value, self.config.max_rows)

    @staticmethod
    def _evidence(
        *,
        response: AzureAPIResult,
        source: str,
        operation: str,
        scope: dict[str, Any],
        start: datetime,
        end: datetime,
        query: str,
        query_parameters: dict[str, Any],
        records: list[dict[str, Any]],
        warnings: list[str],
        truncated: bool,
    ) -> dict[str, Any]:
        return {
            "evidence_id": str(uuid.uuid4()),
            "retrieved_at": _now_utc(),
            "scope": scope,
            "source": source,
            "operation": operation,
            "window": {"start_utc": _utc_iso(start), "end_utc": _utc_iso(end)},
            "query": _redact_query(query),
            "query_parameters": query_parameters,
            "returned_count": len(records),
            "records": records,
            "completeness": {
                "partial": bool(warnings),
                "truncated": truncated,
                "warnings": list(dict.fromkeys(warnings)),
                "request_id": response.request_id,
            },
        }

    @staticmethod
    def _find_metric_definition(
        payload: Mapping[str, Any], metric_name: str
    ) -> dict[str, Any]:
        values = payload.get("value", [])
        if not isinstance(values, list):
            raise AzurePortalAPIError(
                "malformed_response", "Metric definitions response has no value array."
            )
        for item in values:
            if not isinstance(item, dict):
                continue
            name = _nested_value(item, "name", "value")
            if name == metric_name:
                supported = item.get("supportedAggregationTypes", [])
                if not isinstance(supported, list):
                    supported = []
                dimensions = item.get("dimensions", [])
                if not isinstance(dimensions, list):
                    dimensions = []
                return {
                    "name": name,
                    "unit": item.get("unit"),
                    "supported_aggregations": supported,
                    "dimensions": dimensions,
                    "time_grains": _time_grains(item),
                }
        raise AzurePortalValidationError(
            f"Metric '{metric_name}' is not defined for the selected resource."
        )


def _validate_window(
    config: AzurePortalAuthConfig, start: datetime, end: datetime
) -> None:
    if start.tzinfo is None or end.tzinfo is None:
        raise AzurePortalValidationError("Time-window values must be timezone-aware.")
    if end <= start:
        raise AzurePortalValidationError("Time-window end must be after its start.")
    duration = end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    if duration > timedelta(days=config.max_window_days):
        raise AzurePortalValidationError(
            f"Time window exceeds AZUREPORTAL_MAX_WINDOW_DAYS ({config.max_window_days})."
        )


def _validate_alert_window(
    config: AzurePortalAuthConfig, start: datetime, end: datetime
) -> None:
    _validate_window(config, start, end)
    now = datetime.now(timezone.utc)
    if start.astimezone(timezone.utc) < now - timedelta(days=30):
        raise AzurePortalValidationError(
            "Fired-alert queries support custom ranges only within the prior 30 days."
        )
    if end.astimezone(timezone.utc) > now + timedelta(minutes=5):
        raise AzurePortalValidationError(
            "Fired-alert query end cannot be more than five minutes in the future."
        )


def _table_rows(payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    tables = payload.get("tables", [])
    warnings: list[str] = []
    if not isinstance(tables, list):
        raise AzurePortalAPIError(
            "malformed_response", "Azure Logs response has no tables array."
        )
    if not tables:
        return [], warnings
    table = tables[0]
    if not isinstance(table, dict):
        raise AzurePortalAPIError("malformed_response", "Azure Logs table is malformed.")
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise AzurePortalAPIError("malformed_response", "Azure Logs table is malformed.")
    names = [
        column.get("name")
        for column in columns
        if isinstance(column, dict) and isinstance(column.get("name"), str)
    ]
    results = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(names):
            warnings.append("Azure Logs returned a row with an unexpected column shape.")
            continue
        results.append(dict(zip(names, row)))
    if payload.get("error"):
        warnings.append("Azure Logs returned an API warning or partial-result error.")
    return results, warnings


def _redact_record(record: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in record.items():
        if _SENSITIVE_FIELD.search(key):
            result[key] = "[REDACTED]"
        else:
            result[key] = _redact_value(value)
    return result


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _SENSITIVE_VALUE.sub("[REDACTED]", value)[:1000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if _SENSITIVE_FIELD.search(str(key))
                else _redact_value(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(child) for child in value[:100]]
    return "[REDACTED]"


def _redact_records(records: list[Any]) -> list[dict[str, Any]]:
    return [_redact_record(record) for record in records if isinstance(record, dict)]


def _value_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("value", [])
    if not isinstance(value, list):
        raise AzurePortalAPIError(
            "malformed_response", "Azure response does not contain a value array."
        )
    return [record for record in value if isinstance(record, dict)]


def _metric_series(
    payload: Mapping[str, Any], *, max_series: int
) -> tuple[list[dict[str, Any]], bool]:
    values = payload.get("value", [])
    if not isinstance(values, list):
        raise AzurePortalAPIError(
            "malformed_response", "Azure Monitor metrics response has no value array."
        )
    output: list[dict[str, Any]] = []
    truncated = len(values) > max_series
    point_budget = max_series
    for item in values[:max_series]:
        if not isinstance(item, dict):
            continue
        timeseries = item.get("timeseries", [])
        if not isinstance(timeseries, list):
            continue
        for series in timeseries:
            if not isinstance(series, dict):
                continue
            data = series.get("data", [])
            if not isinstance(data, list):
                continue
            if len(data) > point_budget:
                truncated = True
            selected = data[:point_budget]
            output.append(
                {
                    "metadata_values": _redact_records(
                        series.get("metadatavalues", [])
                    ),
                    "data": [
                        _redact_record(point)
                        for point in selected
                        if isinstance(point, dict)
                    ],
                }
            )
            point_budget -= len(selected)
            if point_budget <= 0:
                truncated = True
                return output, truncated
            if len(output) >= max_series:
                truncated = True
                return output, truncated
    return output, truncated


def _metric_dimension_filter(
    requested: Mapping[str, str], dimensions: list[dict[str, Any]]
) -> str:
    available = {
        dimension.get("value")
        for dimension in dimensions
        if isinstance(dimension, dict) and isinstance(dimension.get("value"), str)
    }
    clauses = []
    for name, value in requested.items():
        if name not in available:
            raise AzurePortalValidationError(
                f"Metric dimension '{name}' is not defined for this metric."
            )
        if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
            raise AzurePortalValidationError("Metric dimension value is invalid.")
        clauses.append(f"{name} eq '{_odata_string(value)}'")
    if available != set(requested):
        raise AzurePortalValidationError(
            "A value filter is required for every metric dimension to bound time-series fan-out."
        )
    return " and ".join(clauses)


def _validate_metric_volume(
    *, start: datetime, end: datetime, interval: str, max_points: int
) -> None:
    match = re.fullmatch(
        r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?",
        interval,
    )
    if match is None:
        raise AzurePortalValidationError(
            "Metric time grain must be a supported ISO-8601 duration."
        )
    days, hours, minutes, seconds = match.groups()
    interval_seconds = (
        int(days or 0) * 86400
        + int(hours or 0) * 3600
        + int(minutes or 0) * 60
        + float(seconds or 0)
    )
    if interval_seconds <= 0:
        raise AzurePortalValidationError("Metric time grain must be greater than zero.")
    duration_seconds = (
        end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    ).total_seconds()
    if math.ceil(duration_seconds / interval_seconds) > max_points:
        raise AzurePortalValidationError(
            f"Metric window exceeds the configured {max_points}-point bound at "
            f"time grain {interval}."
        )


def _aggregate_metric(
    series: list[dict[str, Any]], aggregation: str
) -> tuple[float | None, int | None, int]:
    points = [
        point
        for item in series
        for point in item["data"]
        if isinstance(point, dict)
    ]
    if aggregation == "Average":
        weighted_sum = 0.0
        sample_count = 0
        for point in points:
            average = point.get("average")
            count = point.get("count")
            if average is None or count is None:
                raise AzurePortalValidationError(
                    "Cannot compare Average metric windows without per-bucket average and count values."
                )
            weighted_sum += float(average) * int(count)
            sample_count += int(count)
        return (
            weighted_sum / sample_count if sample_count else None,
            sample_count,
            len(points),
        )
    field = {
        "Count": "count",
        "Total": "total",
        "Minimum": "minimum",
        "Maximum": "maximum",
    }.get(aggregation)
    if field is None:
        raise AzurePortalValidationError(
            f"Metric comparison aggregation '{aggregation}' is unsupported."
        )
    values = [
        float(point[field])
        for point in points
        if point.get(field) is not None
    ]
    if not values:
        return None, None, 0
    if aggregation in {"Minimum", "Maximum"}:
        return (
            min(values) if aggregation == "Minimum" else max(values),
            None,
            len(values),
        )
    if aggregation == "Count":
        count = int(sum(values))
        return float(count), count, len(values)
    return sum(values), None, len(values)


def _comparison_method(aggregation: str) -> str:
    if aggregation == "Average":
        return "count-weighted mean of per-bucket averages; no unweighted averaging"
    if aggregation in {"Minimum", "Maximum"}:
        return f"{aggregation.lower()} across the returned buckets"
    return f"sum of returned {aggregation.lower()} bucket values"


def _time_grains(definition: Mapping[str, Any]) -> list[str]:
    availabilities = definition.get("metricAvailabilities", [])
    result = []
    if isinstance(availabilities, list):
        for item in availabilities:
            if not isinstance(item, dict):
                continue
            grain = item.get("timeGrain")
            if isinstance(grain, str) and grain not in result:
                result.append(grain)
    return result


def _nested_value(value: Mapping[str, Any], parent: str, child: str) -> Any:
    nested = value.get(parent)
    return nested.get(child) if isinstance(nested, dict) else None


def _kusto_string(value: str) -> str:
    return value.replace("'", "''")


def _odata_string(value: str) -> str:
    return value.replace("'", "''")


def _redact_query(query: str) -> str:
    return re.sub(r"'(?:''|[^'])*'", "'[REDACTED]'", query)


def _redact_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    return (
        "[REDACTED]"
        if _SENSITIVE_FIELD.search(value) or _SENSITIVE_VALUE.search(value)
        else _SENSITIVE_VALUE.sub("[REDACTED]", value)
    )


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collection_path(subscription_id: str, collection: str) -> str:
    from azureportal_transport import _COLLECTIONS

    return (
        f"/subscriptions/{subscription_id}/providers/"
        f"{_COLLECTIONS[collection][0]}"
    )
