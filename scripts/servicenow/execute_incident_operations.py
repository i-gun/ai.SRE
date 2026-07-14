#!/usr/bin/env python3
"""
Execute ServiceNow incident operations on INC0039027:
1. Update incident fields (vendor ticket, category, subcategory, service offering)
2. Resolve incident with close code and close notes
"""

import sys

from common import bootstrap

bootstrap()

from servicenow_client import ServiceNowClient, ServiceNowValidationError, ServiceNowAPIError

def main():
    # ========================================================================
    # Initialize ServiceNow Client
    # ========================================================================
    print("Initializing ServiceNow client...")
    try:
        client = ServiceNowClient.from_env()
        print("[OK] ServiceNow client initialized successfully\n")
    except Exception as e:
        print("[ERROR] Client initialization failed: {}".format(e))
        return False

    # ========================================================================
    # STEP 1: Update Incident Fields
    # ========================================================================
    print("=" * 80)
    print("STEP 1: UPDATING INCIDENT FIELDS")
    print("=" * 80 + "\n")

    try:
        # First, retrieve the incident to get current state
        incident = client._find_incident(incident_number="INC0039027", sys_id=None)
        incident_sys_id = incident.get("sys_id")
        print("[OK] Found incident INC0039027")
        print("  - sys_id: {}".format(incident_sys_id))
        print("  - Current state: {}".format(incident.get('state')))
        print("  - Current priority: {}".format(incident.get('priority')))
        print()

        # Prepare the update payload with field updates and work note
        update_payload = {
            "u_vendor_ticket": "DDL-34885",
            "vendor_ticket": "DDL-34885",
            "category": "Application",
            "subcategory": "E-Commerce",
            "service_offering": "ODP Azure Service Bus",
            "work_notes": "[UPDATE] Incident enriched with vendor ticket reference and categorization. Escalating to SRE team via DDL-34885 for root-cause analysis."
        }

        # Execute PATCH to update fields
        result = client._request(
            "PATCH",
            "{}/{}".format(client.INCIDENT_TABLE_PATH, incident_sys_id),
            json=update_payload,
            params={"sysparm_display_value": "true", "sysparm_exclude_reference_link": "true"},
        )

        updated_incident = result.get("result", {})

        print("[OK] Field updates completed successfully:")
        print("  - u_vendor_ticket: {}".format(updated_incident.get('u_vendor_ticket', 'N/A')))
        print("  - category: {}".format(updated_incident.get('category', 'N/A')))
        print("  - subcategory: {}".format(updated_incident.get('subcategory', 'N/A')))
        print("  - service_offering: {}".format(updated_incident.get('service_offering', 'N/A')))
        print("  - work_note added: [UPDATE] Incident enriched...")
        print()

    except (ServiceNowValidationError, ServiceNowAPIError) as e:
        print("[ERROR] Field update failed: {}".format(e))
        return False
    except Exception as e:
        print("[ERROR] Unexpected error during field update: {}".format(e))
        return False

    # ========================================================================
    # STEP 2: Resolve Incident
    # ========================================================================
    print("=" * 80)
    print("STEP 2: RESOLVING INCIDENT")
    print("=" * 80 + "\n")

    try:
        close_notes_text = (
            "We are closing this incident to conduct a more thorough investigation in JIRA. "
            "The responsibility for analyzing and identifying the root cause now falls upon the Digital Site Reliability Engineering (SRE) team. "
            "While their objective is to promptly resolve the underlying issue, it's important to note that the resolution time may differ based on resource availability, "
            "as well as the urgency and severity of the impact. https://canadian-tire.atlassian.net/browse/DDL-34885"
        )

        # Resolve incident with close code and close notes
        resolved = client.resolve_incident(
            incident_number="INC0039027",
            close_code="Fixed",
            close_notes=close_notes_text,
            work_note="[RESOLUTION] Incident closed and escalated to SRE team. Ongoing investigation tracked in DDL-34885."
        )

        print("[OK] Incident resolved successfully:")
        print("  - Incident Number: {}".format(resolved.get('number', 'N/A')))
        print("  - sys_id: {}".format(resolved.get('sys_id', 'N/A')))
        print("  - State: {}".format(resolved.get('state', 'N/A')))
        print("  - Close Code: {}".format(resolved.get('close_code', 'N/A')))
        print("  - Close Notes (first 100 chars): {}...".format(resolved.get('close_notes', 'N/A')[:100]))
        print()

    except (ServiceNowValidationError, ServiceNowAPIError) as e:
        print("[ERROR] Resolution failed: {}".format(e))
        return False
    except Exception as e:
        print("[ERROR] Unexpected error during resolution: {}".format(e))
        return False

    # ========================================================================
    # FINAL VERIFICATION
    # ========================================================================
    print("=" * 80)
    print("FINAL VERIFICATION")
    print("=" * 80 + "\n")

    try:
        # Retrieve final incident state to verify all changes
        final_incident = client._find_incident(incident_number="INC0039027", sys_id=None)

        print("[OK] Final incident state verified:")
        print("  - Incident: {}".format(final_incident.get('number', 'N/A')))
        print("  - sys_id: {}".format(final_incident.get('sys_id', 'N/A')))
        print("  - State: {}".format(final_incident.get('state', 'N/A')))
        print("  - Priority: {}".format(final_incident.get('priority', 'N/A')))
        print("  - Category: {}".format(final_incident.get('category', 'N/A')))
        print("  - Subcategory: {}".format(final_incident.get('subcategory', 'N/A')))
        print("  - Service Offering: {}".format(final_incident.get('service_offering', 'N/A')))
        vendor_ticket = final_incident.get('u_vendor_ticket') or final_incident.get('vendor_ticket')
        print("  - Vendor Ticket: {}".format(vendor_ticket or 'N/A'))
        print("  - Close Code: {}".format(final_incident.get('close_code', 'N/A')))
        print()

        print("=" * 80)
        print("[SUCCESS] ALL OPERATIONS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        return True

    except (ServiceNowValidationError, ServiceNowAPIError) as e:
        print("[ERROR] Verification failed: {}".format(e))
        return False
    except Exception as e:
        print("[ERROR] Unexpected error during verification: {}".format(e))
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
