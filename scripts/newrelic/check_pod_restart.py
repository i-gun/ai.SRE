#!/usr/bin/env python3
"""Check if the pod was restarted between 03:35:41 UTC and now."""

import sys
import json
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

    target_pod = "api-6974fc79bf-hwjvc"
    error_time = "2026-08-02T03:35:41Z"

    print(f"\n=== Pod Restart Analysis ===")
    print(f"Target Pod: {target_pod}")
    print(f"Error Time: {error_time}")
    print(f"Analysis Window: 03:35:41 UTC to now (past 4 hours)\n")

    # Query 1: Container restart events
    print("=== STEP 1: Container Restart Events ===\n")
    nrql_restarts = f"SELECT count(*) FROM Log WHERE pod_name = '{target_pod}' AND (message LIKE '%restart%' OR message LIKE '%exit code%' OR message LIKE '%restarted%') SINCE 4 hours ago LIMIT 100"
    
    try:
        restart_events = client.run_nrql(account_id=1679802, nrql=nrql_restarts)
        if restart_events:
            print(f"Found potential restart events:")
            for row in restart_events:
                print(f"  Count: {row.get('count', 0)}")
        else:
            print("No restart event logs found.\n")
    except Exception as e:
        print(f"Query error: {str(e)[:300]}\n")

    # Query 2: Pod uptime - check when pod first appeared in logs
    print("\n=== STEP 2: Pod Activity Timeline ===\n")
    nrql_timeline = f"SELECT count(*), min(timestamp) as earliest_log, max(timestamp) as latest_log FROM Log WHERE pod_name = '{target_pod}' SINCE 5 hours ago LIMIT 10"
    
    try:
        timeline = client.run_nrql(account_id=1679802, nrql=nrql_timeline)
        if timeline:
            print("Pod activity timeline:")
            for row in timeline:
                earliest = row.get('earliest_log', 'N/A')
                latest = row.get('latest_log', 'N/A')
                count = row.get('count', 0)
                print(f"  Total logs: {count}")
                print(f"  Earliest log: {earliest}")
                print(f"  Latest log: {latest}")
        else:
            print("No logs found for this pod in past 5 hours.\n")
    except Exception as e:
        print(f"Query error: {str(e)[:300]}\n")

    # Query 3: Container lifecycle logs (docker_id changes indicate restart)
    print("\n=== STEP 3: Container ID Changes (Restart Indicator) ===\n")
    nrql_container_ids = f"SELECT count(*) FROM Log WHERE pod_name = '{target_pod}' SINCE 5 hours ago FACET docker_id LIMIT 20"
    
    try:
        container_ids = client.run_nrql(account_id=1679802, nrql=nrql_container_ids)
        if container_ids and len(container_ids) > 0:
            print(f"Found {len(container_ids)} unique container ID(s) for this pod:")
            print("(Multiple container IDs = pod restarts)")
            for row in container_ids:
                docker_id = row.get('facet', 'N/A')
                count = row.get('count', 0)
                print(f"  • Container: {docker_id[:16]}... | Logs: {count}")
            
            if len(container_ids) > 1:
                print(f"\n⚠️  RESTART DETECTED: {len(container_ids)} different container IDs found!")
                print("   Pod has been restarted at least once in the analysis window.")
            else:
                print(f"\n✓ No restarts: Only 1 container ID throughout the window.")
        else:
            print("No container ID data found.\n")
    except Exception as e:
        print(f"Query error: {str(e)[:300]}\n")

    # Query 4: Logs immediately before and after error time
    print("\n=== STEP 4: Logs Around Error Time (±15 min) ===\n")
    nrql_around_error = f"SELECT count(*), level FROM Log WHERE pod_name = '{target_pod}' AND timestamp >= 1785641141000 AND timestamp <= 1785642341000 FACET level"
    
    try:
        around_error = client.run_nrql(account_id=1679802, nrql=nrql_around_error)
        if around_error:
            print("Log distribution around error time (03:20 - 03:50 UTC):")
            for row in around_error:
                level = row.get('facet', 'N/A')
                count = row.get('count', 0)
                print(f"  • Level {level}: {count} logs")
        else:
            print("No logs found in this time window.\n")
    except Exception as e:
        print(f"Query error: {str(e)[:300]}\n")

    # Query 5: Check for duplicate or anomalous pod_id
    print("\n=== STEP 5: Pod ID Analysis ===\n")
    nrql_pod_ids = f"SELECT count(*) FROM Log WHERE pod_name = '{target_pod}' SINCE 5 hours ago FACET pod_id LIMIT 20"
    
    try:
        pod_ids = client.run_nrql(account_id=1679802, nrql=nrql_pod_ids)
        if pod_ids and len(pod_ids) > 0:
            print(f"Found {len(pod_ids)} unique pod ID(s):")
            for row in pod_ids:
                pod_id = row.get('facet', 'N/A')
                count = row.get('count', 0)
                print(f"  • Pod ID: {pod_id[:20]}... | Logs: {count}")
            
            if len(pod_ids) > 1:
                print(f"\n⚠️  WARNING: {len(pod_ids)} different pod IDs = pod was recreated!")
            else:
                print(f"\n✓ Consistent pod ID throughout window.")
        else:
            print("No pod ID data found.\n")
    except Exception as e:
        print(f"Query error: {str(e)[:300]}\n")

    print("\n=== Summary ===")
    print("✓ Analysis complete. Review findings above.")


if __name__ == "__main__":
    main()
