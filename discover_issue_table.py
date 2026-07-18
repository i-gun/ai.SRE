"""
Discover actual issue table names in ServiceNow.
Uses HTTPBasicAuth for authentication like verify_capabilities.py which was successful.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

import requests
from requests.auth import HTTPBasicAuth

# Load .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

def test_table_access(host: str, username: str, password: str, table_path: str) -> Dict[str, Any]:
    """Test access to a specific table."""
    session = requests.Session()
    session.auth = HTTPBasicAuth(username, password)
    session.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    
    try:
        response = session.request(
            method="GET",
            url=f"{host}{table_path}?sysparm_limit=1",
            timeout=30,
        )
        
        if response.status_code == 200:
            return {
                "table": table_path,
                "status": "OK",
                "http_code": 200,
                "records": len(response.json().get("result", [])),
            }
        else:
            try:
                error_detail = response.json()
            except:
                error_detail = response.text[:200]
            return {
                "table": table_path,
                "status": "FAILED",
                "http_code": response.status_code,
                "error": str(error_detail),
            }
    except Exception as e:
        return {
            "table": table_path,
            "status": "ERROR",
            "error": str(e),
        }

def main():
    host = os.getenv("SERVICENOW_HOST", "").strip()
    username = os.getenv("SERVICENOW_USERNAME", "").strip()
    password = os.getenv("SERVICENOW_PASSWORD", "").strip()
    
    if not all([host, username, password]):
        print("ERROR: Missing credentials")
        sys.exit(1)
    
    print("=" * 70)
    print("ServiceNow Issue Table Discovery")
    print("=" * 70)
    print(f"Host: {host}\n")
    
    # Test different possible issue table names
    tables_to_test = [
        "/api/now/table/issue",
        "/api/now/table/u_issue",
        "/api/now/table/pm_issue",
        "/api/now/table/sn_si_incident",  # Service Incident
        "/api/now/table/problem",
        "/api/now/table/incident",
    ]
    
    results = []
    for table in tables_to_test:
        result = test_table_access(host, username, password, table)
        results.append(result)
        status_symbol = "✓" if result["status"] == "OK" else "✗"
        print(f"{status_symbol} {table}: {result['status']} (HTTP {result.get('http_code', 'N/A')})")
        if result["status"] == "OK":
            print(f"  Records: {result.get('records', 0)}")
        if result.get("error"):
            print(f"  Error: {result['error']}")
    
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    
    accessible_tables = [r for r in results if r["status"] == "OK"]
    if accessible_tables:
        print(f"\nAccessible tables ({len(accessible_tables)}):")
        for r in accessible_tables:
            print(f"  ✓ {r['table']}")
    
    failed_tables = [r for r in results if r["status"] == "FAILED"]
    if failed_tables:
        print(f"\nFailed to access ({len(failed_tables)}):")
        for r in failed_tables:
            print(f"  ✗ {r['table']}: HTTP {r['http_code']}")
    
    print("\nConclusion:")
    if any(t["table"] == "/api/now/table/issue" and t["status"] == "OK" for t in results):
        print("✓ Standard 'issue' table is available and functional")
    else:
        print("✗ Standard 'issue' table is NOT available")
        if any(t["table"] == "/api/now/table/u_issue" and t["status"] == "OK" for t in results):
            print("  Alternative: Use '/api/now/table/u_issue' (custom issue table)")
        elif any(t["table"] == "/api/now/table/pm_issue" and t["status"] == "OK" for t in results):
            print("  Alternative: Use '/api/now/table/pm_issue' (Project Management issue table)")
        else:
            print("  Note: Issue Management module may not be installed on this instance")

if __name__ == "__main__":
    main()
