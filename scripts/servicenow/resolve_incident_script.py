#!/usr/bin/env python3
"""
ServiceNow Incident Resolution Script
Resolves incident INC0039891 with provided resolution details
"""

import sys

from common import bootstrap

bootstrap(include_auth=True)

from servicenow_client import ServiceNowClient
from servicenow_env import load_servicenow_auth_config_from_env, ServiceNowAuthConfigError

def main():
    # Validate credentials from environment
    try:
        auth_config = load_servicenow_auth_config_from_env()
        print("[INFO] ServiceNow authentication configuration validated successfully")
        print(f"[INFO] Host: {auth_config.host}")
        print(f"[INFO] Username: {auth_config.username}")
        print(f"[INFO] Assignment Groups: {', '.join(auth_config.assignment_groups)}")
    except ServiceNowAuthConfigError as e:
        print(f"[ERROR] Authentication configuration error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to load authentication config: {e}")
        return False
    
    # Initialize client from environment
    try:
        client = ServiceNowClient.from_env()
        print("[INFO] ServiceNow client initialized successfully")
    except Exception as e:
        print(f"[ERROR] Failed to initialize client: {e}")
        return False

    # Resolution parameters
    incident_number = "INC0039891"
    close_code = "Solved (Permanently)"
    close_notes = """Problem PRB0040185 has been created and escalated for root-cause analysis and systemic remediation. Issue tracking and credential key rotation will be managed by the BET team under the scope of BET-22489. The BET team will perform comprehensive key rotation and renewal procedures to prevent future expiration-related alerts. Monitoring will continue post-rotation to confirm resolution."""

    work_note = "[RESOLUTION] Incident resolved. Problem record PRB0040185 created for long-term tracking. BET team assigned for key rotation under BET-22489."

    print(f"\n{'='*80}")
    print(f"INCIDENT RESOLUTION OPERATION")
    print(f"{'='*80}")
    print(f"Incident Number: {incident_number}")
    print(f"Close Code: {close_code}")
    print(f"Work Note: {work_note}")
    print(f"{'='*80}\n")

    # Execute resolution
    try:
        result = client.resolve_incident(
            incident_number=incident_number,
            close_code=close_code,
            close_notes=close_notes,
            work_note=work_note
        )
        
        print(f"\n[SUCCESS] Incident resolution completed successfully")
        print(f"\n{'='*80}")
        print(f"RESOLUTION RESULT:")
        print(f"{'='*80}")
        print(result)
        print(f"{'='*80}\n")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Resolution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
