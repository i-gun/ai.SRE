#!/usr/bin/env python3
"""Reusable Jira secrets task utilities (chain-check for DDL label/BET)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from requests.auth import HTTPBasicAuth

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from jira.http_common import load_config
from jira.chain_check_common import collect_project_candidates, evaluate_chain, run_tiered_queries


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage Jira secrets tickets with safe defaults")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chain = subparsers.add_parser(
        "chain-check",
        help="Validate DDL label/BET chain for a vault+secret pair (5-tier JQL)",
    )
    chain.add_argument("--vault", required=True, help="Key Vault name, e.g. 'digital-prd-mer-cc-01-k'")
    chain.add_argument("--secret", required=True, help="Secret object name, e.g. 'corp-prod-095-dms-spn-client-secret'")
    chain.add_argument("--urgency", required=True, choices=["moderate", "urgent", "critical"],
                      help="Urgency tier")
    chain.add_argument("--required-label", default="AzureKV", help="Required DDL label (default: AzureKV)")
    chain.add_argument("--limit", type=int, default=5, help="Max results per JQL tier (default: 5)")
    chain.add_argument("--search-days", type=int, default=30,
                       help="Only include Jira issues created within this many days (default: 30)")
    chain.add_argument("--json", action="store_true", help="Output JSON format")

    return parser.parse_args(argv)


def run_chain_check(args: argparse.Namespace, host: str, auth: HTTPBasicAuth) -> Dict[str, Any]:
    """Run 5-tier JQL chain check for vault+secret pair."""
    if args.search_days <= 0:
        raise ValueError("search-days must be greater than zero")
    vault_safe = args.vault.replace('"', '\\"')
    secret_safe = args.secret.replace('"', '\\"')
    recent_clause = f"created >= -{args.search_days}d"

    tiers = [
        {
            "name": "Exact DDL match",
            "jql": (
                f'project = DDL AND {recent_clause} AND summary ~ "{secret_safe}" AND summary ~ "{vault_safe}" '
                f'AND labels = "{args.required_label}" ORDER BY updated DESC'
            ),
        },
        {
            "name": "DDL by secret name",
            "jql": (
                f'project = DDL AND {recent_clause} AND summary ~ "{secret_safe}" '
                f'AND labels = "{args.required_label}" ORDER BY updated DESC'
            ),
        },
        {
            "name": "DDL by vault name",
            "jql": (
                f'project = DDL AND {recent_clause} AND summary ~ "{vault_safe}" '
                f'AND labels = "{args.required_label}" ORDER BY updated DESC'
            ),
        },
        {
            "name": "BET by secret name",
            "jql": (
                f'project = BET AND {recent_clause} AND summary ~ "{secret_safe}" AND summary ~ "{vault_safe}" '
                f'ORDER BY updated DESC'
            ),
        },
        {
            "name": "BET by vault name",
            "jql": (
                f'project = BET AND {recent_clause} AND summary ~ "{vault_safe}" '
                f'ORDER BY updated DESC'
            ),
        },
    ]

    tier_results = run_tiered_queries(host, auth, tiers=tiers, limit=args.limit)
    candidates = collect_project_candidates(tier_results)
    eval_result = evaluate_chain(
        ddl_candidates=candidates["ddl"],
        bet_candidates=candidates["bet"],
        required_label=args.required_label,
    )

    best_ddl = eval_result["best_ddl"]
    best_bet = eval_result["best_bet"]
    ddl_has_label = eval_result["has_label"]
    chain_status = eval_result["chain_status"]
    has_bet = eval_result["has_bet"]

    gaps = []
    if best_bet and not best_ddl:
        gaps.append("No corresponding DDL issue found for the recent BET issue")
    if best_ddl:
        if not ddl_has_label:
            gaps.append(f"DDL missing required label '{args.required_label}'")
        if not has_bet:
            gaps.append("No corresponding BET issue found")

    return {
        "command": "chain-check",
        "vault": args.vault,
        "secret": args.secret,
        "urgency": args.urgency,
        "chain_status": chain_status,
        "best_ddl": best_ddl,
        "best_bet": best_bet,
        "ddl_label_ok": ddl_has_label,
        "gaps": gaps,
        "tier_results": tier_results,
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    try:
        host, auth = load_config()

        if args.command == "chain-check":
            result = run_chain_check(args, host, auth)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                # Human-readable output
                print(f"Chain Check: {args.vault} / {args.secret} ({args.urgency})")
                print(f"Status: {result['chain_status'].upper()}")
                if result.get("best_ddl"):
                    print(f"  DDL: {result['best_ddl']['key']} - {result['best_ddl']['summary']}")
                    print(f"    Label OK: {result['ddl_label_ok']} (required: {args.required_label})")
                if result.get("best_bet"):
                    print(f"  BET: {result['best_bet']['key']} - {result['best_bet']['summary']}")
                if result.get("gaps"):
                    print("  Gaps:")
                    for gap in result["gaps"]:
                        print(f"    - {gap}")
            return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
