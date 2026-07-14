#!/usr/bin/env python3
"""
Diagnostic script to check available tables and Issue Management configuration
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
    
    # Try to access issue table with a test query
    print("\nDiagnostics: Testing Issue Table Access")
    print("=" * 80)
    
    test_paths = [
        "/api/now/table/issue",
        "/api/now/table/u_issue",
        "/api/now/table/pm_issue",
        "/api/now/table/problem",
    ]
    
    for path in test_paths:
        try:
            print(f"\nTesting path: {path}")
            result = client._request(
                "GET",
                path,
                params={
                    "sysparm_limit": 1,
                    "sysparm_exclude_reference_link": "true",
                }
            )
            print(f"  [OK] Table accessible - returned {len(result.get('result', []))} records")
        except Exception as e:
            error_msg = str(e)
            if "Invalid table" in error_msg:
                print(f"  [TABLE NOT FOUND] {error_msg}")
            else:
                print(f"  [ERROR] {error_msg}")
    
    # Check ServiceNow system info if available
    print("\n" + "=" * 80)
    print("Checking ServiceNow instance info...")
    print("=" * 80)
    
    try:
        result = client._request(
            "GET",
            "/api/now/table/sys_properties",
            params={
                "sysparm_query": "nameLIKEissue",
                "sysparm_limit": 10,
            }
        )
        props = result.get('result', [])
        if props:
            print(f"\nFound {len(props)} properties related to 'issue':")
            for prop in props:
                print(f"  - {prop.get('name')}: {prop.get('value', '[No value]')}")
        else:
            print("No properties found related to 'issue'")
    except Exception as e:
        print(f"Could not retrieve system properties: {str(e)}")
    
    print("\n" + "=" * 80)
    print("Note: The 'issue' table may require the Issue Management module.")
    print("If not installed, consider using alternative tables or configurations.")
    print("=" * 80)

if __name__ == '__main__':
    main()
