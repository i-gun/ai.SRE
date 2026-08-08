# Promoted Artifacts (2026-08-07)

This note captures temporary artifacts promoted into reusable scripts.

## Promoted to core scripts

1. Jira CVE utilities
- Legacy artifacts:
  - `artifacts/jira_cve_search.py`
  - `artifacts/jira_cve_probe_transitions.py`
  - `artifacts/jira_cve_bulk_close.py`
- Promoted script:
  - `scripts/jira/cve_task_manager.py`
- Improvements:
  - Consolidates three one-shot scripts into one CLI with subcommands: `search`, `probe`, `bulk-close`.
  - Defaults to dry-run for bulk close; writes require `--execute`.
  - Supports issue-key file input and structured JSON output for automation.

2. New Relic dashboard inspection
- Legacy artifacts:
  - `artifacts/nr_dashboard_fetch.py`
  - `artifacts/nr_analyze_tab.py`
- Promoted script:
  - `scripts/newrelic/dashboard_catalog.py`
- Improvements:
  - Consolidates backup and inspection flows into one CLI: `list-tabs`, `fetch-tab`, `backup`, `show`.
  - Supports controlled artifact output path and structured JSON output.
  - Uses repository New Relic bootstrap pattern (`scripts/newrelic/common.py`).

## Usage quickstart

```powershell
# Jira CVE search
.\.venv\Scripts\python.exe scripts\jira\cve_task_manager.py search --cve CVE-2026-40895 --project DDL

# Jira transition probe
.\.venv\Scripts\python.exe scripts\jira\cve_task_manager.py probe --issue-key DDL-40208

# Jira bulk-close dry-run (safe default)
.\.venv\Scripts\python.exe scripts\jira\cve_task_manager.py bulk-close --issue-file artifacts\ddl_keys.txt --duplicate-of DDL-40243

# Jira bulk-close execute
.\.venv\Scripts\python.exe scripts\jira\cve_task_manager.py bulk-close --issue-file artifacts\ddl_keys.txt --duplicate-of DDL-40243 --execute

# New Relic list tabs
.\.venv\Scripts\python.exe scripts\newrelic\dashboard_catalog.py list-tabs

# New Relic backup
.\.venv\Scripts\python.exe scripts\newrelic\dashboard_catalog.py backup --output-file artifacts\nr_dashboard_backup_checkout_order_2026-08-07.json

# New Relic inspect tab from backup
.\.venv\Scripts\python.exe scripts\newrelic\dashboard_catalog.py show --backup-file artifacts\nr_dashboard_backup_checkout_order_2026-08-07.json --tab APIM
```

## Recommendation

Keep legacy artifact scripts for short overlap only, then archive/remove once operators switch to `scripts/` entry points.
