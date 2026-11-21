---
name: 'azureportal-resource-operations'
description: 'Read-only Azure Resource Graph discovery, ambiguity-safe resource resolution, non-secret resource metadata, and workspace-based Application Insights workspace mapping when users ask to find or inspect Azure resources.'
keywords: ['azure', 'azureportal', 'resource-graph', 'resource-discovery', 'metadata', 'application-insights', 'workspace']
---

# AzurePortal Resource Operations Skill

Use the testable [azureportal_resource_client.py](azureportal_resource_client.py) client after `azureportal-authentication` succeeds. It supports:

- Bounded resource enumeration through Azure Resource Graph only in configured subscriptions, optionally narrowed to configured/requested resource groups and exact resource IDs.
- Exact resource-ID metadata lookup and friendly-name resolution. If a name returns multiple matches, report all bounded matches and ask the user to select one; never choose the first.
- Resource IDs, type, location, resource group, subscription ID, and tags with sensitive tag values redacted.
- Workspace-based Application Insights mapping by reading the component's `properties.WorkspaceResourceId` from Resource Graph and matching that ARM ID against the explicitly verified workspace map. The Application Insights ARM ID, app ID, and workspace GUID are distinct identifiers.

## Read-Only and Query Limits

- Resource Graph uses the documented `POST /providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01` query endpoint. The POST is read-only by semantics.
- The client constructs the allowed Kusto queries; it does not accept a user-supplied Resource Graph query string as an operation.
- Pagination is finite, uses only the returned skip token, and remains on the same Resource Graph endpoint. Each page reuses only the configured subscription IDs.
- Resource properties are not broadly projected. Provider-specific configuration and provider/API-version catalogs are not currently exposed.

## Unsupported

- Arbitrary provider resource GETs, deployments, updates, deletes, remediation, role assignments, broad property dumps, management-group/tenant-wide discovery, and providers not returned by the supported Resource Graph projection.
- Classic Application Insights resources without a workspace mapping. If a component has no mapped workspace, stop and report that it is unsupported rather than treating its app ID as a workspace ID.

Every result includes an evidence ID, retrieval time, source, operation, scoped subscriptions, reproducible query with literals redacted, result count, request ID where available, and truncation/partial-result metadata.
