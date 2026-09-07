---
title: Agent Capabilities Reference
description: Current ai.SRE agent catalog, skill dependencies, operating scopes, and key controls
---

# Agent Capabilities Reference

This is the maintained catalog for selecting the appropriate `@AgentName` integration. Agent and skill definitions under `.github/` are the implementation authority; this reference explains their intended operating boundaries.

## Shared Operating Model

- Integrations load credentials from the repository-root `.env`; do not place credentials in prompts, scripts, or tracked files.
- Delegate work to the specialized agent before considering a custom script. Reusable additions belong in `scripts/<service>/`; temporary diagnostics belong in `artifacts/` and are removed after use.
- Treat agent findings as evidence requiring appropriate human review, especially for security, production mutation, and root-cause conclusions.
- `data/` is generated locally and ignored by Git. Regenerate required inputs after cloning rather than assuming they are available.

## Agent Catalog

| Agent | Primary capabilities | Skills | Key boundaries |
|---|---|---|---|
| `@Advisor` | Copilot/VS Code architecture, adoption, governance, risk, and implementation decision support | None | Provides strategic guidance; implementation generation requires an explicit `generate` request. |
| `@Gitter` | Local Git synchronization, branch and commit strategy, and GitHub pull-request workflow | `gitter-credentials` | Uses `gh` plus the narrowly scoped `GITHUB_PR_TOKEN` for PR operations; protected branches land through PRs. |
| `@ServiceNow` | Incident and problem lifecycle retrieval, creation, updates, assignment, and controlled resolution | `servicenow-authentication`, `servicenow-incident-operations` | Enforces configured assignment scope; mutating actions require validation and explicit execution intent. |
| `@Jira` | Project and dashboard lookup; issue search, creation, updates, comments, links, and lifecycle interpretation | `jira-authentication`, `jira-issue-operations` | Uses Jira credentials from `.env`; validate project and issue fields before write operations. |
| `@Confluence` | Space browsing, CQL search, page retrieval, service linkage, and service-flow graph construction | `confluence-authentication`, `confluence-knowledge-operations` | Restricts retrieval to configured Confluence space keys. |
| `@AzureGit` | Azure DevOps project and repository discovery, file access, code search, and lightweight code-path analysis | `azuregit-authentication`, `azuregit-repository-operations` | Read-only and limited to the configured project allowlist. |
| `@NewRelic` | Multi-account log search, alert operations, trends, dependency analysis, and service degradation investigation | `newrelic-authentication`, `newrelic-alert-operations`, `newrelic-log-operations` | Account scope comes from `.env`; alert acknowledgment is controlled and scoped to configured policy criteria. |
| `@Dynatrace` | Grail/DQL log search and trends, Smartscape dependencies, Problems v2 investigation, and Davis AI evidence-led RCA | `dynatrace-authentication`, `dynatrace-monitoring-operations`, `dynatrace-problem-operations` | Single configured environment only. Acknowledgment is an audit-trail comment, never a status mutation; explicit user intent is required to post it. |
| `@RCA` | Evidence-driven incident investigation that correlates telemetry, tickets, knowledge, and source attribution into an RCA report | New Relic, ServiceNow, Jira, Confluence, AzureGit, and RCA analysis skills | Requires explicit `APPROVE_RUN_RCA` before execution; distinguishes corroborated evidence from hypotheses. |
| `@Emailer` | Outlook desktop folder reading and redaction-aware, recipient-governed draft composition | `emailer-connection`, `emailer-mail-operations` | Uses local Outlook COM without OAuth credentials; recipient domain allowlisting is fail-closed and drafts require human review. |

## Dynatrace Integration

`@Dynatrace` is appropriate when the source of truth is the configured Dynatrace environment. It operates through three skills:

| Skill | Responsibility | Required configuration |
|---|---|---|
| `dynatrace-authentication` | Validates and normalizes Dynatrace configuration before any API operation | `DYNATRACE_ENVIRONMENT_URL`, `DYNATRACE_API_TOKEN`, `DYNATRACE_USERNAME` |
| `dynatrace-monitoring-operations` | Executes bounded Grail/DQL log search and trends, Smartscape relationship lookup, and Davis-evidence-first root-cause analysis | URL and token with log, event, entity, and problem read permissions |
| `dynatrace-problem-operations` | Searches Problems v2, retrieves Davis problem evidence, and writes acknowledgment comments | URL, token with `problems.read` and comment-only `problems.write`, and username |

### Operational Semantics

- Grail queries use Dynatrace's asynchronous execute-and-poll API cycle internally. Agent responses provide findings rather than request tokens or polling mechanics.
- Dependency relationships come from Smartscape's service entity model: callers are upstream and declared dependencies are downstream.
- Root-cause responses prioritize Davis AI `rootCauseEntity`, `impactAnalysis`, and `evidenceDetails`; log-pattern analysis is a clearly labeled fallback when native evidence is absent or inconclusive.
- Dynatrace problems transition between `OPEN` and `CLOSED`; this integration does not resolve, close, or mute them. Posting a comment records pickup in the audit trail and must state that the status is unchanged.

## Selection Guide

| Need | Delegate to |
|---|---|
| Repository synchronization, branch management, or GitHub PR lifecycle | `@Gitter` |
| Azure DevOps source discovery or code attribution | `@AzureGit` |
| New Relic logs, alerts, or cross-account dependency analysis | `@NewRelic` |
| Dynatrace logs, Smartscape topology, Davis problem evidence, or a problem audit comment | `@Dynatrace` |
| ServiceNow incident/problem actions | `@ServiceNow` |
| Jira issue lifecycle actions | `@Jira` |
| Confluence service knowledge retrieval | `@Confluence` |
| Cross-system incident root-cause package | `@RCA` |
| Outlook mailbox reading or reviewed email draft composition | `@Emailer` |
| Copilot adoption, extension architecture, or governance decisions | `@Advisor` |

## Documentation Maintenance

When an agent or skill is added or materially changed, update its definition first, then the README catalog and this reference. Add capability-specific operational details to the relevant skill documentation and credential/security controls to [INTEGRATION_GOVERNANCE.md](INTEGRATION_GOVERNANCE.md). Do not manually modify the hook-maintained README file-change log.