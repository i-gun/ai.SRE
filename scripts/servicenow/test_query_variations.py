#!/usr/bin/env python
"""Search for resolved/closed incidents with query variations."""

import sys
from datetime import datetime, timedelta

from common import bootstrap

bootstrap()

from servicenow_client import ServiceNowClient, ServiceNowConfigError, ServiceNowAPIError


def test_query(client, description, query_parts):
    """Test a single query."""
    print(f"\n>>> Testing: {description}")
    query = "^".join(query_parts)
    print(f"    Query: {query}")
    
    try:
        result = client._request(
            "GET",
            client.INCIDENT_TABLE_PATH,
            params={
                "sysparm_query": query,
                "sysparm_limit": 10,
                "sysparm_fields": ",".join(["sys_id", "number", "short_description", "state", "sys_updated_on", "active", "close_code"]),
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_order_by_desc": "sys_updated_on",
            },
        )
        
        incidents = result.get("result", [])
        print(f"    Result: {len(incidents)} incidents found")
        
        if incidents:
            for inc in incidents[:3]:  # Show first 3
                print(f"      - {inc.get('number')}: {inc.get('short_description')[:60]} (state={inc.get('state')}, active={inc.get('active')})")
        
        return incidents
        
    except Exception as e:
        print(f"    ERROR: {e}")
        return []


def main():
    try:
        client = ServiceNowClient.from_env()
        print("[SUCCESS] ServiceNow client initialized")
        print(f"  Host: {client.config.host}")
    except ServiceNowConfigError as e:
        print(f"[ERROR] Configuration error: {e}")
        sys.exit(1)

    target_date = datetime(2026, 7, 12)
    start_date = target_date - timedelta(days=7)
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = target_date.strftime('%Y-%m-%d')
    
    print(f"\nDate range: {start_date_str} to {end_date_str}")
    print(f"Pattern: dam.inbound.cds-sbq query result")
    
    # Test various query combinations
    print("\n" + "="*80)
    print("TESTING QUERY VARIATIONS")
    print("="*80)
    
    # Variation 1: Check all incidents in designated groups with date filter
    test_query(client, "All incidents in designated groups (date filtered)", [
        f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
        f"sys_updated_on>={start_date_str}",
        f"sys_updated_on<={end_date_str} 23:59:59",
    ])
    
    # Variation 2: Check for resolved (state=4)
    test_query(client, "Only resolved incidents (state=4)", [
        f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
        "state=4",
        f"sys_updated_on>={start_date_str}",
    ])
    
    # Variation 3: Check for closed (state=5)
    test_query(client, "Only closed incidents (state=5)", [
        f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
        "state=5",
        f"sys_updated_on>={start_date_str}",
    ])
    
    # Variation 4: Check for states 7 and 8
    test_query(client, "State IN 7,8", [
        f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
        "stateIN7,8",
        f"sys_updated_on>={start_date_str}",
    ])
    
    # Variation 5: Check for all non-active incidents
    test_query(client, "All non-active incidents", [
        f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
        "active=false",
        f"sys_updated_on>={start_date_str}",
    ])
    
    # Variation 6: Pattern search with LIKE
    test_query(client, "Short description pattern match (LIKE)", [
        f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
        "short_descriptionLIKEdam.inbound.cds-sbq",
        f"sys_updated_on>={start_date_str}",
    ])
    
    # Variation 7: Pattern search without state filter
    test_query(client, "Pattern search without state filter", [
        f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
        "short_descriptionLIKEdam.inbound.cds-sbq query result",
    ])
    
    # Variation 8: Try simpler date format
    test_query(client, "Simpler date format", [
        f"assignment_group.nameIN{','.join(client.config.assignment_groups)}",
        "active=false",
        f"sys_updated_on>=2026-07-05",
        f"sys_updated_on<=2026-07-13",
    ])
    
    print("\n" + "="*80)
    print("QUERY TESTING COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
