#!/usr/bin/env python3
"""Shared create/reuse helpers for ServiceNow incident/problem flows."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from servicenow_client import ServiceNowClient


def extract_ref(value: Any) -> str:
    if isinstance(value, dict):
        raw = value.get("value") or value.get("display_value") or ""
        return str(raw).strip()
    return str(value or "").strip()


def _state_rank(client: ServiceNowClient, state: Any) -> int:
    # Prefer active/non-resolved records when selecting reuse candidates.
    return 1 if client.is_resolved_state(state) else 0


def _sort_key(client: ServiceNowClient, item: Dict[str, Any]) -> tuple[int, str]:
    return (
        _state_rank(client, item.get("state")),
        str(item.get("sys_updated_on") or ""),
    )


def query_problems(
    client: ServiceNowClient,
    *,
    query_parts: List[str],
    limit: int,
) -> List[Dict[str, Any]]:
    scoped_parts = [
        "assignment_group.nameIN" + ",".join(client.config.assignment_groups),
    ]
    scoped_parts.extend(part for part in query_parts if str(part or "").strip())
    result = client._request(  # pylint: disable=protected-access
        "GET",
        client.PROBLEM_TABLE_PATH,
        params={
            "sysparm_query": "^".join(scoped_parts),
            "sysparm_limit": limit,
            "sysparm_fields": ",".join(client.PROBLEM_FIELDS + ["state"]),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_order_by_desc": "sys_updated_on",
        },
    )
    return result.get("result", [])


def find_incident_candidates(
    client: ServiceNowClient,
    *,
    exact_short_description: str,
    fallback_terms: List[str],
    limit: int,
) -> Dict[str, Any]:
    exact = client.query_incidents(query_parts=[f"short_description={exact_short_description}"], limit=limit)

    fallback_matches: List[Dict[str, Any]] = []
    for term in fallback_terms:
        term_clean = str(term or "").strip()
        if not term_clean:
            continue
        fallback_matches.extend(
            client.query_incidents(query_parts=[f"short_descriptionLIKE{term_clean}"], limit=limit)
        )

    all_candidates: Dict[str, Dict[str, Any]] = {}
    for row in exact + fallback_matches:
        sys_id = extract_ref(row.get("sys_id"))
        if not sys_id:
            continue
        all_candidates[sys_id] = row

    best: Optional[Dict[str, Any]] = None
    if all_candidates:
        best = sorted(all_candidates.values(), key=lambda item: _sort_key(client, item))[0]

    return {
        "exact_matches": exact,
        "fallback_matches": fallback_matches,
        "best": best,
    }


def find_problem_candidates(
    client: ServiceNowClient,
    *,
    exact_short_description: str,
    fallback_terms: List[str],
    linked_problem_number: str,
    limit: int,
) -> Dict[str, Any]:
    linked: List[Dict[str, Any]] = []
    if linked_problem_number:
        try:
            linked = [client._find_problem(problem_number=linked_problem_number)]  # pylint: disable=protected-access
        except Exception:  # pylint: disable=broad-except
            linked = []

    exact = query_problems(client, query_parts=[f"short_description={exact_short_description}"], limit=limit)

    fallback_matches: List[Dict[str, Any]] = []
    for term in fallback_terms:
        term_clean = str(term or "").strip()
        if not term_clean:
            continue
        fallback_matches.extend(
            query_problems(client, query_parts=[f"short_descriptionLIKE{term_clean}"], limit=limit)
        )

    all_candidates: Dict[str, Dict[str, Any]] = {}
    for row in linked + exact + fallback_matches:
        sys_id = extract_ref(row.get("sys_id"))
        if not sys_id:
            continue
        all_candidates[sys_id] = row

    best: Optional[Dict[str, Any]] = None
    if all_candidates:
        best = sorted(all_candidates.values(), key=lambda item: _sort_key(client, item))[0]

    return {
        "linked_matches": linked,
        "exact_matches": exact,
        "fallback_matches": fallback_matches,
        "best": best,
    }
