#!/usr/bin/env python3
"""Check which pods are experiencing JWT validation errors."""

import sys
import json
from pathlib import Path

# Bootstrap
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / ".github" / "skills" / "newrelic-authentication"))
sys.path.insert(0, str(PROJECT_ROOT / ".github" / "skills" / "newrelic-log-operations"))

from newrelic_env import load_newrelic_auth_config_from_env
from newrelic_client import NewRelicClient, NewRelicConfig


def main():
    auth_cfg = load_newrelic_auth_config_from_env()
    nr_config = NewRelicConfig(api_key=auth_cfg.api_key, account_ids=auth_cfg.account_ids)
    client = NewRelicClient(nr_config)

    # Query 1: All ERROR logs by pod
    print("\n=== STEP 1: All ERROR logs by pod (past 4 hours) ===\n")
    nrql_all_errors = "SELECT count(*) FROM Log WHERE level = 'ERROR' SINCE 4 hours ago FACET pod_name LIMIT 100"
    
    try:
        all_errors = client.run_nrql(account_id=1679802, nrql=nrql_all_errors)
        if all_errors:
            print(f"Found {len(all_errors)} pods with ERROR-level logs:\n")
            total_errors = 0
            for row in all_errors:
                pod = row.get("facet", "N/A") if isinstance(row.get("facet"), str) else (row.get("facet", ["N/A"])[0] if row.get("facet") else "N/A")
                count = row.get("count", 0)
                print(f"  • Pod: {pod:50} | ERROR logs: {count}")
                total_errors += count
            print(f"\nTotal ERROR entries: {total_errors}\n")
        else:
            print("No ERROR logs found.\n")
    except Exception as e:
        print(f"Query error: {str(e)[:500]}\n")

    # Query 2: JWT/Bearer/Algorithm errors specifically
    print("\n=== STEP 2: JWT-related errors by pod ===\n")
    nrql_jwt_errors = "SELECT count(*) FROM Log WHERE level IN ('ERROR', 'INFO') AND (message LIKE '%InvalidBearerTokenException%' OR message LIKE '%JWT%' OR message LIKE '%algorithm%' OR message LIKE '%Bearer%') SINCE 4 hours ago FACET pod_name LIMIT 100"
    
    try:
        jwt_errors = client.run_nrql(account_id=1679802, nrql=nrql_jwt_errors)
        if jwt_errors:
            print(f"Found {len(jwt_errors)} pods with JWT-related errors:\n")
            for row in jwt_errors:
                pod = row.get("facet", "N/A") if isinstance(row.get("facet"), str) else (row.get("facet", ["N/A"])[0] if row.get("facet") else "N/A")
                count = row.get("count", 0)
                print(f"  • Pod: {pod:50} | JWT errors: {count}")
            print()
        else:
            print("No JWT-related errors found.\n")
    except Exception as e:
        print(f"Query error: {str(e)[:500]}\n")

    # Query 3: Info-level logs from the specific logger
    print("\n=== STEP 3: AbstractRestHandlerExceptionResolver logs (past 4 hours) ===\n")
    nrql_resolver = "SELECT count(*) FROM Log WHERE loggerName LIKE '%AbstractRestHandlerExceptionResolver%' SINCE 4 hours ago FACET pod_name LIMIT 100"
    
    try:
        resolver_logs = client.run_nrql(account_id=1679802, nrql=nrql_resolver)
        if resolver_logs:
            print(f"Found {len(resolver_logs)} pods with RestHandlerExceptionResolver logs:\n")
            for row in resolver_logs:
                pod = row.get("facet", "N/A") if isinstance(row.get("facet"), str) else (row.get("facet", ["N/A"])[0] if row.get("facet") else "N/A")
                count = row.get("count", 0)
                print(f"  • Pod: {pod:50} | Resolver logs: {count}")
            print()
        else:
            print("No RestHandlerExceptionResolver logs found.\n")
    except Exception as e:
        print(f"Query error: {str(e)[:500]}\n")


if __name__ == "__main__":
    main()
