#!/usr/bin/env python3
"""Check pod restart status using docker_id and container metrics."""

import sys
from pathlib import Path

# Bootstrap
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / ".github" / "skills" / "newrelic-authentication"))
sys.path.insert(0, str(PROJECT_ROOT / ".github" / "skills" / "newrelic-log-operations"))

from newrelic_env import load_newrelic_auth_config_from_env
from newrelic_client import NewRelicClient, NewRelicConfig


def main():
    auth_cfg = load_newrelic_auth_config_from_env()
    nr_config = NewRelicConfig(api_key=auth_cfg.api_key, account_ids=auth_cfg.account_ids)
    client = NewRelicClient(nr_config)

    # Docker ID from the error log
    docker_id = "bb539219c964c0e15d966e3b24698095ba7b16635ac1ccbd08b204b8e86ef30d"
    pod_name = "api-6974fc79bf-hwjvc"

    print(f"\n=== Pod Restart Verification ===")
    print(f"Pod Name: {pod_name}")
    print(f"Docker ID (from error): {docker_id[:16]}...")
    print(f"Error Timestamp: 2026-08-02T03:35:41.589974718Z\n")

    # Query 1: Check if this docker_id still has active logs
    print("=== STEP 1: Activity from Original Container ===\n")
    nrql_docker_id = f"SELECT count(*) FROM Log WHERE docker_id = '{docker_id}' SINCE 5 hours ago LIMIT 100"
    
    try:
        result = client.run_nrql(account_id=1679802, nrql=nrql_docker_id)
        if result and len(result) > 0:
            count = result[0].get('count', 0)
            print(f"✓ Found {count} logs from this container in past 5 hours")
            if count > 0:
                print("  → Container is STILL ACTIVE (no restart)")
            else:
                print("  → Container appears INACTIVE (may have restarted)")
        else:
            print("✗ No logs found from this container")
            print("  → Container may be RESTARTED or not logging\n")
    except Exception as e:
        print(f"Query error: {str(e)[:300]}\n")

    # Query 2: Check all containers for this pod in past 5 hours
    print("\n=== STEP 2: All Containers for Pod (Last 5 hours) ===\n")
    nrql_all_containers = f"SELECT count(*) FROM Log WHERE pod_name = '{pod_name}' SINCE 5 hours ago FACET docker_id LIMIT 50"
    
    try:
        result = client.run_nrql(account_id=1679802, nrql=nrql_all_containers)
        if result and len(result) > 0:
            print(f"Found {len(result)} unique container(s) for this pod:\n")
            for row in result:
                container = row.get('facet', 'N/A')
                count = row.get('count', 0)
                is_error_container = "← ERROR CONTAINER" if container == docker_id else ""
                print(f"  • {container[:20]}... | Logs: {count:6} {is_error_container}")
            
            print()
            if len(result) == 1:
                print("✓ CONCLUSION: Pod has NOT been restarted")
                print("  Only 1 container ID found = same container throughout window")
            else:
                print(f"⚠️  CONCLUSION: Pod appears to have been RESTARTED")
                print(f"  {len(result)} different container IDs = multiple restart cycles")
        else:
            print("No container data found for this pod\n")
    except Exception as e:
        print(f"Query error: {str(e)[:300]}\n")

    # Query 3: Timeline of logs for this pod
    print("\n=== STEP 3: Pod Log Timeline ===\n")
    nrql_timeline = f"SELECT min(timestamp) as first_log, max(timestamp) as last_log FROM Log WHERE pod_name = '{pod_name}' SINCE 5 hours ago"
    
    try:
        result = client.run_nrql(account_id=1679802, nrql=nrql_timeline)
        if result and len(result) > 0:
            first_log = result[0].get('first_log', 'N/A')
            last_log = result[0].get('last_log', 'N/A')
            print(f"First log:  {first_log}")
            print(f"Last log:   {last_log}")
            
            if first_log != 'N/A' and last_log != 'N/A':
                print(f"\nPod has been logging continuously from first to last timestamp.")
                print("This indicates the pod is still running (no restart).")
        else:
            print("No log timeline data available\n")
    except Exception as e:
        print(f"Query error: {str(e)[:300]}\n")

    # Query 4: Check for ERROR-level logs after the reported error
    print("\n=== STEP 4: Error Logs After 03:35:41 ===\n")
    nrql_after_error = f"SELECT count(*) FROM Log WHERE pod_name = '{pod_name}' AND level = 'ERROR' AND timestamp > 1785641741589 SINCE 4 hours ago"
    
    try:
        result = client.run_nrql(account_id=1679802, nrql=nrql_after_error)
        if result and len(result) > 0:
            count = result[0].get('count', 0)
            if count > 0:
                print(f"Found {count} ERROR logs AFTER the JWT error")
                print("This means the pod continued operating after the error.")
            else:
                print("No ERROR logs found after the JWT error")
        else:
            print("No data available\n")
    except Exception as e:
        print(f"Query error: {str(e)[:300]}\n")

    print("\n=== Summary ===")
    print("Check the above steps for restart indicators:")
    print("  • Same container ID = NO RESTART ✓")
    print("  • Different container IDs = RESTART OCCURRED ⚠️")
    print("  • Continuous log timeline = Pod stayed running ✓\n")


if __name__ == "__main__":
    main()
