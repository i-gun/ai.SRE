# Project Overview

This project contains GitHub Copilot AI tools agents and skills for advanced development workflows.

## Quick Start

### Credential Configuration
All integrations read credentials from `.env` in the project root:

```bash
# Copy template to .env (not committed to repository)
cp .env.template .env

# Edit with your credentials
SERVICENOW_HOST=https://your-instance.service-now.com
SERVICENOW_USERNAME=your_user
SERVICENOW_PASSWORD=your_secure_password
SERVICENOW_ASSIGNMENT_GROUPS=Group1,Group2
```

**Security:** `.env` is in `.gitignore` — NEVER commit credentials.

### Use Agents for Operations
Always use agent delegation (`@AgentName`) rather than creating custom scripts:

```bash
@ServiceNow, [operation description]
@Jira, [operation description]
@Confluence, [operation description]
@AzureGit, [operation description]
@NewRelic, [operation description]
@RCA, [incident identifier or description]
```

Agents automatically handle credential loading, validation, and error handling.

### Data Bootstrap (Required After Clone)
The `data/` folder is intentionally gitignored for security and does not synchronize across environments.

Before running repository-mapping workflows, generate local data with available agents:

1. Preferred path: `@NewRelic, export current APM service names for account 1679802 and save locally to data/newrelic_apm_service_names_1679802.txt, data/newrelic_apm_service_names_1679802.csv, and data/newrelic_apm_services_1679802.json`
2. Non-chat automation fallback:

```bash
python scripts/newrelic/generate_service_catalog.py --account-id 1679802 --since "30 days ago" --pretty-json
```

This generates the same three files under `data/`.

3. Run: `@Confluence, analyze services in data/newrelic_apm_service_names_1679802.txt`
4. Run: `@AzureGit, map services in data/newrelic_apm_service_names_1679802.txt to repositories`

### Development & Governance
- **Integration Governance** — See [INTEGRATION_GOVERNANCE.md](docs/INTEGRATION_GOVERNANCE.md) for credential handling, script placement, and best practices
- **Hook Setup** — See [GIT_HOOKS_IMPLEMENTATION.md](docs/GIT_HOOKS_IMPLEMENTATION.md) for automated documentation and formatting
- **Repository Mapping (Primary)** — [COMBINED_SERVICE_REPOSITORY_MAPPING_REPORT.md](docs/COMBINED_SERVICE_REPOSITORY_MAPPING_REPORT.md) is the canonical combined view (AzureGit + Confluence + Jira label signal run).
- **Repository Mapping (Supporting)**
  - [AZUREGIT_REPOSITORY_MAPPING_REPORT.md](docs/AZUREGIT_REPOSITORY_MAPPING_REPORT.md) — Project/repository inventory snapshot (278 repos across 15 projects)
  - [SERVICE_REPOSITORY_MAPPING_REPORT.md](docs/SERVICE_REPOSITORY_MAPPING_REPORT.md) — AzureGit-focused service-to-repository baseline analysis
- **Knowledge Mapping** — Run `@Confluence` agent to regenerate service documentation analysis. Current summary: 3.9% coverage, 124 services with documentation gaps. Cross-check with [COMBINED_SERVICE_REPOSITORY_MAPPING_REPORT.md](docs/COMBINED_SERVICE_REPOSITORY_MAPPING_REPORT.md).
- **ServiceNow Resolve Prompt Pack** — See [README-SN-RESOLVE.md](.github/prompts/README-SN-RESOLVE.md) for reusable Gigya, RTCDP, and SFSC incident resolution prompts

## Project Structure

```
├── .github/
│   ├── agents/              # AI agent definitions
│   │   ├── advisor.agent.md
│   │   ├── azuregit.agent.md
│   │   ├── confluence.agent.md
│   │   ├── gitter.agent.md
│   │   ├── jira.agent.md
│   │   ├── newrelic.agent.md
│   │   ├── rca.agent.md
│   │   └── servicenow.agent.md
│   ├── prompts/             # Reusable prompt templates
│   │   ├── rca-intake.prompt.md
│   │   ├── rca-deep-investigation.prompt.md
│   │   ├── rca-hypothesis-stress-test.prompt.md
│   │   ├── rca-similar-incident-comparison.prompt.md
│   │   ├── rca-azuregit-code-attribution.prompt.md
│   │   ├── rca-final-report-assembly.prompt.md
│   │   ├── rca-executive-summary.prompt.md
│   │   ├── README-SN-RESOLVE.md
│   │   └── README-SN-PRB-Jira.md
│   └── skills/              # Domain-specific skill implementations
│       └── gitter-credentials/
│           ├── SKILL.md
│           ├── SETUP.md
│           ├── README.md
│           ├── ARCHITECTURE.md
│           ├── gitter_credentials.py
│           └── gitter_credentials.js
│       └── servicenow-authentication/
│           ├── SKILL.md
│           └── servicenow_env.py
│       └── servicenow-incident-operations/
│           ├── SKILL.md
│           ├── README.md
│           └── servicenow_client.py
│       └── jira-authentication/
│           ├── SKILL.md
│           └── jira_env.py
│       └── jira-issue-operations/
│           ├── SKILL.md
│           ├── README.md
│           └── jira_client.py
│       └── confluence-authentication/
│           ├── SKILL.md
│           └── confluence_env.py
│       └── confluence-knowledge-operations/
│           ├── SKILL.md
│           ├── README.md
│           └── confluence_client.py
│       └── azuregit-authentication/
│           ├── SKILL.md
│           └── azuregit_env.py
│       └── azuregit-repository-operations/
│           ├── SKILL.md
│           ├── README.md
│           └── azuregit_client.py
│       └── newrelic-authentication/
│           └── SKILL.md
│       └── newrelic-alert-operations/
│           └── SKILL.md
│       └── newrelic-log-operations/
│           ├── SKILL.md
│           └── README.md
│       └── rca-log-forensics/
│           └── SKILL.md
│       └── rca-incident-similarity/
│           └── SKILL.md
│       └── rca-servicenow-mining/
│           └── SKILL.md
│       └── rca-jira-lifecycle/
│           └── SKILL.md
│       └── rca-confluence-context/
│           └── SKILL.md
│       └── rca-azuregit-attribution/
│           └── SKILL.md
│       └── rca-cross-system-correlation/
│           └── SKILL.md
│       └── rca-visualization/
│           └── SKILL.md
│       └── rca-report-authoring/
│           └── SKILL.md
├── docs/                    # Project and implementation documentation
│   ├── GIT_HOOKS_IMPLEMENTATION.md
│   ├── GITTER_CREDENTIALS_SKILL_SUMMARY.md
│   ├── INTEGRATION_GOVERNANCE.md
│   └── NEWRELIC_SERVICENOW_ORCHESTRATOR_USAGE.md
├── scripts/                 # Core operational scripts
│   └── confluence/
│       ├── common.py
│       ├── search_space_pages.py
│       ├── search_content.py
│       └── build_service_flow_graph.py
│   └── newrelic/
│       ├── common.py
│       ├── search_logs.py
│       ├── analyze_trends.py
│       ├── trace_dependencies.py
│       ├── root_cause_analysis.py
│       └── generate_service_catalog.py
│   └── azuregit/
│       ├── common.py
│       └── fetch_repo_map.py
│   └── orchestration/
│       └── newrelic_servicenow_alert_orchestrator.py
│   └── servicenow/
│       ├── common.py
│       ├── batch_resolve_triggered_incidents.py
│       ├── create_issue_from_problem.py
├── data/                    # Local generated input data (gitignored, not synchronized)
│   ├── newrelic_apm_service_names_1679802.txt
│   ├── newrelic_apm_service_names_1679802.csv
│   └── newrelic_apm_services_1679802.json
├── artifacts/               # Gitignored: local-only temp scripts and generated outputs
│   └── servicenow/
│       └── archive/
│           ├── diagnose_issue_table.py
│           ├── execute_incident_operations.py
│           ├── resolve_incident_script.py
│           ├── search_final_resolved_incidents.py
│           ├── search_resolved_incidents.py
│           └── test_query_variations.py
├── tests/
│   ├── test_confluence_client.py
│   ├── test_newrelic_scripts.py
│   ├── test_newrelic_servicenow_alert_orchestrator.py
│   ├── test_servicenow_client.py
│   └── test_servicenow_scripts.py
├── git-hooks/               # Hook sources tracked in repo
├── .env.template            # Environment configuration template
├── .env.example             # Example configuration
├── .gitignore               # Git security excludes
└── README.md                # This file
```

## Agents

### Advisor Agent
Senior advisor specializing in GitHub Copilot AI tools architecture and enterprise adoption strategies.

### Gitter Agent
Expert Git workflow strategist for repository optimization and team collaboration.

### ServiceNow Agent
Incident lifecycle operations agent for secure ServiceNow communication using `.env` credentials, including incident creation, assignment/reassignment, priority changes, and incident-to-problem linkage.

### Jira Agent
Jira Cloud operations agent for project lookup, dashboard discovery, issue search, fetch, create, update, comment, and issue linking using `.env` credentials.

### Confluence Agent
Confluence knowledge operations agent for scoped page browsing, CQL search, content retrieval, cross-page service relationship discovery, and service-flow graph generation.

### AzureGit Agent
Azure DevOps Git read-only operations agent for scoped multi-project repository lookup, code search, and lightweight codebase analysis using `.env` credentials.

### NewRelic Agent
New Relic observability agent for log search, trend analysis, dependency traversal, automated root cause analysis, and alert acknowledgment across configured accounts using `.env` credentials. Primary account: CTC Production `1679802`.

### RCA Agent
Elite RCA Orchestrator for end-to-end, evidence-driven root cause analysis. Correlates New Relic observability, ServiceNow incidents, Jira work tracking, Confluence knowledge, and AzureGit source attribution into a defensible RCA package. Requires explicit `APPROVE_RUN_RCA` command to begin execution. Use the [rca-intake prompt](.github/prompts/rca-intake.prompt.md) to initiate an investigation.

## Skills

### Gitter Credentials Skill
Secure credential management for Git operations with support for SSH keys, tokens, and GPG signing.

### ServiceNow Authentication Skill
Credential validation and normalization for ServiceNow host, username, and password loaded from `.env`.

### ServiceNow Incident Operations Skill
ServiceNow Incident, Problem, and Issue Table API operations for scoped incident retrieval/creation, assignment/reassignment, work-note updates, matrix-based priority changes, incident-to-problem linkage, issue-from-problem creation, and validated resolution workflows.

### Jira Authentication Skill
Credential validation and normalization for Jira Cloud host, username, and API token loaded from `.env`.

### Jira Issue Operations Skill
Jira Cloud Project, Dashboard, and Issue API operations for search, fetch, create, update, comment, and issue-link workflows.

### Confluence Authentication Skill
Credential validation and normalization for Confluence access using Jira Cloud host, username, API token, and a dedicated Confluence space key from `.env`.

### Confluence Knowledge Operations Skill
Confluence Cloud content operations for space browsing, CQL search, page retrieval, schema/service signal extraction, relationship linking, and service-flow graph construction.

### AzureGit Authentication Skill
Credential validation and normalization for Azure DevOps organization, scoped project allowlist, PAT, and optional API version loaded from `.env`.

### AzureGit Repository Operations Skill
Read-only Azure DevOps Git operations for repository discovery, file listing, content search, and lightweight repository structure analysis across scoped projects.

### NewRelic Authentication Skill
Credential validation and normalization for New Relic API key and comma-separated account ID list loaded from `.env`.

### NewRelic Alert Operations Skill
Fetch open unacknowledged New Relic issues scoped to account `1679802` and policies matching Digital Operations prefix, then acknowledge them with platform-resolved username.

### NewRelic Log Operations Skill
New Relic log search, trend analysis, pod restart checking, JWT/auth anomaly detection, dependency traversal, and automated RCA scoring across configured accounts.

### RCA Log Forensics Skill
Multi-account New Relic log forensics for deep error collection, burst detection, novelty scoring, pod restart analysis, JWT/auth anomaly detection, and pre/post-incident trend comparison.

### RCA Incident Similarity Skill
Discovers and differentially compares historical ServiceNow incidents against a target incident using signal matching, symptom overlap, resolution pattern mining, and recurrence scoring.

### RCA ServiceNow Mining Skill
Extracts structured timeline, assignee history, work notes, resolution notes, and linked problem/task records from a target ServiceNow incident.

### RCA Jira Lifecycle Skill
Jira lifecycle interpretation for discovering related issues, transition history, comment analysis, component and label ownership, fix-version linking, and dependency chain mapping.

### RCA Confluence Context Skill
Retrieves architecture documentation, service ownership pages, runbooks, known-error records, and prior RCA guidance from Confluence relevant to a target incident or service.

### RCA AzureGit Attribution Skill
Scoped repository discovery, service-name-driven code search, call-path tracing, fault location hypothesis generation, and confidence-scored attribution for RCA source analysis.

### RCA Cross-System Correlation Skill
Builds a unified causal timeline, scores competing hypotheses, rejects weak candidates, and produces a root cause determination with contributing factors from all evidence streams.

### RCA Visualization Skill
Produces structured chart data, error volume trend tables, latency overlays, incident timeline Mermaid diagrams, and causal relationship graphs from correlated evidence streams.

### RCA Report Authoring Skill
Assembles the complete, structured RCA markdown document from all stream outputs, including executive summary, technical timeline, evidence matrix, code attribution pack, corrective actions, and validation plan.

### Confluence Scripts & Tests
- Helper scripts in `scripts/confluence/` support page browsing, CQL search, and service-flow graph generation.
- Unit tests in `tests/test_confluence_client.py` validate graph extraction and CQL space-scoping behavior.

### ServiceNow Script Safety
- Core mutation scripts under `scripts/servicenow/` are parameterized and default to read-only mode.
- Use explicit execution flags only after reviewing listed records and input values.

### Orchestration Script Safety
- Cross-system mutation scripts under `scripts/orchestration/` also default to read-only mode.
- Use explicit execution flags and alert-count thresholds before acknowledging alerts or creating/updating incidents.

### Test Commands
- Run the full suite with `python -m unittest discover -s tests`.
- Use targeted module runs for focused validation while editing individual integrations.

### CI Validation
- GitHub Actions runs the discovered Python unit test suite on pushes and pull requests via [.github/workflows/python-tests.yml](.github/workflows/python-tests.yml).

## File Changes Log

This section is automatically maintained by pre-commit hooks.

