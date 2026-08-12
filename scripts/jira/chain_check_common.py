#!/usr/bin/env python3
"""Shared helpers for Jira chain-check style workflows."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from requests.auth import HTTPBasicAuth

from jira.http_common import request_json


def format_issue_summary(issue: Dict[str, Any]) -> Dict[str, Any]:
    fields = issue.get("fields", {})
    labels = fields.get("labels") or []
    parent = fields.get("parent") or {}
    parent_key = parent.get("key") if isinstance(parent, dict) else None

    links = fields.get("issuelinks") or []
    linked_keys = []
    for link in links:
        inward = (link.get("inwardIssue") or {}).get("key")
        outward = (link.get("outwardIssue") or {}).get("key")
        if inward:
            linked_keys.append(inward)
        if outward:
            linked_keys.append(outward)

    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": (fields.get("status") or {}).get("name"),
        "assignee": (fields.get("assignee") or {}).get("displayName"),
        "priority": (fields.get("priority") or {}).get("name"),
        "updated": fields.get("updated"),
        "issue_type": (fields.get("issuetype") or {}).get("name"),
        "labels": labels,
        "parent": parent_key,
        "linked_keys": sorted(set(linked_keys)),
    }


def search_jql_issues(
    host: str,
    auth: HTTPBasicAuth,
    *,
    jql: str,
    limit: int,
    fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    payload = {
        "jql": jql,
        "maxResults": limit,
        "fields": fields
        or [
            "summary",
            "status",
            "assignee",
            "priority",
            "updated",
            "issuetype",
            "labels",
            "parent",
            "issuelinks",
        ],
    }
    data = request_json("POST", host, auth, "/rest/api/3/search/jql", payload=payload)
    return [format_issue_summary(issue) for issue in data.get("issues", [])]


def run_tiered_queries(
    host: str,
    auth: HTTPBasicAuth,
    *,
    tiers: List[Dict[str, str]],
    limit: int,
) -> List[Dict[str, Any]]:
    tier_results: List[Dict[str, Any]] = []
    for tier in tiers:
        name = str(tier.get("name") or "")
        jql = str(tier.get("jql") or "")
        try:
            issues = search_jql_issues(host, auth, jql=jql, limit=limit)
            tier_results.append(
                {
                    "tier": name,
                    "jql": jql,
                    "count": len(issues),
                    "issues": issues,
                }
            )
        except Exception as exc:  # pylint: disable=broad-except
            tier_results.append(
                {
                    "tier": name,
                    "jql": jql,
                    "error": str(exc)[:300],
                }
            )
    return tier_results


def collect_project_candidates(tier_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    ddl_candidates: Dict[str, Dict[str, Any]] = {}
    bet_candidates: Dict[str, Dict[str, Any]] = {}
    for tier in tier_results:
        issues = tier.get("issues")
        if not isinstance(issues, list):
            continue
        for issue in issues:
            key = str(issue.get("key") or "")
            if key.startswith("DDL-"):
                ddl_candidates.setdefault(key, issue)
            elif key.startswith("BET-"):
                bet_candidates.setdefault(key, issue)
    return {
        "ddl": ddl_candidates,
        "bet": bet_candidates,
    }


def evaluate_chain(
    *,
    ddl_candidates: Dict[str, Dict[str, Any]],
    bet_candidates: Dict[str, Dict[str, Any]],
    ddl_parent: str,
    required_label: str,
) -> Dict[str, Any]:
    def _score(issue: Dict[str, Any]) -> int:
        score = 0
        if (issue.get("parent") or "") == ddl_parent:
            score += 4
        if required_label in (issue.get("labels") or []):
            score += 2
        if (issue.get("status") or "").lower() != "done":
            score += 1
        return score

    best_ddl = max(ddl_candidates.values(), key=_score) if ddl_candidates else None
    best_bet = max(bet_candidates.values(), key=_score) if bet_candidates else None

    has_parent = bool(best_ddl and (best_ddl.get("parent") or "") == ddl_parent)
    has_label = bool(best_ddl and required_label in (best_ddl.get("labels") or []))
    bet_linked = bool(
        best_ddl and any(k in bet_candidates for k in (best_ddl.get("linked_keys") or []))
    )
    has_bet = bet_linked or bool(bet_candidates)

    if not best_ddl:
        chain_status = "no_chain"
    elif has_parent and has_label and has_bet:
        chain_status = "complete"
    else:
        chain_status = "partial"

    return {
        "best_ddl": best_ddl,
        "best_bet": best_bet,
        "has_parent": has_parent,
        "has_label": has_label,
        "has_bet": has_bet,
        "chain_status": chain_status,
    }
