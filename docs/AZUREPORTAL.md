# AzurePortal Read-Only Azure Monitoring

`@AzurePortal` performs bounded, evidence-backed reads from Azure public cloud. It uses Microsoft Entra ID and documented Azure Resource Manager, Resource Graph, Azure Monitor Logs, and metrics APIs. It does not scrape the portal, use browser cookies, execute arbitrary Azure CLI commands, or expose a general HTTP/KQL tool.

## Setup

1. Copy `.env.template` to `.env`; do not commit `.env` or paste secrets into chat.
2. Set `AZUREPORTAL_AUTH_MODE` explicitly to `azure_cli`, `managed_identity`, or `service_principal`. The integration never falls back between identities.
3. Configure `AZUREPORTAL_TENANT_ID` and an explicit comma-separated `AZUREPORTAL_SUBSCRIPTION_IDS` allowlist.
4. Configure `AZUREPORTAL_WORKSPACE_MAP` as JSON mapping each workspace GUID to its verified `Microsoft.OperationalInsights/workspaces` ARM resource ID. Include only workspaces whose subscription and (if set) resource group are allowed.
5. Optionally add exact resource groups and resource IDs. Note: subscription-wide alert/rule/Activity Log inventory is disabled when either narrower list is set because the implemented subscription-level inventory endpoints cannot enforce those narrower scopes before the request.
6. Install the project requirements. The client uses `azure-identity` with the repository's existing `requests` transport.

The only supported cloud is Azure public cloud. Sovereign clouds and custom endpoint URLs are intentionally unsupported.

## Configuration Reference

| Variable | Required | Meaning |
|---|---:|---|
| `AZUREPORTAL_AUTH_MODE` | Yes | Explicit `azure_cli`, `managed_identity`, or `service_principal`; no default fallback. |
| `AZUREPORTAL_TENANT_ID` | Yes | Entra tenant GUID. |
| `AZUREPORTAL_SUBSCRIPTION_IDS` | Yes | Comma-separated subscription GUID allowlist. |
| `AZUREPORTAL_WORKSPACE_MAP` | For Logs queries | JSON mapping of workspace GUID to verified workspace ARM resource ID. |
| `AZUREPORTAL_RESOURCE_GROUPS` | No | Optional comma-separated resource-group allowlist. |
| `AZUREPORTAL_RESOURCE_IDS` | No | Optional comma-separated exact ARM resource-ID allowlist. |
| `AZUREPORTAL_MANAGED_IDENTITY_CLIENT_ID` | Conditional | Optional client ID for a user-assigned managed identity. |
| `AZUREPORTAL_CLIENT_ID`, `AZUREPORTAL_CLIENT_SECRET` | Conditional | Required only for service-principal mode. Secret is read at runtime and never emitted. |
| `AZUREPORTAL_MAX_WINDOW_DAYS` | No | Maximum query window; default 30, allowed range 1–365. |
| `AZUREPORTAL_MAX_ROWS` | No | Result/series bound; default 500, allowed range 1–5,000. |
| `AZUREPORTAL_MAX_PAGES` | No | Pagination bound; default 5, allowed range 1–20. |
| `AZUREPORTAL_TIMEOUT_SECONDS` | No | Per-request timeout; default 30, allowed range 1–120. |
| `AZUREPORTAL_MAX_CONCURRENT_REQUESTS` | No | Bounded in-flight requests; default 3, allowed range 1–10. |

Fields for unused identity modes must be blank. For service-principal mode, obtain the secret through the approved secret-management path; never include it in prompts, logs, test fixtures, or committed files.

## Authentication and Least Privilege

The selected identity receives distinct tokens for:

- Azure Resource Manager and Resource Graph: `https://management.azure.com/.default`.
- Logs API: `https://api.loganalytics.azure.com/.default`.

The configured API host must match its token audience. Redirects and arbitrary API hosts are rejected.

Assign permissions at the smallest supported scope:

- **Resource Graph discovery and metadata:** Reader on only the allowed subscriptions (or equivalent read access to resources queried).
- **Metric definitions/series, fired alerts, rule definitions, Activity Log, diagnostic settings, action-group metadata:** the relevant Azure Monitor read roles; `Monitoring Reader` is often appropriate but does not grant Log Analytics data-plane access by itself.
- **Workspace telemetry and schema queries:** `Log Analytics Reader` or an appropriately narrower workspace data-plane role on each mapped workspace. A control-plane Reader role alone is insufficient for Logs API queries.
- **Application Insights workspace mapping:** read access to the component and workspace metadata plus Logs API read access to the mapped workspace.

The actual permission needed depends on resource-provider and table access controls. A `403` is reported as an access failure, not an empty result.

## Supported Operations

| Area | Implemented read-only behavior |
|---|---|
| Resources | Resource Graph enumeration, exact ARM ID metadata, friendly-name resolution with ambiguity reporting, allowlisted group/resource filters, and workspace-based Application Insights component-to-workspace mapping. |
| Logs/Application Insights | Fixed, bounded templates for `AppRequests`, `AppExceptions`, `AppDependencies`, `AppTraces`, `AppAvailabilityResults`, table schema, and request failure trends. No arbitrary KQL. |
| Metrics | Discover metric names/units/aggregations/dimensions/time grains, query bounded series, and compare equal-duration windows with aggregation-safe calculations. Queries set the API's series `top` bound, reject windows exceeding the configured point bound, and require exact filters for every declared metric dimension. |
| Alerts and monitoring definitions | Fired alert instances, metric alert rules, scheduled-query rules, activity-log alert rules, action-group metadata, Activity Log events, and per-resource diagnostic settings. Definitions are not live firing evidence. |

Workbooks are not retrieved or executed. Classic Application Insights app-only queries, arbitrary/custom schemas, cross-workspace/application/resource KQL, management-group discovery, universal provider metadata/API-version catalogs, and unimplemented resource-provider definitions are unsupported. The integration does not claim coverage of every Azure resource or monitoring category.

## Query, Redaction, and Evidence Contract

- Every log query is created from a finite typed template. User-supplied KQL is not accepted. This avoids pretending that a regex can safely isolate the full Kusto language.
- Queries require explicit timezone-aware start/end values and enforce the maximum window. API/row/page/time/concurrency bounds are finite.
- Metric point counts are estimated from the selected time grain before the request; dimensioned metrics require equality filters for every declared dimension to prevent unbounded series fan-out.
- Resource IDs, workspace GUIDs, and subscriptions are validated before requests. Pagination and continuation links are revalidated for endpoint, API version, operation, and subscription. Redirects are rejected before forwarding credentials.
- Retries are bounded, transient status handling honors capped `Retry-After`, and errors are classified without raw payloads or credential exceptions.
- Telemetry and definitions are untrusted input. Sensitive keys, receiver/webhook details, emails, IPs, and common inline secret forms are redacted; large/unselected properties are not projected.
- Results include evidence IDs, retrieval time, source and scope, exact UTC windows, redacted query or reproducible parameters, counts, units/aggregations/dimensions, request IDs where available, and partial/truncation warnings.
- Zero matching rows are not proof of health. Missing instrumentation, retention, permission denial, partial data, and unsupported schemas must be stated separately. Temporal correlation is not proof of causation.

The agent's concise response format is Summary, Evidence, Assessment, and Limitations / next verification. Evidence is not persisted by default.

## Opt-In Read-Only Smoke Test

This procedure is intentionally separate from unit tests. Do not run it during implementation or without the operator's authorization.

Prerequisites:

- A maintainer explicitly authorizes a live read-only check.
- `.env` contains the explicit identity mode, correct tenant, one approved subscription, and verified workspace mapping.
- The identity can acquire the expected Entra token and has Reader plus workspace `Log Analytics Reader` (or equivalent) permissions.
- Azure CLI mode: the operator has already authenticated with the expected tenant. Managed identity or service principal mode is configured for its intended runtime.

Run through the agent, not `az rest` or a custom request:

1. `@AzurePortal, list up to 5 resources in the configured subscription.`
2. After selecting a mapped workspace, `@AzurePortal, summarize AppRequests for the last 30 minutes, grouped into 5-minute request and failure counts.`

Expected output: each operation reports a distinct evidence ID and retrieval time, exact authorized scope, UTC window for telemetry, source/operation, bounded counts, and completeness metadata. A zero-match result is explicitly labeled; it must not be described as healthy. A permissions/configuration error is reported as failure. No mutation should occur.

## Official API References

- [Azure Resource Graph REST query](https://learn.microsoft.com/en-us/rest/api/azureresourcegraph/resourcegraph/resources/resources) (`2022-10-01`)
- [Azure Monitor Logs query API request format](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/api/request-format) (`v1`)
- [Azure Monitor metrics REST API](https://learn.microsoft.com/en-us/rest/api/monitor/metrics/list) (definitions/values `2018-01-01`)
- [Azure Monitor REST API index](https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/azure-monitor-rest-api-index)
- [Azure Identity client library for Python](https://learn.microsoft.com/en-us/python/api/overview/azure/identity-readme)
