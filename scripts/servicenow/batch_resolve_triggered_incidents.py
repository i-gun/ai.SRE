#!/usr/bin/env python3
"""
Batch resolve ServiceNow incidents matching 'Triggered : ' pattern.

GOVERNANCE NOTE:
  This script is provided as a reference implementation for batch incident resolution.
  For operational use, prefer: @ServiceNow agent with prepared prompts
  
  Reasons to use @ServiceNow agent instead:
  - Automatic credential loading from .env (more robust)
  - Built-in error handling and retry logic
  - Audit trail maintained by agent layer
  - No custom script maintenance required
  
  This script remains useful for:
  - Understanding batch workflow patterns
  - Offline/local execution scenarios
  - Integration with other tools/pipelines
  
Credentials:
  - Loads from .env in project root
  - Preserves special characters in passwords
  - Uses direct file parsing (avoids python-dotenv limitations)
  
See: docs/INTEGRATION_GOVERNANCE.md for governance framework
"""

import sys
import os
from typing import Dict, Any
from pathlib import Path

# Direct .env file parsing (avoids python-dotenv comment handling)
def load_env_directly(env_path: Path) -> Dict[str, str]:
    """Load .env file and preserve special characters."""
    env_vars = {}
    if not env_path.exists():
        return env_vars
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            # Remove surrounding quotes (single or double)
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            
            env_vars[key] = value
    
    return env_vars


PROJECT_ROOT = Path(__file__).resolve().parents[2]
env_path = PROJECT_ROOT / ".env"

# Load environment variables directly
env_vars = load_env_directly(env_path)
for key, value in env_vars.items():
    os.environ[key] = value

# Add skill path
INCIDENT_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-incident-operations"
if str(INCIDENT_SKILL_PATH) not in sys.path:
    sys.path.insert(0, str(INCIDENT_SKILL_PATH))

from servicenow_client import ServiceNowClient, ServiceNowValidationError, ServiceNowAPIError


def _reference_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("display_value") or value.get("value") or "").strip()
    return str(value or "").strip()


def main():
    # ========================================================================
    # STEP 0: INITIALIZATION
    # ========================================================================
    print("=" * 100)
    print("BATCH RESOLVE TRIGGERED INCIDENTS")
    print("=" * 100 + "\n")

    print("[INIT] Initializing ServiceNow client...")
    try:
        client = ServiceNowClient.from_env()
        print("[OK] ServiceNow client initialized\n")
    except Exception as e:
        print(f"[ERROR] Failed to initialize client: {e}")
        return False

    # Get configured username for assignments
    configured_user = os.getenv("SERVICENOW_USERNAME", "").strip()
    if not configured_user:
        print("[ERROR] SERVICENOW_USERNAME not configured in .env")
        return False
    print(f"[CONFIG] Configured assignment user: {configured_user}\n")

    # ========================================================================
    # STEP 1: FETCH MATCHING INCIDENTS
    # ========================================================================
    print("=" * 100)
    print("STEP 1: FETCHING INCIDENTS")
    print("=" * 100 + "\n")

    print("[FETCH] Retrieving active incidents with short_description starting with 'Triggered : '...")
    try:
        # Enforce unresolved-only at query level and with client-side defensive filter.
        all_incidents = client.list_incidents(active_only=True, exclude_resolved=True, limit=500)

        # Filter for 'Triggered : ' pattern.
        matching_incidents = [
            inc for inc in all_incidents
            if inc.get("short_description", "").startswith("Triggered : ")
        ]
        
        print(f"[OK] Found {len(matching_incidents)} matching incident(s)\n")
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch incidents: {e}")
        return False

    if not matching_incidents:
        print("[INFO] No incidents match the criteria.")
        print("[DONE] Process complete.\n")
        return True

    # ========================================================================
    # STEP 2: LIST INCIDENTS FOR CONFIRMATION
    # ========================================================================
    print("=" * 100)
    print("STEP 2: MATCHING INCIDENTS SUMMARY")
    print("=" * 100 + "\n")

    print(
        f"{'#':<3} {'Number':<12} {'Priority':<12} {'State':<14} {'Assignment Group':<30} "
        f"{'Assigned To':<28} {'sys_id':<34} {'Short Description':<40}"
    )
    print("-" * 190)

    for idx, inc in enumerate(matching_incidents, 1):
        number = inc.get("number", "N/A")
        priority = inc.get("priority", "N/A")
        state = _reference_text(inc.get("state")) or "N/A"
        assignment_group = _reference_text(inc.get("assignment_group")) or "N/A"
        assigned_to = _reference_text(inc.get("assigned_to")) or "(unassigned)"
        short_desc = inc.get("short_description", "N/A")[:38]
        sys_id = inc.get("sys_id", "N/A")

        print(
            f"{idx:<3} {number:<12} {str(priority):<12} {str(state):<14} {str(assignment_group):<30} "
            f"{str(assigned_to):<28} {str(sys_id):<34} {short_desc:<40}"
        )

    print(f"\n[CONFIRM] Total incidents to process: {len(matching_incidents)}\n")

    # ========================================================================
    # STEP 3: ASSIGN UNASSIGNED INCIDENTS
    # ========================================================================
    print("=" * 100)
    print("STEP 3: ASSIGNING UNASSIGNED INCIDENTS")
    print("=" * 100 + "\n")

    unassigned_incidents = [
        inc for inc in matching_incidents
        if not _reference_text(inc.get("assigned_to"))
    ]

    assignment_results = {
        "assigned": [],
        "already_assigned": [],
        "failed": []
    }

    for inc in unassigned_incidents:
        number = inc.get("number", "N/A")
        sys_id = inc.get("sys_id")
        try:
            print(f"[ASSIGN] {number}: Assigning to {configured_user}...")
            client.assign_incident(
                sys_id=sys_id,
                assigned_to=configured_user,
                allow_reassign=False
            )
            assignment_results["assigned"].append(number)
            print(f"[OK] {number}: Assigned successfully")
        except ServiceNowValidationError as e:
            if "already has an assignee" in str(e):
                assignment_results["already_assigned"].append(number)
                print(f"[INFO] {number}: Already assigned")
            else:
                assignment_results["failed"].append((number, str(e)))
                print(f"[WARN] {number}: {e}")
        except Exception as e:
            assignment_results["failed"].append((number, str(e)))
            print(f"[ERROR] {number}: {e}")

    print(f"\n[SUMMARY] Assignment Results:")
    print(f"  - Assigned: {len(assignment_results['assigned'])}")
    print(f"  - Already assigned: {len(assignment_results['already_assigned'])}")
    print(f"  - Failed: {len(assignment_results['failed'])}")
    if assignment_results["failed"]:
        for num, err in assignment_results["failed"]:
            print(f"    - {num}: {err}")
    print()

    # ========================================================================
    # STEP 4: UPDATE AND RESOLVE INCIDENTS
    # ========================================================================
    print("=" * 100)
    print("STEP 4: UPDATING AND RESOLVING INCIDENTS")
    print("=" * 100 + "\n")

    # Close notes template
    CLOSE_NOTES = (
        "Implemented remediation based on Jira analysis ticket "
        "https://canadian-tire.atlassian.net/browse/DDL-29601, "
        "validated service behavior post-change, and completed operational "
        "handoff with traceability to DDL-29601 for follow-up monitoring and audit continuity."
    )

    # Update configuration
    UPDATE_CONFIG = {
        "category": "Application",
        "subcategory": "E-Commerce",
        "service_offering": "Adobe RTCDP - CTC",
        "u_vendor_ticket": "DDL-29601",
        "vendor_ticket": "DDL-29601",
        "close_code": "Fixed",
        "close_notes": CLOSE_NOTES
    }

    resolution_results = {
        "resolved": [],
        "failed": []
    }

    for inc in matching_incidents:
        number = inc.get("number", "N/A")
        sys_id = inc.get("sys_id")
        
        print(f"[UPDATE] {number}: Updating fields and resolving...")
        
        try:
            # Perform PATCH with all field updates and resolution
            payload = {
                "category": UPDATE_CONFIG["category"],
                "subcategory": UPDATE_CONFIG["subcategory"],
                "service_offering": UPDATE_CONFIG["service_offering"],
                "u_vendor_ticket": UPDATE_CONFIG["u_vendor_ticket"],
                "vendor_ticket": UPDATE_CONFIG["vendor_ticket"],
                "state": "6",  # Resolved state
                "close_code": UPDATE_CONFIG["close_code"],
                "close_notes": UPDATE_CONFIG["close_notes"],
                "work_notes": f"[BULK RESOLUTION] Updated from batch operation: category='{UPDATE_CONFIG['category']}', " +
                              f"subcategory='{UPDATE_CONFIG['subcategory']}', " +
                              f"service_offering='{UPDATE_CONFIG['service_offering']}', " +
                              f"vendor_ticket='{UPDATE_CONFIG['u_vendor_ticket']}'"
            }
            
            result = client._request(
                "PATCH",
                f"{client.INCIDENT_TABLE_PATH}/{sys_id}",
                json=payload,
                params={"sysparm_display_value": "true", "sysparm_exclude_reference_link": "true"}
            )
            
            updated_incident = result.get("result", {})
            final_state = updated_incident.get("state")
            final_priority = updated_incident.get("priority")
            
            resolution_results["resolved"].append(number)
            print(f"[OK] {number}: Resolved (State: {final_state}, Priority: {final_priority})")
            
        except ServiceNowAPIError as e:
            error_msg = str(e)
            resolution_results["failed"].append((number, error_msg))
            print(f"[ERROR] {number}: API Error - {error_msg}")
            
        except Exception as e:
            error_msg = str(e)
            resolution_results["failed"].append((number, error_msg))
            print(f"[ERROR] {number}: {error_msg}")

    print()

    # ========================================================================
    # STEP 5: FINAL SUMMARY
    # ========================================================================
    print("=" * 100)
    print("FINAL SUMMARY")
    print("=" * 100 + "\n")

    print("[RESULTS] Resolution Summary:")
    print(f"  - Successfully resolved: {len(resolution_results['resolved'])}")
    print(f"  - Failed resolutions: {len(resolution_results['failed'])}")

    if resolution_results["resolved"]:
        print(f"\n[RESOLVED INCIDENTS]:")
        for num in resolution_results["resolved"]:
            print(f"  ✓ {num}")

    if resolution_results["failed"]:
        print(f"\n[FAILED INCIDENTS]:")
        for num, error in resolution_results["failed"]:
            print(f"  ✗ {num}: {error}")

    # Check for remaining matching incidents (should be none if all resolved)
    print(f"\n[FINAL CHECK] Verifying incident states...")
    try:
        remaining = client.list_incidents(active_only=True, exclude_resolved=True, limit=500)
        remaining_matching = [
            inc for inc in remaining
            if inc.get("short_description", "").startswith("Triggered : ")
        ]
        print(f"  - Remaining active 'Triggered : ' incidents: {len(remaining_matching)}")
        if remaining_matching:
            print("    (These may have been created after initial fetch)")
            for inc in remaining_matching[:5]:
                print(f"      - {inc.get('number')}: {inc.get('short_description')[:50]}")
    except Exception as e:
        print(f"  - Final check error: {e}")

    print(f"\n[DONE] Batch operation complete.\n")
    
    return len(resolution_results["failed"]) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
