"""Mocked safety, scope, evidence, and Azure API contract tests."""

from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = ROOT / ".github" / "skills" / "azureportal-authentication"
RESOURCE_PATH = ROOT / ".github" / "skills" / "azureportal-resource-operations"
MONITOR_PATH = ROOT / ".github" / "skills" / "azureportal-monitoring-operations"
for path in (AUTH_PATH, RESOURCE_PATH, MONITOR_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from azureportal_env import (  # noqa: E402
    AzurePortalAuthConfig,
    AzurePortalAuthConfigError,
    AzureWorkspaceScope,
    create_azure_credential,
    load_azureportal_auth_config_from_env,
)
from azureportal_monitoring_client import (  # noqa: E402
    AzurePortalMonitoringClient,
    _aggregate_metric,
)
from azureportal_resource_client import AzurePortalResourceClient  # noqa: E402
from azureportal_query_templates import (  # noqa: E402
    build_logs_query,
    build_resource_graph_query,
)
from azureportal_transport import (  # noqa: E402
    ARM_SCOPE,
    LOGS_SCOPE,
    AzureAPIResult,
    AzurePortalAPIError,
    AzurePortalTransport,
    AzurePortalValidationError,
)


TENANT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SUBSCRIPTION = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
WORKSPACE = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
WORKSPACE_ARM_ID = (
    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/monitoring/providers/"
    "Microsoft.OperationalInsights/workspaces/workspace-a"
)
RESOURCE_ID = (
    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/apps/providers/"
    "Microsoft.Compute/virtualMachines/vm-a"
)
START = datetime(2026, 10, 29, 10, tzinfo=timezone.utc)
END = START + timedelta(hours=1)


def config(**overrides) -> AzurePortalAuthConfig:
    values = {
        "auth_mode": "azure_cli",
        "tenant_id": TENANT,
        "subscription_ids": (SUBSCRIPTION,),
        "workspace_scopes": {
            WORKSPACE: AzureWorkspaceScope(
                WORKSPACE, WORKSPACE_ARM_ID, SUBSCRIPTION
            )
        },
        "max_window_days": 30,
        "max_rows": 20,
        "max_pages": 3,
        "timeout_seconds": 5,
        "max_concurrent_requests": 2,
    }
    values.update(overrides)
    return AzurePortalAuthConfig(**values)


def env_values(**overrides) -> dict[str, str]:
    values = {
        "AZUREPORTAL_AUTH_MODE": "azure_cli",
        "AZUREPORTAL_TENANT_ID": TENANT,
        "AZUREPORTAL_SUBSCRIPTION_IDS": SUBSCRIPTION,
        "AZUREPORTAL_WORKSPACE_MAP": json.dumps({WORKSPACE: WORKSPACE_ARM_ID}),
    }
    values.update(overrides)
    return values


class FakeResponse:
    def __init__(
        self,
        payload: dict | None = None,
        status_code: int = 200,
        headers: dict | None = None,
    ) -> None:
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [FakeResponse()])
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class FakeCredential:
    def __init__(self):
        self.scopes = []

    def get_token(self, scope):
        self.scopes.append(scope)
        return SimpleNamespace(token="fake-access-token")


def api_result(
    payload: dict, *, status=200, request_id="request-id", query=None
) -> AzureAPIResult:
    return AzureAPIResult(payload, status, request_id, (), query)


class TestAzurePortalEnvironment(unittest.TestCase):
    def test_explicit_mode_and_scope_load(self):
        with patch.dict(os.environ, env_values(), clear=True):
            result = load_azureportal_auth_config_from_env()
        self.assertEqual(result.auth_mode, "azure_cli")
        self.assertEqual(result.tenant_id, TENANT)
        self.assertEqual(result.subscription_ids, (SUBSCRIPTION,))
        self.assertEqual(result.authorize_workspace(WORKSPACE).resource_id, WORKSPACE_ARM_ID)

    def test_auth_mode_is_required_and_no_fallback_is_allowed(self):
        for mode in ("", "auto", "default"):
            with self.subTest(mode=mode), patch.dict(
                os.environ, env_values(AZUREPORTAL_AUTH_MODE=mode), clear=True
            ):
                with self.assertRaises(AzurePortalAuthConfigError):
                    load_azureportal_auth_config_from_env()

    def test_invalid_tenant_or_subscription_is_rejected(self):
        with patch.dict(
            os.environ, env_values(AZUREPORTAL_TENANT_ID="not-a-guid"), clear=True
        ):
            with self.assertRaises(AzurePortalAuthConfigError):
                load_azureportal_auth_config_from_env()
        with patch.dict(
            os.environ,
            env_values(AZUREPORTAL_SUBSCRIPTION_IDS="not-a-guid"),
            clear=True,
        ):
            with self.assertRaises(AzurePortalAuthConfigError):
                load_azureportal_auth_config_from_env()

    def test_workspace_mapping_must_be_guid_to_verified_arm_id(self):
        invalid = {
            "AZUREPORTAL_WORKSPACE_MAP": json.dumps({WORKSPACE: RESOURCE_ID})
        }
        with patch.dict(os.environ, env_values(**invalid), clear=True):
            with self.assertRaises(AzurePortalAuthConfigError):
                load_azureportal_auth_config_from_env()

    def test_workspace_and_resource_scope_enforced(self):
        cfg = config(resource_group_allowlist=("apps",))
        with self.assertRaises(AzurePortalAuthConfigError):
            cfg.authorize_resource_id(RESOURCE_ID.replace("/apps/", "/other/"))
        with self.assertRaises(AzurePortalAuthConfigError):
            cfg.authorize_subscription(TENANT)

    def test_exact_resource_allowlist_is_enforced(self):
        cfg = config(resource_id_allowlist=(RESOURCE_ID,))
        self.assertEqual(cfg.authorize_resource_id(RESOURCE_ID), RESOURCE_ID)
        with self.assertRaises(AzurePortalAuthConfigError):
            cfg.authorize_resource_id(RESOURCE_ID + "/extensions/one")

    def test_mode_conditional_variables_are_validated(self):
        with patch.dict(
            os.environ,
            env_values(
                AZUREPORTAL_AUTH_MODE="service_principal",
                AZUREPORTAL_CLIENT_ID="client-id",
            ),
            clear=True,
        ):
            with self.assertRaises(AzurePortalAuthConfigError):
                load_azureportal_auth_config_from_env()
        with patch.dict(
            os.environ,
            env_values(AZUREPORTAL_CLIENT_SECRET="unused-secret"),
            clear=True,
        ):
            with self.assertRaises(AzurePortalAuthConfigError):
                load_azureportal_auth_config_from_env()

    def test_numeric_limits_are_finite(self):
        with patch.dict(
            os.environ, env_values(AZUREPORTAL_MAX_ROWS="5001"), clear=True
        ):
            with self.assertRaises(AzurePortalAuthConfigError):
                load_azureportal_auth_config_from_env()

    def test_selected_identity_constructs_exact_credential(self):
        from azure import identity

        with patch.object(identity, "AzureCliCredential") as cli:
            create_azure_credential(config())
        cli.assert_called_once_with(tenant_id=TENANT)
        with patch.object(identity, "ManagedIdentityCredential") as managed:
            create_azure_credential(
                config(auth_mode="managed_identity", managed_identity_client_id="mi-id")
            )
        managed.assert_called_once_with(client_id="mi-id")
        with patch.object(identity, "ClientSecretCredential") as sp:
            create_azure_credential(
                config(
                    auth_mode="service_principal",
                    service_principal_client_id="client-id",
                    service_principal_secret="do-not-print",
                )
            )
        sp.assert_called_once_with(
            tenant_id=TENANT,
            client_id="client-id",
            client_secret="do-not-print",
        )
        self.assertNotIn("do-not-print", repr(config(service_principal_secret="do-not-print")))


class TestAzurePortalTransport(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.credential = FakeCredential()
        self.session = FakeSession()
        self.delays = []
        self.transport = AzurePortalTransport(
            self.cfg, self.credential, session=self.session, sleep=self.delays.append
        )

    def test_resource_graph_post_is_an_allowed_read_query(self):
        self.session.responses = [FakeResponse({"data": []})]
        self.transport.query_resource_graph(operation="list_resources", top=5)
        method, url, kwargs = self.session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://management.azure.com/providers/Microsoft.ResourceGraph/resources")
        self.assertEqual(kwargs["json"]["subscriptions"], [SUBSCRIPTION])
        self.assertEqual(self.credential.scopes, [ARM_SCOPE])

    def test_logs_post_uses_workspace_scope_and_distinct_audience(self):
        self.session.responses = [FakeResponse({"tables": []})]
        self.transport.query_application_telemetry(
            workspace_id=WORKSPACE,
            category="requests",
            start=START,
            end=END,
            limit=1,
        )
        method, url, kwargs = self.session.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn(f"/v1/workspaces/{WORKSPACE}/query", url)
        self.assertEqual(self.credential.scopes, [LOGS_SCOPE])
        self.assertEqual(
            kwargs["json"]["timespan"],
            "2026-10-29T10:00:00Z/2026-10-29T11:00:00Z",
        )

    def test_unknown_method_mutation_or_endpoint_is_rejected(self):
        for method, operation, path in (
            ("DELETE", "metric_series", RESOURCE_ID + "/providers/Microsoft.Insights/metrics"),
            ("POST", "unknown", "/subscriptions/" + SUBSCRIPTION + "/delete"),
        ):
            with self.subTest(method=method):
                with self.assertRaises(AzurePortalValidationError):
                    self.transport._request(
                        host="management.azure.com",
                        path=path,
                        service="arm",
                        operation=operation,
                        method=method,
                    )
        self.assertEqual(self.session.calls, [])

    def test_activity_log_filter_is_scoped_and_uses_documented_parameters(self):
        scoped = AzurePortalTransport(
            config(resource_group_allowlist=("apps",)),
            self.credential,
            session=self.session,
            sleep=self.delays.append,
        )
        self.session.responses = [FakeResponse({"value": []})]
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)
        scoped.get_activity_log(
            subscription_id=SUBSCRIPTION,
            start=start,
            end=end,
            top=10,
            resource_group="apps",
        )
        parameters = self.session.calls[0][2]["params"]
        self.assertIn("resourceGroupName eq 'apps'", parameters["$filter"])
        self.assertNotIn("$top", parameters)
        with self.assertRaises(AzurePortalValidationError):
            scoped.get_activity_log(
                subscription_id=SUBSCRIPTION,
                start=start,
                end=end,
                top=10,
                resource_group="other",
            )
        self.assertEqual(len(self.session.calls), 1)

    def test_cross_workspace_and_untrusted_hosts_are_rejected_before_request(self):
        with self.assertRaises(AzurePortalAuthConfigError):
            self.transport.query_application_telemetry(
                workspace_id=TENANT,
                category="requests",
                start=START,
                end=END,
                limit=1,
            )
        with self.assertRaises(AzurePortalValidationError):
            self.transport._request(
                host="example.org",
                path="/v1/workspaces/" + WORKSPACE + "/query",
                service="logs",
                operation="bounded_logs_query",
                method="POST",
                json_body={"query": "AppRequests"},
            )
        self.assertEqual(self.session.calls, [])

    def test_redirect_is_never_followed(self):
        self.session.responses = [
            FakeResponse({}, 302, {"Location": "https://attacker.example/"})
        ]
        with self.assertRaises(AzurePortalAPIError) as caught:
            self.transport.query_resource_graph(operation="list_resources", top=5)
        self.assertEqual(caught.exception.code, "redirect_rejected")
        self.assertFalse(self.session.calls[0][2]["allow_redirects"])

    def test_continuation_must_keep_host_path_subscription_and_version(self):
        expected = (
            f"/subscriptions/{SUBSCRIPTION}/providers/Microsoft.Insights/metricAlerts"
        )
        for url in (
            "https://evil.example" + expected + "?api-version=2018-03-01",
            "https://management.azure.com" + expected.replace(SUBSCRIPTION, TENANT)
            + "?api-version=2018-03-01",
            "https://management.azure.com" + expected + "?api-version=2099-01-01",
            "https://management.azure.com" + expected + "?api-version=2018-03-01&x=1",
        ):
            with self.subTest(url=url), self.assertRaises(AzurePortalValidationError):
                self.transport.get_arm_continuation(
                    url=url,
                    expected_path=expected,
                    subscription_id=SUBSCRIPTION,
                    operation="metric_alert_rules",
                )
        self.assertEqual(self.session.calls, [])

    def test_429_honors_bounded_retry_after(self):
        self.session.responses = [
            FakeResponse({}, 429, {"Retry-After": "100"}),
            FakeResponse({"data": []}),
        ]
        self.transport.query_resource_graph(operation="list_resources", top=5)
        self.assertEqual(self.delays, [30.0])
        self.assertEqual(len(self.session.calls), 2)

    def test_permission_and_malformed_response_errors_are_explicit(self):
        self.session.responses = [FakeResponse({}, 403)]
        with self.assertRaises(AzurePortalAPIError) as caught:
            self.transport.query_resource_graph(operation="list_resources", top=5)
        self.assertEqual(caught.exception.code, "forbidden")
        self.session.responses = [FakeResponse([])]
        with self.assertRaises(AzurePortalAPIError) as caught:
            self.transport.query_resource_graph(operation="list_resources", top=5)
        self.assertEqual(caught.exception.code, "malformed_response")

    def test_time_row_and_page_bounds_are_enforced(self):
        with self.assertRaises(AzurePortalValidationError):
            self.transport.query_resource_graph(operation="list_resources", top=0)
        with self.assertRaises(AzurePortalValidationError):
            self.transport.query_application_telemetry(
                workspace_id=WORKSPACE,
                category="requests",
                start=START.replace(tzinfo=None),
                end=END,
                limit=1,
            )
        with self.assertRaises(AzurePortalValidationError):
            self.transport.query_application_telemetry(
                workspace_id=WORKSPACE,
                category="requests",
                start=START - timedelta(days=31),
                end=END,
                limit=1,
            )


class FakeResourceClient:
    def __init__(self, scope):
        self.scope = scope
        self.arguments = []

    def resolve_workspace_for_application(self, *, application_resource_id):
        self.arguments.append(application_resource_id)
        return self.scope


class FakeMonitorTransport:
    def __init__(self, *, log_payload=None, definitions=None, metric_payloads=None):
        self.log_payload = log_payload or {
            "tables": [{"columns": [{"name": "Message"}], "rows": []}]
        }
        self.definition_payload = definitions or {"value": []}
        self.metric_payloads = list(metric_payloads or [])
        self.calls = []

    def _logs(self, operation, **kwargs):
        self.calls.append(("logs", kwargs))
        template_args = {key: value for key, value in kwargs.items() if key != "workspace_id"}
        query = build_logs_query(operation=operation, **template_args)
        return api_result(self.log_payload, query=query)

    def query_application_telemetry(self, **kwargs):
        return self._logs("application_telemetry", **kwargs)

    def query_table_metadata(self, **kwargs):
        return self._logs("table_metadata", **kwargs)

    def query_request_error_trend(self, **kwargs):
        return self._logs("request_error_trend", **kwargs)

    def query_exception_groups(self, **kwargs):
        return self._logs("exception_groups", **kwargs)

    def get_metric_definitions(self, resource_id):
        self.calls.append(("definitions", resource_id))
        return api_result(self.definition_payload)

    def get_metrics(self, *, resource_id, parameters):
        self.calls.append(("metrics", resource_id, parameters))
        return api_result(self.metric_payloads.pop(0))

    def list_subscription_collection(self, **kwargs):
        self.calls.append(("collection", kwargs))
        return api_result({"value": []})


def metric_definition():
    return {
        "value": [
            {
                "id": "metric-definition-id",
                "name": {"value": "Requests", "localizedValue": "Requests"},
                "namespace": "Microsoft.Compute/virtualMachines",
                "unit": "Count",
                "primaryAggregationType": "Total",
                "supportedAggregationTypes": ["Average", "Count", "Total"],
                "dimensions": [{"value": "Instance", "localizedValue": "Instance"}],
                "metricAvailabilities": [{"timeGrain": "PT1M"}],
            }
        ]
    }


def metric_payload(points):
    return {
        "value": [
            {
                "name": {"value": "Requests"},
                "timeseries": [{"metadatavalues": [], "data": points}],
            }
        ]
    }


class TestAzurePortalResourceOperations(unittest.TestCase):
    def test_resource_graph_group_filter_cannot_escape_allowlist(self):
        with self.assertRaises(AzurePortalValidationError):
            build_resource_graph_query(
                operation="list_resources",
                resource_group_allowlist=("apps",),
                resource_id_allowlist=(),
                resource_group="other",
            )
        query = build_resource_graph_query(
            operation="list_resources",
            resource_group_allowlist=("apps",),
            resource_id_allowlist=(),
            resource_group="APPS",
        )
        self.assertIn("resourceGroup =~ 'APPS'", query)

    def test_ambiguous_names_are_not_resolved_by_first_match(self):
        transport = FakeMonitorTransport()
        client = AzurePortalResourceClient(config(), transport)
        client._run_paged_query = lambda **kwargs: {
            "records": [
                {"id": RESOURCE_ID, "name": "vm"},
                {"id": RESOURCE_ID + "-other", "name": "vm"},
            ],
            "completeness": {"truncated": False},
        }
        result = client.resolve_resource(name_or_id="vm")
        self.assertEqual(result["resolution"], "ambiguous")
        self.assertNotIn("resource", result)

    def test_resource_metadata_output_redacts_sensitive_tags(self):
        class ResourceTransport:
            def query_resource_graph(self, **kwargs):
                return api_result(
                    {
                        "data": [
                            {
                                "id": RESOURCE_ID,
                                "name": "vm-a",
                                "tags": {
                                    "owner": "team",
                                    "client-secret": "sensitive",
                                },
                            }
                        ]
                    },
                    query="Resources | project id",
                )

        transport = ResourceTransport()
        client = AzurePortalResourceClient(config(), transport)
        result = client.get_resource_metadata(resource_id=RESOURCE_ID)
        self.assertEqual(result["resource"]["tags"]["owner"], "team")
        self.assertEqual(result["resource"]["tags"]["client-secret"], "[REDACTED]")

    def test_application_insights_mapping_uses_workspace_resource_arm_id(self):
        scope = config().workspace_scopes[WORKSPACE]
        resource_client = AzurePortalResourceClient(config(), FakeMonitorTransport())
        resource_client._run_paged_query = lambda **kwargs: {
            "records": [{"workspaceResourceId": scope.resource_id}],
            "completeness": {"truncated": False},
        }
        result = resource_client.resolve_workspace_for_application(
            application_resource_id=(
                f"/subscriptions/{SUBSCRIPTION}/resourceGroups/apps/providers/"
                "Microsoft.Insights/components/app-a"
            )
        )
        self.assertEqual(result.workspace_id, WORKSPACE)

    def test_app_id_without_workspace_mapping_is_rejected(self):
        resource_client = AzurePortalResourceClient(config(), FakeMonitorTransport())
        resource_client._run_paged_query = lambda **kwargs: {
            "records": [{"workspaceResourceId": ""}],
            "completeness": {"truncated": False},
        }
        with self.assertRaises(AzurePortalValidationError):
            resource_client.resolve_workspace_for_application(
                application_resource_id=(
                    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/apps/providers/"
                    "Microsoft.Insights/components/app-a"
                )
            )


class TestAzurePortalMonitoringOperations(unittest.TestCase):
    def test_fixed_template_query_provenance_and_telemetry_redaction(self):
        payload = {
            "tables": [
                {
                    "columns": [
                        {"name": "TimeGenerated"},
                        {"name": "Message"},
                        {"name": "Properties"},
                    ],
                    "rows": [
                        [
                            "2026-10-29T10:10:00Z",
                            "password=hunter2 user=person@example.com",
                            {"client-secret": "hidden", "safe": "ok"},
                        ]
                    ],
                }
            ]
        }
        transport = FakeMonitorTransport(log_payload=payload)
        client = AzurePortalMonitoringClient(config(), transport)
        result = client.query_telemetry(
            workspace_id=WORKSPACE,
            category="traces",
            start=START,
            end=END,
            service_name="api",
        )
        query = result["query"]
        self.assertIn("AppTraces", query)
        self.assertIn("TimeGenerated between", query)
        self.assertNotIn("Properties", query)
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["data_status"], "records_returned")
        self.assertIn("evidence_id", result)
        self.assertEqual(
            result["records"][0]["Message"],
            "[REDACTED] user=[REDACTED]",
        )

    def test_unsupported_category_and_cross_scope_are_rejected(self):
        client = AzurePortalMonitoringClient(config(), FakeMonitorTransport())
        with self.assertRaises(AzurePortalValidationError):
            client.query_telemetry(
                workspace_id=WORKSPACE,
                category="custom_query",
                start=START,
                end=END,
            )
        with self.assertRaises(AzurePortalAuthConfigError):
            client.query_telemetry(
                workspace_id=TENANT,
                category="requests",
                start=START,
                end=END,
            )

    def test_zero_records_are_distinguished_from_no_table(self):
        zero = AzurePortalMonitoringClient(
            config(),
            FakeMonitorTransport(
                log_payload={
                    "tables": [
                        {"columns": [{"name": "Name"}], "rows": []}
                    ]
                }
            ),
        ).query_telemetry(
            workspace_id=WORKSPACE, category="requests", start=START, end=END
        )
        missing = AzurePortalMonitoringClient(
            config(), FakeMonitorTransport(log_payload={"tables": []})
        ).query_telemetry(
            workspace_id=WORKSPACE, category="requests", start=START, end=END
        )
        self.assertEqual(zero["data_status"], "zero_matching_records")
        self.assertEqual(
            missing["data_status"],
            "no_table_returned_instrumentation_or_retention_unverified",
        )

    def test_metric_definitions_include_units_aggregation_dimensions_and_grains(self):
        client = AzurePortalMonitoringClient(
            config(),
            FakeMonitorTransport(definitions=metric_definition()),
        )
        result = client.list_metric_definitions(resource_id=RESOURCE_ID)
        definition = result["definitions"][0]
        self.assertEqual(definition["unit"], "Count")
        self.assertIn("Average", definition["supported_aggregations"])
        self.assertEqual(definition["dimensions"][0]["name"], "Instance")
        self.assertEqual(definition["time_grains"], ["PT1M"])
        self.assertEqual(definition["namespace"], "Microsoft.Compute/virtualMachines")

    def test_metric_query_validates_aggregation_grain_and_dimensions(self):
        transport = FakeMonitorTransport(definitions=metric_definition())
        client = AzurePortalMonitoringClient(config(), transport)
        with self.assertRaises(AzurePortalValidationError):
            client.query_metric(
                resource_id=RESOURCE_ID,
                metric_name="Unknown",
                aggregation="Average",
                interval="PT1M",
                start=START,
                end=END,
            )
        with self.assertRaises(AzurePortalValidationError):
            client.query_metric(
                resource_id=RESOURCE_ID,
                metric_name="Requests",
                aggregation="Average",
                interval="PT1H",
                start=START,
                end=END,
            )
        with self.assertRaises(AzurePortalValidationError):
            client.query_metric(
                resource_id=RESOURCE_ID,
                metric_name="Requests",
                aggregation="Average",
                interval="PT1M",
                start=START,
                end=END,
                dimensions={"Unknown": "x"},
            )
        with self.assertRaisesRegex(AzurePortalValidationError, "every metric dimension"):
            client.query_metric(
                resource_id=RESOURCE_ID,
                metric_name="Requests",
                aggregation="Average",
                interval="PT1M",
                start=START,
                end=START + timedelta(minutes=10),
            )
        with self.assertRaisesRegex(AzurePortalValidationError, "point bound"):
            client.query_metric(
                resource_id=RESOURCE_ID,
                metric_name="Requests",
                aggregation="Average",
                interval="PT1M",
                start=START,
                end=END,
                dimensions={"Instance": "vm-1"},
            )
        self.assertFalse(any(call[0] == "metrics" for call in transport.calls))

    def test_average_comparison_uses_weighted_means_and_exact_windows(self):
        transport = FakeMonitorTransport(
            definitions=metric_definition(),
            metric_payloads=[
                metric_payload(
                    [
                        {"average": 10, "count": 2},
                        {"average": 20, "count": 8},
                    ]
                ),
                metric_payload([{"average": 5, "count": 10}]),
            ],
        )
        result = AzurePortalMonitoringClient(config(max_rows=100), transport).compare_metric_windows(
            resource_id=RESOURCE_ID,
            metric_name="Requests",
            aggregation="Average",
            interval="PT1M",
            current_start=START,
            current_end=END,
            baseline_start=START - timedelta(hours=1),
            baseline_end=START,
            dimensions={"Instance": "vm-1"},
        )
        self.assertEqual(result["comparison"]["current_value"], 18)
        self.assertEqual(result["comparison"]["baseline_value"], 5)
        self.assertAlmostEqual(result["comparison"]["change_percent"], 260)
        metric_requests = [call for call in transport.calls if call[0] == "metrics"]
        self.assertEqual(
            metric_requests[0][2]["aggregation"], "Average,Count"
        )
        self.assertEqual(
            metric_requests[0][2]["$filter"], "Instance eq 'vm-1'"
        )
        self.assertEqual(metric_requests[0][2]["top"], "100")

    def test_metric_average_without_counts_is_rejected_and_zero_baseline_has_no_percent(self):
        with self.assertRaises(AzurePortalValidationError):
            _aggregate_metric(
                [{"data": [{"average": 10}]}],
                "Average",
            )
        result, samples, buckets = _aggregate_metric(
            [{"data": [{"total": 0}]}], "Total"
        )
        self.assertEqual(result, 0)
        self.assertIsNone(samples)
        self.assertEqual(buckets, 1)
        self.assertEqual(_aggregate_metric([], "Total"), (None, None, 0))
        current = 5
        baseline = 0
        change = (current - baseline) / abs(baseline) * 100 if baseline else None
        self.assertIsNone(change)

    def test_subscription_inventory_rejects_narrower_allowlists_before_request(self):
        cfg = config(resource_group_allowlist=("apps",))
        transport = FakeMonitorTransport()
        client = AzurePortalMonitoringClient(cfg, transport)
        with self.assertRaises(AzurePortalValidationError):
            client.list_monitoring_definitions(
                subscription_id=SUBSCRIPTION, category="metric_alert_rules"
            )
        self.assertEqual(transport.calls, [])

    def test_fired_alert_window_is_limited_to_thirty_days(self):
        transport = FakeMonitorTransport()
        client = AzurePortalMonitoringClient(config(), transport)
        now = datetime.now(timezone.utc)
        with self.assertRaisesRegex(AzurePortalValidationError, "prior 30 days"):
            client.list_fired_alerts(
                subscription_id=SUBSCRIPTION,
                start=now - timedelta(days=31),
                end=now - timedelta(days=31) + timedelta(hours=1),
            )
        self.assertEqual(transport.calls, [])
        result = client.list_fired_alerts(
            subscription_id=SUBSCRIPTION,
            start=now - timedelta(hours=1),
            end=now,
        )
        self.assertEqual(
            transport.calls[0][1]["parameters"]["monitorCondition"], "Fired"
        )
        self.assertEqual(result["returned_count"], 0)

    def test_grouped_exceptions_uses_bounded_fixed_template(self):
        transport = FakeMonitorTransport()
        client = AzurePortalMonitoringClient(config(), transport)
        result = client.group_application_exceptions(
            workspace_id=WORKSPACE, start=START, end=END, limit=7
        )
        query = result["query"]
        self.assertIn("AppExceptions", query)
        self.assertIn("summarize ExceptionCount=count()", query)
        self.assertIn("top 7", query)
        self.assertNotIn("externaldata", query.lower())


if __name__ == "__main__":
    unittest.main()
