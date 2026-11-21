---
name: 'azureportal-monitoring-operations'
description: 'Read-only bounded Azure Monitor Logs and workspace-based Application Insights telemetry, metric definitions and series, fired alerts, monitoring rules, Activity Log, diagnostic settings, and action-group metadata for Azure troubleshooting requests.'
keywords: ['azure', 'azureportal', 'logs', 'kql', 'application-insights', 'metrics', 'alerts', 'activity-log', 'diagnostic-settings']
---

# AzurePortal Monitoring Operations Skill

Use [azureportal_monitoring_client.py](azureportal_monitoring_client.py) after `azureportal-authentication` succeeds. All query and inventory operations are read-only and use fixed operations in [azureportal_transport.py](../azureportal-authentication/azureportal_transport.py).

## Supported Operations

- Query bounded workspace-based Application Insights tables `AppRequests`, `AppExceptions`, `AppDependencies`, `AppTraces`, and `AppAvailabilityResults` over explicit UTC windows.
- Map an Application Insights component ARM ID to a workspace through Resource Graph and the verified `AZUREPORTAL_WORKSPACE_MAP`; the client does not interchange workspace GUIDs, app IDs, or ARM IDs.
- Retrieve table column metadata using the fixed `getschema` query for those tables.
- Aggregate request and failed-request counts into supported fixed grains (`1m`, `5m`, `15m`, `1h`).
- Discover metric definitions before selection; validate metric names, supported aggregations, dimensions, and available time grains before querying bounded metric series.
- Compare equal-duration metric windows. `Average` comparisons require per-bucket counts and use count-weighted means; `Total`/`Count` are summed, and `Minimum`/`Maximum` preserve their semantics. A zero baseline yields no percentage rather than a misleading value.
- Retrieve fired alert instances, metric alert rules, scheduled-query rules, activity-log alert rules, action-group metadata, Activity Log events, and per-resource diagnostic settings through implemented read-only ARM endpoints.

## KQL and Evidence Safety

- Do not accept arbitrary KQL. Select a supported template and safe parameters; the user cannot add `workspace()`, `app()`, `externaldata`, `union`, cross-resource references, or remote-query constructs.
- Never silently rewrite a user's custom KQL. Explain that arbitrary KQL is unsupported and offer a supported category or fixed aggregation instead.
- Logs API POST is a query operation; it is not a general write facility. No mutation endpoint or arbitrary HTTP/CLI operation is exposed.
- Query windows use explicit timezone-aware UTC start/end values and respect configured limits. Row/series counts, retry, timeout, and pagination limits are finite.
- Telemetry/definition content is untrusted. Sensitive keys, webhook/receiver configuration, email addresses, IP addresses, and common inline secret forms are redacted before output. Do not persist raw API payloads.
- Each result includes evidence ID, retrieval time, source, scope, UTC window, query or reproducible parameters, counts, units/aggregations/dimensions where applicable, request ID, and partial/truncated warnings.

## Evidence Semantics

- A zero-row Logs response is not proof of health. Report no matching rows separately from a missing table/schema response; missing instrumentation, disabled collection, access denial, retention, and unsupported schema are not interchangeable.
- Alert instances, rule definitions, Activity Log, application telemetry, metric series, and diagnostic settings are distinct evidence sources. A configured threshold or alert does not prove a breach or root cause.
- Do not claim causation from timing alone. State sample counts, comparison windows, gaps, aggregation, and missing coverage.

## Explicit Limitations

- Azure public cloud only; no sovereign cloud or arbitrary endpoint URLs.
- Application Insights query support is workspace-based only. Classic app-only endpoints and custom/legacy table schemas are not implemented.
- Arbitrary KQL, cross-workspace/application queries, workbook execution or retrieval, arbitrary metric percentile aggregation, unimplemented resource-provider definitions, and all-resource universal coverage are unsupported.
- Subscription-wide fired-alert/rule/Activity Log inventory is disabled if resource-group or resource-ID allowlists narrow the configured scope; the current inventory endpoints cannot safely enforce those narrower scopes before the request.
- Action groups are read as definitions only; no notifications or embedded actions are executed. Diagnostic settings and alert rules are never changed.

## API Reference Set

The client uses documented Microsoft REST interfaces: [Azure Resource Graph query](https://learn.microsoft.com/en-us/rest/api/azureresourcegraph/resourcegraph/resources/resources), [Azure Monitor Logs query API](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/api/request-format), [Azure Monitor metric definitions and values](https://learn.microsoft.com/en-us/rest/api/monitor/metrics/list), and the [Azure Monitor REST API index](https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/azure-monitor-rest-api-index). API versions are pinned to the values in the client and are not user-configurable.
