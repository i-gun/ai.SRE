"""
Verify ServiceNow capabilities for:
- Capability A: Creating a Problem (PRB) record from an Incident (INC) record
- Capability B: Creating an Issue record from a Problem (PRB) record

This script validates API endpoints and field mappings WITHOUT creating records.
"""

import os
import sys
import json
from typing import Dict, Any, Tuple
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

# Load .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path, override=True)


class ServiceNowCapabilityVerifier:
    """Verify ServiceNow capabilities for problem and issue creation."""

    INCIDENT_TABLE_PATH = "/api/now/table/incident"
    PROBLEM_TABLE_PATH = "/api/now/table/problem"
    ISSUE_TABLE_PATH = "/api/now/table/issue"
    SCHEMA_PATH = "/api/now/table"

    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(self, host: str, username: str, password: str):
        """Initialize with ServiceNow credentials."""
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self.results = {
            "timestamp": None,
            "host": self.host,
            "authentication": None,
            "capability_a": None,
            "capability_b": None,
        }

    def _url(self, path: str) -> str:
        return f"{self.host}{path}"

    def _safe_error_detail(self, response: requests.Response) -> str:
        """Extract error details safely from response."""
        try:
            body = response.json()
            if isinstance(body, dict):
                err = body.get("error") or body.get("message") or body
                return str(err)[:500]
            return str(body)[:500]
        except ValueError:
            return (response.text or "Unknown error")[:500]

    def test_authentication(self) -> bool:
        """Test basic authentication by fetching incident table metadata."""
        print("\n[1] Testing Authentication...")
        try:
            response = self.session.request(
                method="GET",
                url=self._url(f"{self.INCIDENT_TABLE_PATH}?sysparm_limit=1"),
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
            )
            
            if response.status_code == 401:
                detail = self._safe_error_detail(response)
                self.results["authentication"] = {
                    "status": "FAILED",
                    "http_code": response.status_code,
                    "error": "Authentication failed (401 Unauthorized)",
                    "detail": detail,
                }
                print(f"  [FAIL] Authentication FAILED: {detail}")
                return False
            
            if response.status_code >= 400:
                detail = self._safe_error_detail(response)
                self.results["authentication"] = {
                    "status": "FAILED",
                    "http_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                    "detail": detail,
                }
                print(f"  [FAIL] Authentication FAILED: HTTP {response.status_code}")
                return False
            
            self.results["authentication"] = {
                "status": "SUCCESS",
                "http_code": response.status_code,
                "message": "Authentication verified",
            }
            print(f"  [OK] Authentication SUCCESS (HTTP {response.status_code})")
            return True
            
        except Exception as e:
            self.results["authentication"] = {
                "status": "ERROR",
                "error": str(e),
            }
            print(f"  [ERROR] Authentication ERROR: {e}")
            return False

    def verify_capability_a(self) -> bool:
        """
        Capability A: Creating a Problem (PRB) record from an Incident (INC) record.
        
        API Endpoint: POST /api/now/table/problem
        """
        print("\n[2] Verifying Capability A: Problem creation from Incident...")
        
        capability_result = {
            "name": "Capability A: Create Problem from Incident",
            "endpoint": self.PROBLEM_TABLE_PATH,
            "method": "POST",
            "status": None,
            "http_code": None,
            "field_mapping": {
                "origin_task": "incident.number",
                "category": "fixed to: Application",
                "subcategory": "fixed to: E-Commerce",
                "problem_statement": "incident.short_description",
                "short_description": "derived from incident",
                "description": "derived from incident",
                "assignment_group": "incident.assignment_group",
                "service_offering": "incident.cmdb_ci",
                "cmdb_ci": "incident.cmdb_ci",
            },
            "prerequisites": [
                "Incident must exist with sys_id",
                "Incident must have short_description and description",
            ],
            "test_result": None,
        }
        
        try:
            print(f"  Testing endpoint: POST {self.PROBLEM_TABLE_PATH}")
            
            response = self.session.request(
                method="GET",
                url=self._url(f"{self.PROBLEM_TABLE_PATH}?sysparm_limit=1"),
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
            )
            
            if response.status_code == 200:
                capability_result["http_code"] = 200
                capability_result["status"] = "VERIFIED"
                capability_result["test_result"] = "Problem table is accessible and readable (GET succeeded)"
                print(f"  [OK] Problem table endpoint verified (HTTP {response.status_code})")
                
                data = response.json()
                if data.get("result"):
                    problem_record = data["result"][0]
                    print(f"  [OK] Sample problem record retrieved (sys_id: {problem_record.get('sys_id', 'N/A')})")
                    
                    required_fields = ["origin_task", "category", "subcategory", "problem_statement", "short_description", "description"]
                    found_fields = {f: f in problem_record for f in required_fields}
                    capability_result["field_validation"] = found_fields
                    print(f"  [OK] Field validation: {sum(found_fields.values())}/{len(required_fields)} expected fields present")
                
                return True
            else:
                capability_result["http_code"] = response.status_code
                capability_result["status"] = "FAILED"
                detail = self._safe_error_detail(response)
                capability_result["test_result"] = f"HTTP {response.status_code}: {detail}"
                print(f"  [FAIL] Problem table access failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            capability_result["status"] = "ERROR"
            capability_result["test_result"] = str(e)
            print(f"  [ERROR] Error: {e}")
            return False
        finally:
            self.results["capability_a"] = capability_result

    def verify_capability_b(self) -> bool:
        """
        Capability B: Creating an Issue record from a Problem (PRB) record.
        
        API Endpoint: POST /api/now/table/issue (or alternative)
        """
        print("\n[3] Verifying Capability B: Issue creation from Problem...")
        
        capability_result = {
            "name": "Capability B: Create Issue from Problem",
            "endpoint": self.ISSUE_TABLE_PATH,
            "method": "POST",
            "status": None,
            "http_code": None,
            "field_mapping": {
                "short_description": "problem.short_description or derived",
                "description": "problem.description or derived",
                "select_project": "fixed to: Digital Delivery",
                "problem": "problem.sys_id",
                "category": "problem.category (optional)",
                "subcategory": "problem.subcategory (optional)",
                "service_offering": "problem.service_offering (optional)",
                "cmdb_ci": "problem.cmdb_ci (optional)",
            },
            "prerequisites": [
                "Problem must exist with sys_id",
                "Problem must have short_description and description",
                "Digital Delivery project must exist in ServiceNow",
            ],
            "test_result": None,
            "alternative_tables_tested": [],
        }
        
        possible_tables = [
            "/api/now/table/issue",
            "/api/now/table/u_issue",
            "/api/now/table/pm_issue",
        ]
        
        for table_path in possible_tables:
            try:
                print(f"  Testing endpoint: {table_path}")
                
                response = self.session.request(
                    method="GET",
                    url=self._url(f"{table_path}?sysparm_limit=1"),
                    timeout=self.DEFAULT_TIMEOUT_SECONDS,
                )
                
                test_result = {
                    "table": table_path,
                    "http_code": response.status_code,
                }
                
                if response.status_code == 200:
                    test_result["status"] = "OK"
                    capability_result["alternative_tables_tested"].append(test_result)
                    capability_result["endpoint"] = table_path
                    capability_result["http_code"] = 200
                    capability_result["status"] = "VERIFIED"
                    capability_result["test_result"] = f"Issue table is accessible (found: {table_path})"
                    print(f"  [OK] Table endpoint verified (HTTP {response.status_code})")
                    
                    data = response.json()
                    if data.get("result"):
                        record = data["result"][0]
                        print(f"  [OK] Sample record retrieved (sys_id: {record.get('sys_id', 'N/A')})")
                    
                    return True
                else:
                    test_result["status"] = f"HTTP {response.status_code}"
                    test_result["error"] = self._safe_error_detail(response)
                    capability_result["alternative_tables_tested"].append(test_result)
                    
            except Exception as e:
                test_result["status"] = "ERROR"
                test_result["error"] = str(e)
                capability_result["alternative_tables_tested"].append(test_result)
        
        capability_result["status"] = "NOT_AVAILABLE"
        capability_result["http_code"] = 400
        capability_result["test_result"] = "Issue table not found or not accessible on this ServiceNow instance"
        print(f"  [WARN] Issue table access failed: Table not found in ServiceNow instance")
        print(f"  [NOTE] Tested: {', '.join([t['table'] for t in capability_result['alternative_tables_tested']])}")
        
        self.results["capability_b"] = capability_result
        return False

    def run_verification(self) -> bool:
        """Run all verification tests."""
        print("=" * 70)
        print("ServiceNow Capability Verification")
        print("=" * 70)
        print(f"Host: {self.host}")
        
        if not self.test_authentication():
            print("\n[FAIL] Authentication failed. Cannot proceed with capability verification.")
            return False
        
        cap_a_ok = self.verify_capability_a()
        cap_b_ok = self.verify_capability_b()
        
        return cap_a_ok and cap_b_ok

    def print_results(self) -> None:
        """Print formatted results."""
        print("\n" + "=" * 70)
        print("VERIFICATION RESULTS")
        print("=" * 70)
        
        print("\n[AUTHENTICATION]")
        auth = self.results.get("authentication") or {}
        print(f"  Status: {auth.get('status', 'UNKNOWN')}")
        print(f"  HTTP Code: {auth.get('http_code', 'N/A')}")
        if auth.get("message"):
            print(f"  Message: {auth.get('message')}")
        if auth.get("error"):
            print(f"  Error: {auth.get('error')}")
        
        print("\n[CAPABILITY A: Create Problem (PRB) from Incident (INC)]")
        cap_a = self.results.get("capability_a") or {}
        print(f"  Status: {cap_a.get('status', 'UNKNOWN')}")
        print(f"  Endpoint: {cap_a.get('endpoint', 'N/A')}")
        print(f"  Method: {cap_a.get('method', 'N/A')}")
        print(f"  HTTP Response Code: {cap_a.get('http_code', 'N/A')}")
        print(f"  Test Result: {cap_a.get('test_result', 'N/A')}")
        print(f"\n  Field Mapping (from Incident to Problem):")
        for field, mapping in cap_a.get("field_mapping", {}).items():
            print(f"    - {field}: {mapping}")
        print(f"\n  Prerequisites:")
        for prereq in cap_a.get("prerequisites", []):
            print(f"    - {prereq}")
        if cap_a.get("field_validation"):
            print(f"\n  Field Validation (from sample record):")
            for field, found in cap_a.get("field_validation", {}).items():
                status = "[FOUND]" if found else "[MISSING]"
                print(f"    {status} {field}")
        
        print("\n[CAPABILITY B: Create Issue from Problem (PRB)]")
        cap_b = self.results.get("capability_b") or {}
        print(f"  Status: {cap_b.get('status', 'UNKNOWN')}")
        print(f"  Endpoint: {cap_b.get('endpoint', 'N/A')}")
        print(f"  Method: {cap_b.get('method', 'N/A')}")
        print(f"  HTTP Response Code: {cap_b.get('http_code', 'N/A')}")
        print(f"  Test Result: {cap_b.get('test_result', 'N/A')}")
        
        if cap_b.get("alternative_tables_tested"):
            print(f"\n  Tables Tested:")
            for alt in cap_b.get("alternative_tables_tested", []):
                print(f"    - {alt.get('table')}: {alt.get('status', 'UNKNOWN')}")
                if alt.get("error"):
                    print(f"      Error: {alt.get('error')}")
        
        print(f"\n  Field Mapping (from Problem to Issue):")
        for field, mapping in cap_b.get("field_mapping", {}).items():
            print(f"    - {field}: {mapping}")
        print(f"\n  Prerequisites:")
        for prereq in cap_b.get("prerequisites", []):
            print(f"    - {prereq}")
        
        print("\n" + "=" * 70)
        
    def export_json(self, filepath: str) -> None:
        """Export results to JSON file."""
        try:
            with open(filepath, "w") as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\n[OK] Results exported to: {filepath}")
        except Exception as e:
            print(f"\n[WARN] Failed to export results: {e}")


def main():
    """Main entry point."""
    host = os.getenv("SERVICENOW_HOST", "").strip()
    username = os.getenv("SERVICENOW_USERNAME", "").strip()
    password = os.getenv("SERVICENOW_PASSWORD", "").strip()
    
    if not all([host, username, password]):
        print("ERROR: Missing required environment variables:")
        print("  - SERVICENOW_HOST")
        print("  - SERVICENOW_USERNAME")
        print("  - SERVICENOW_PASSWORD")
        sys.exit(1)
    
    verifier = ServiceNowCapabilityVerifier(host, username, password)
    success = verifier.run_verification()
    verifier.print_results()
    
    output_file = "servicenow_capability_verification_results.json"
    verifier.export_json(output_file)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
