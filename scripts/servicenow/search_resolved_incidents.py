#!/usr/bin/env python
"""Search for resolved/closed incidents matching specific criteria."""

import sys
from datetime import datetime, timedelta

from common import bootstrap

bootstrap()

from servicenow_client import ServiceNowClient, ServiceNowConfigError, ServiceNowAPIError


def format_incident_summary(incident):
    """Format a single incident for display."""
    return {
        'number': incident.get('number', ''),
        'short_description': incident.get('short_description', ''),
        'state': incident.get('state', ''),
        'priority': incident.get('priority', ''),
        'close_code': incident.get('close_code', ''),
        'close_notes': incident.get('close_notes', ''),
        'sys_updated_on': incident.get('sys_updated_on', ''),
        'assigned_to': incident.get('assigned_to', ''),
        'assignment_group': incident.get('assignment_group', ''),
        'sys_id': incident.get('sys_id', ''),
    }


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

    print("Search Parameters:")
    print(f"  Date range: {start_date_str} to {end_date_str} (last 7 days)")
    print(f"  Short description pattern: Contains 'dam.inbound.cds-sbq query result'")
    print(f"  State: Resolved or Closed")
    print(f"  Assignment groups: IT - Epam - L2 - ODP, IT - Epam - Monitoring - ODP")
    print(f"  Limit: 50 incidents\n")

    try:
        # Build query using ServiceNow query language
        # State codes: 4=Resolved, 5=Closed (or 7, 8 depending on instance)
        # We'll query for both resolved and closed incidents
        
        query_parts = [
            # Match designated assignment groups
            f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
            # Search for the pattern in short_description
            "short_descriptionLIKEdam.inbound.cds-sbq query result is > 0.0 for 15 minutes",
            # Filter by date range (sys_updated_on)
            f"sys_updated_on>={start_date_str} 00:00:00",
            f"sys_updated_on<={end_date_str} 23:59:59",
            # Filter by state: Resolved or Closed
            # In ServiceNow: 4=Resolved, 5=Closed
            "stateIN4,5",
            # Exclude active incidents
            "active=false",
        ]
        
        query = "^".join(query_parts)
        
        print(f"Executing ServiceNow API query...")
        print(f"Query string: {query}\n")
        
        # Make the API request
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
            print("No incidents found matching the search criteria.")
            return
        
        print(f"Found {len(incidents)} incidents matching criteria\n")
        print("=" * 120)
        
        for idx, incident in enumerate(incidents, 1):
            summary = format_incident_summary(incident)
            print(f"\n[{idx}] Incident: {summary['number']}")
            print(f"    Short Description: {summary['short_description']}")
            print(f"    State: {summary['state']}")
            print(f"    Priority: {summary['priority']}")
            print(f"    Close Code: {summary['close_code']}")
            print(f"    Assigned To: {summary['assigned_to']}")
            print(f"    Assignment Group: {summary['assignment_group']}")
            print(f"    Last Updated: {summary['sys_updated_on']}")
            print(f"\n    Close Notes (Resolution Details):")
            close_notes = summary['close_notes'] or "(No resolution notes)"
            # Format close notes with indentation
            for line in close_notes.split('\n'):
                print(f"    {line}")
            print("-" * 120)
        
        # Generate summary report
        print("\n" + "=" * 120)
        print("COMPLETION REPORT")
        print("=" * 120)
        print(f"\nTotal Incidents Found: {len(incidents)}")
        print(f"\nIncident Breakdown:")
        print("-" * 120)
        
        for incident in incidents:
            print(f"\n• {incident.get('number')} - {incident.get('short_description')}")
            print(f"  State: {incident.get('state')} | Priority: {incident.get('priority')} | Close Code: {incident.get('close_code')}")
            print(f"  Resolution: {incident.get('close_notes', '(No notes)').split(chr(10))[0][:100]}")
        
        # Analyze resolution patterns
        print("\n" + "=" * 120)
        print("RESOLUTION PATTERNS/THEMES")
        print("=" * 120)
        
        close_codes = {}
        for incident in incidents:
            code = incident.get('close_code', 'Unknown')
            close_codes[code] = close_codes.get(code, 0) + 1
        
        print("\nClose Codes Distribution:")
        for code, count in sorted(close_codes.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {code}: {count} incident(s)")
        
        print("\nCommon Resolution Themes:")
        # Extract common themes from close_notes
        resolution_keywords = {}
        keywords = ['restart', 'restart', 'config', 'fixed', 'queue', 'retry', 'timeout', 'connection', 'memory', 'cpu', 'resolved']
        
        for incident in incidents:
            notes = (incident.get('close_notes', '') or '').lower()
            for keyword in keywords:
                if keyword in notes:
                    resolution_keywords[keyword] = resolution_keywords.get(keyword, 0) + 1
        
        if resolution_keywords:
            for keyword, count in sorted(resolution_keywords.items(), key=lambda x: x[1], reverse=True):
                print(f"  • '{keyword}': mentioned in {count} resolution note(s)")
        else:
            print("  • No common keywords detected in resolution notes")
        
        print("\n" + "=" * 120)
        
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
