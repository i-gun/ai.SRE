#!/usr/bin/env python3
"""Shared create/reuse helpers for ServiceNow incident/problem flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from servicenow_client import ServiceNowClient


def extract_ref(value: Any) -> str:
    if isinstance(value, dict):
        raw = value.get("value") or value.get("display_value") or ""
        return str(raw).strip()
    return str(value or "").strip()


def _state_rank(client: ServiceNowClient, state: Any) -> int:
    # Prefer active/non-resolved records when selecting reuse candidates.
    normalized = extract_ref(state).lower()
    is_closed = normalized == "7" or normalized.startswith("7 -") or "closed" in normalized
    return 0 if client.is_resolved_state(state) or is_closed else 1


def _sort_key(
    client: ServiceNowClient,
    item: Dict[str, Any],
    match_rank: int = 0,
) -> tuple[int, int, str]:
    return (
        match_rank,
        _state_rank(client, item.get("state")),
        str(item.get("sys_updated_on") or ""),
    )


def _recent_query_clause(max_age_days: Optional[int]) -> List[str]:
    if max_age_days is None:
        return []
    if max_age_days <= 0:
        raise ValueError("max_age_days must be greater than zero")
    return [f"sys_created_on>=javascript:gs.daysAgoStart({max_age_days})"]


def _is_recent_record(record: Dict[str, Any], max_age_days: Optional[int]) -> bool:
    if max_age_days is None:
        return True
    raw_created = extract_ref(record.get("sys_created_on"))
    if not raw_created:
        return False
    try:
        created_at = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
    except ValueError:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at >= datetime.now(timezone.utc) - timedelta(days=max_age_days)


def _match_rank(description: str, exact_short_description: str, fallback_terms: List[str]) -> int:
    if description == exact_short_description:
        return 3
    for index, term in enumerate(fallback_terms):
        if term and term.lower() in description.lower():
            return max(1, len(fallback_terms) - index)
    return 0


def query_problems(
    client: ServiceNowClient,
    *,
    query_parts: List[str],
    limit: int,
    max_age_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    scoped_parts = [
        "assignment_group.nameIN" + ",".join(client.config.assignment_groups),
    ]
    scoped_parts.extend(_recent_query_clause(max_age_days))
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
    max_age_days: Optional[int] = None,
) -> Dict[str, Any]:
    recent_clause = _recent_query_clause(max_age_days)

    exact = client.query_incidents(
        query_parts=recent_clause + [f"short_description={exact_short_description}"],
        limit=limit,
    )

    fallback_matches: List[Dict[str, Any]] = []
    for term in fallback_terms:
        term_clean = str(term or "").strip()
        if not term_clean:
            continue
        fallback_matches.extend(
            client.query_incidents(
                query_parts=recent_clause + [f"short_descriptionLIKE{term_clean}"],
                limit=limit,
            )
        )

    all_candidates: Dict[str, tuple[Dict[str, Any], int]] = {}
    for row in exact + fallback_matches:
        sys_id = extract_ref(row.get("sys_id"))
        if not sys_id:
            continue
        description = str(row.get("short_description") or "")
        match_rank = _match_rank(description, exact_short_description, fallback_terms)
        all_candidates[sys_id] = (row, match_rank)

    best: Optional[Dict[str, Any]] = None
    if all_candidates:
        active_candidates = [
            candidate
            for candidate in all_candidates.values()
            if _state_rank(client, candidate[0].get("state")) > 0
        ]
        if active_candidates:
            best = sorted(
                active_candidates,
                key=lambda candidate: _sort_key(client, candidate[0], candidate[1]),
                reverse=True,
            )[0][0]

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
    max_age_days: Optional[int] = None,
) -> Dict[str, Any]:
    linked: List[Dict[str, Any]] = []
    if linked_problem_number:
        try:
            linked_candidate = client._find_problem(problem_number=linked_problem_number)  # pylint: disable=protected-access
            if _is_recent_record(linked_candidate, max_age_days):
                linked = [linked_candidate]
        except Exception:  # pylint: disable=broad-except
            linked = []

    exact = query_problems(
        client,
        query_parts=[f"short_description={exact_short_description}"],
        limit=limit,
        max_age_days=max_age_days,
    )

    fallback_matches: List[Dict[str, Any]] = []
    for term in fallback_terms:
        term_clean = str(term or "").strip()
        if not term_clean:
            continue
        fallback_matches.extend(
            query_problems(
                client,
                query_parts=[f"short_descriptionLIKE{term_clean}"],
                limit=limit,
                max_age_days=max_age_days,
            )
        )

    all_candidates: Dict[str, tuple[Dict[str, Any], int]] = {}
    for row in linked + exact + fallback_matches:
        sys_id = extract_ref(row.get("sys_id"))
        if not sys_id:
            continue
        description = str(row.get("short_description") or "")
        match_rank = _match_rank(description, exact_short_description, fallback_terms)
        all_candidates[sys_id] = (row, match_rank)

    best: Optional[Dict[str, Any]] = None
    if all_candidates:
        ranked_candidates = sorted(
            all_candidates.values(),
            key=lambda candidate: _sort_key(client, candidate[0], candidate[1]),
            reverse=True,
        )
        if ranked_candidates[0][1] >= 2:
            best = ranked_candidates[0][0]

    return {
        "linked_matches": linked,
        "exact_matches": exact,
        "fallback_matches": fallback_matches,
        "best": best,
    }
