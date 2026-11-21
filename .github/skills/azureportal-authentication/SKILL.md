---
name: 'azureportal-authentication'
description: 'Validate AzurePortal Entra authentication and configured public-cloud tenant, subscription, workspace, resource-group, and resource scope when users ask to connect to Azure or inspect authorized Azure resources; read-only only.'
keywords: ['azure', 'azureportal', 'entra', 'authentication', 'managed-identity', 'azure-cli', 'service-principal', 'scope']
---

# AzurePortal Authentication Skill

Validate the project-root `.env` configuration and construct the explicitly selected Entra credential for AzurePortal read-only resource and monitoring operations.

## Required Configuration

- `AZUREPORTAL_AUTH_MODE`: exactly `azure_cli`, `managed_identity`, or `service_principal`; there is no fallback.
- `AZUREPORTAL_TENANT_ID`: Entra tenant GUID.
- `AZUREPORTAL_SUBSCRIPTION_IDS`: comma-separated allowed subscription GUIDs; at least one is required.
- `AZUREPORTAL_WORKSPACE_MAP`: JSON object mapping each allowed workspace GUID to its verified `Microsoft.OperationalInsights/workspaces` ARM resource ID. A workspace is not authorized by GUID alone.

Conditional identity settings:

- `azure_cli`: use the already approved local Azure CLI identity in the configured tenant. No client secret variables are accepted.
- `managed_identity`: optional `AZUREPORTAL_MANAGED_IDENTITY_CLIENT_ID` for a user-assigned identity; otherwise use the system-assigned identity. No CLI fallback.
- `service_principal`: require `AZUREPORTAL_CLIENT_ID` and `AZUREPORTAL_CLIENT_SECRET`, as well as the configured tenant. The secret is read only at runtime and is excluded from configuration representations.

Optional scope and bounds:

- `AZUREPORTAL_RESOURCE_GROUPS`, `AZUREPORTAL_RESOURCE_IDS`: optional comma-separated allowlists. When configured, all operations enforce them; subscription-wide monitoring inventory is refused because it cannot be narrowed to those lists by the implemented endpoint.
- `AZUREPORTAL_MAX_WINDOW_DAYS` (30, maximum 365), `AZUREPORTAL_MAX_ROWS` (500, maximum 5,000), `AZUREPORTAL_MAX_PAGES` (5, maximum 20), `AZUREPORTAL_TIMEOUT_SECONDS` (30, maximum 120), and `AZUREPORTAL_MAX_CONCURRENT_REQUESTS` (3, maximum 10).

## Behavior and Security

- Implementation: [azureportal_env.py](azureportal_env.py) and [azureportal_transport.py](azureportal_transport.py).
- Uses `AzureCliCredential`, `ManagedIdentityCredential`, or `ClientSecretCredential` from `azure-identity` based only on the explicit mode.
- Requests separate `.default` token audiences for Azure Resource Manager and Azure Monitor Logs.
- Public Azure cloud endpoints only. No configurable endpoint hosts, portal scraping, arbitrary request method, or redirect-following.
- Resource, subscription, and workspace scopes are validated before the API call. Continuation URLs must retain the trusted ARM host, exact operation path, allowed API version, and configured subscription.
- Azure API errors are classified without returning raw response bodies or credential exception text. Transient retries are finite and honor bounded `Retry-After`.
- Never print or persist tokens or client secrets. Do not request secrets in chat.

## Permission Guidance

Grant only the selected identity's required read permissions:

- Resource Graph discovery: Reader on the allowed subscriptions (or equivalent read access to the queried resource types).
- Metric definitions and values, fired alerts, monitoring rules, Activity Log, diagnostic settings, and action-group metadata: appropriate Azure Monitor/Reader permissions at the smallest supported scope. `Monitoring Reader` is relevant to monitor data and definitions but does not automatically grant Log Analytics data access.
- Workspace telemetry queries: `Log Analytics Reader` (or a narrower workspace data-plane role) on each explicitly mapped workspace. A control-plane Reader role alone does not grant query access.
- Application Insights mapping needs read access to the component/workspace resource metadata through Resource Graph plus Logs API access to the mapped workspace.

Confirm tenant access, role assignment propagation, and workspace/resource mappings with the Azure administrator. The skill does not check credentials against live Azure during configuration validation.
