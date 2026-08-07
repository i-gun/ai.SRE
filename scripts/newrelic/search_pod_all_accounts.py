#!/usr/bin/env python3
"""Search all configured accounts for the pod."""

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

    docker_id = "bb539219c964c0e15d966e3b24698095ba7b16635ac1ccbd08b204b8e86ef30d"
    pod_id = "ee0ace63-e5ce-46d8-90ae-1b919a50624f"

    print("\n=== Cross-Account Pod Search ===\n")
    print(f"Looking for pod_id: {pod_id}")
    print(f"Looking for docker_id: {docker_id[:16]}...\n")

    # Search all accounts
    for account_id in nr_config.account_ids:
        print(f"\n--- Account {account_id} ---")
        
        # Query by pod_id
        nrql_pod_id = f"SELECT count(*) FROM Log WHERE pod_id = '{pod_id}' SINCE 5 hours ago"
        
        try:
            result = client.run_nrql(account_id=account_id, nrql=nrql_pod_id)
            if result and len(result) > 0 and result[0].get('count', 0) > 0:
                print(f"✓ Found {result[0].get('count')} logs by pod_id in account {account_id}")
        except Exception as e:
            pass
        
        # Query by docker_id
        nrql_docker = f"SELECT count(*) FROM Log WHERE docker_id = '{docker_id}' SINCE 5 hours ago"
        
        try:
            result = client.run_nrql(account_id=account_id, nrql=nrql_docker)
            if result and len(result) > 0 and result[0].get('count', 0) > 0:
                print(f"✓ Found {result[0].get('count')} logs by docker_id in account {account_id}")
        except Exception as e:
            pass


if __name__ == "__main__":
    main()
