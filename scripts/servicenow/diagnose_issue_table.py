#!/usr/bin/env python3
"""
Diagnostic script to verify problem_task (PTASK) table access and confirm
that /api/now/table/issue does not exist on this instance.

Use this to validate connectivity before running create_issue_from_problem.py.
"""

import sys

from common import bootstrap

bootstrap()

from servicenow_client import ServiceNowClient

def main():
    # Initialize client
    try:
        client = ServiceNowClient.from_env()
        print("[OK] ServiceNow Client initialized")
    except Exception as e:
        print(f"[FAILED] Failed to initialize: {str(e)}")
        sys.exit(1)

    print("\nDiagnostics: Problem Task Table Access")
    print("=" * 80)

    test_cases = [
        ("/api/now/table/problem_task", "PTASK backing table for 'Create Issue' button"),
        ("/api/now/table/problem",      "Problem table"),
        ("/api/now/table/incident",     "Incident table"),
        ("/api/now/table/issue",        "(expected NOT FOUND on this instance)"),
    ]

    for path, label in test_cases:
        try:
            result = client._request(
                "GET",
                path,
                params={"sysparm_limit": 1, "sysparm_exclude_reference_link": "true"},
            )
            count = len(result.get("result", []))
            print(f"  [OK ]  {path:<45s}  {label}  ({count} record(s))")
        except Exception as e:
            err = str(e)
            tag = "[TABLE NOT FOUND]" if "Invalid table" in err else "[ERROR]"
            print(f"  {tag}  {path:<45s}  {err[:80]}")


if __name__ == "__main__":
    main()


if __name__ == '__main__':
    main()
