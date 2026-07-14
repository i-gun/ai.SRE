#!/usr/bin/env python
"""Final comprehensive search for resolved/closed incidents matching the pattern."""

import sys
from datetime import datetime, timedelta

from common import bootstrap

bootstrap()

from servicenow_client import ServiceNowClient, ServiceNowConfigError, ServiceNowAPIError


def main():
    try:
        client = ServiceNowClient.from_env()
        print("[SUCCESS] ServiceNow client initialized successfully")
        print(f"  Host: {client.config.host}")
        print(f"  Designated groups: {', '.join(client.config.assignment_groups)}\n")
    except ServiceNowConfigError as e:
        print(f"[ERROR] Configuration error: {e}")
        sys.exit(1)

    # Calculate date range: last 7 days from 2026-07-12
    target_date = datetime(2026, 7, 12)
    start_date = target_date - timedelta(days=7)
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = target_date.strftime('%Y-%m-%d')

    print("SEARCH PARAMETERS:")
    print(f"  Date range: {start_date_str} to {end_date_str} (last 7 days)")
    print(f"  Short description pattern: Contains 'dam.inbound.cds-sbq query result'")
    print(f"  States: Resolved or Closed")
    print(f"  Assignment groups: IT - Epam - L2 - ODP, IT - Epam - Monitoring - ODP")
    print(f"  Limit: 50 incidents\n")

    try:
        # Query 1: Incidents matching the pattern (both resolved and closed)
        print("Step 1: Searching for incidents matching the pattern...")
        
        query_parts = [
            f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
            "short_descriptionLIKEdam.inbound.cds-sbq query result",
            f"sys_updated_on>={start_date_str}",
        ]
        
        query = "^".join(query_parts)
        
        result = client._request(
            "GET",
            client.INCIDENT_TABLE_PATH,
            params={
                "sysparm_query": query,
                "sysparm_limit": 50,
                "sysparm_fields": ",".join(client.LIST_FIELDS + ["close_code", "close_notes"]),
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_order_by_desc": "sys_updated_on",
            },
        )
        
        incidents = result.get("result", [])
        
        if not incidents:
            print("[INFO] No incidents found matching the search criteria.")
            return
        
        print(f"[SUCCESS] Found {len(incidents)} incident(s) matching the pattern\n")
        
        # Filter for resolved/closed incidents
        resolved_closed = []
        active_incidents = []
        
        for inc in incidents:
            state = inc.get('state', '')
            active = inc.get('active', 'true')
            
            # Check if it's resolved or closed
            if state in ['Resolved', 'Closed', '4', '5', '7', '8'] or active == 'false':
                resolved_closed.append(inc)
            else:
                active_incidents.append(inc)
        
        print("=" * 140)
        print("INCIDENT DETAILS - RESOLVED/CLOSED INCIDENTS")
        print("=" * 140)
        
        if resolved_closed:
            print(f"\nFound {len(resolved_closed)} RESOLVED/CLOSED incidents:\n")
            
            for idx, incident in enumerate(resolved_closed, 1):
                print(f"\n[{idx}] INCIDENT: {incident.get('number')}")
                print(f"    Short Description: {incident.get('short_description')}")
                print(f"    State: {incident.get('state')}")
                print(f"    Priority: {incident.get('priority')}")
                print(f"    Close Code: {incident.get('close_code')}")
                print(f"    Assigned To: {incident.get('assigned_to')}")
                print(f"    Assignment Group: {incident.get('assignment_group')}")
                print(f"    Last Updated: {incident.get('sys_updated_on')}")
                print(f"    System ID: {incident.get('sys_id')}")
                
                close_notes = incident.get('close_notes') or "(No resolution notes)"
                print(f"\n    CLOSE NOTES / RESOLUTION DETAILS:")
                print(f"    " + "-" * 136)
                if close_notes and close_notes != "(No resolution notes)":
                    for line in close_notes.split('\n'):
                        if line.strip():
                            print(f"    {line}")
                else:
                    print(f"    {close_notes}")
                print(f"    " + "-" * 136)
        else:
            print("\n[INFO] No RESOLVED/CLOSED incidents found in the search results.")
        
        # Show active incidents separately
        if active_incidents:
            print("\n" + "=" * 140)
            print(f"ADDITIONAL INFORMATION - ACTIVE INCIDENTS ({len(active_incidents)} found)")
            print("=" * 140)
            print("\nThese incidents match the pattern but are still ACTIVE:\n")
            
            for idx, incident in enumerate(active_incidents, 1):
                print(f"[{idx}] {incident.get('number')}: {incident.get('short_description')} (State: {incident.get('state')})")
        
        # Generate summary report
        print("\n" + "=" * 140)
        print("COMPLETION REPORT")
        print("=" * 140)
        
        print(f"\nTotal incidents matching pattern: {len(incidents)}")
        print(f"Resolved/Closed: {len(resolved_closed)}")
        print(f"Active: {len(active_incidents)}")
        
        if resolved_closed:
            print(f"\nDETAILS OF RESOLVED/CLOSED INCIDENTS:")
            print("-" * 140)
            
            for incident in resolved_closed:
                print(f"\nIncident: {incident.get('number')}")
                print(f"  Description: {incident.get('short_description')}")
                print(f"  State: {incident.get('state')}")
                print(f"  Priority: {incident.get('priority')}")
                print(f"  Close Code: {incident.get('close_code')}")
                
                close_notes = incident.get('close_notes') or "(No notes)"
                if close_notes != "(No notes)":
                    first_line = close_notes.split('\n')[0][:80]
                    print(f"  Resolution: {first_line}")
            
            # Analyze resolution patterns
            print("\n" + "=" * 140)
            print("RESOLUTION PATTERNS & THEMES")
            print("=" * 140)
            
            close_codes = {}
            for incident in resolved_closed:
                code = incident.get('close_code', 'Unknown')
                close_codes[code] = close_codes.get(code, 0) + 1
            
            print("\nClose Codes Distribution:")
            for code, count in sorted(close_codes.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {code}: {count} incident(s)")
            
            print("\nCommon Resolution Keywords:")
            keywords = ['monitoring', 'alert', 'threshold', 'query', 'config', 'restart', 'timeout', 'false', 'alarm']
            resolution_keywords = {}
            
            for incident in resolved_closed:
                notes = (incident.get('close_notes', '') or '').lower()
                for keyword in keywords:
                    if keyword in notes:
                        resolution_keywords[keyword] = resolution_keywords.get(keyword, 0) + 1
            
            if resolution_keywords:
                for keyword, count in sorted(resolution_keywords.items(), key=lambda x: x[1], reverse=True):
                    print(f"  - '{keyword}': {count} occurrence(s)")
            else:
                print("  - No common keywords identified")
        
        print("\n" + "=" * 140)
        
    except ServiceNowAPIError as e:
        print(f"[ERROR] ServiceNow API error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
