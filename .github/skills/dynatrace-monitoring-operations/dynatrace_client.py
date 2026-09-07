"""Dynatrace Grail/DQL client for log search, trend analysis, dependency traversal, and RCA."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from dynatrace_env import DynatraceAuthConfig, load_dynatrace_auth_config_from_env


class DynatraceConfigError(Exception):
    """Raised when Dynatrace configuration is invalid."""


class DynatraceValidationError(Exception):
    """Raised when operation inputs fail validation checks."""


class DynatraceAPIError(Exception):
    """Raised when Dynatrace API calls fail."""


# Patterns used to normalize repetitive log message variants for fallback RCA.
_NORMALIZE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<ip>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r'"[^"]{32,}"'), '"<value>"'),
]


def _dql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class DynatraceClient:
    """Client for Dynatrace Grail/DQL logs, Smartscape topology, and RCA."""

    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_POLL_INTERVAL_SECONDS = 1.0

    def __init__(self, config: DynatraceAuthConfig) -> None:
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Api-Token {config.api_token}",
            }
        )

    @classmethod
    def from_env(cls) -> "DynatraceClient":
        return cls(load_dynatrace_auth_config_from_env())

    # ------------------------------------------------------------------
    # Core Grail DQL transport (async execute + poll)
    # ------------------------------------------------------------------

    def execute_dql(self, *, query: str, timeout_s: int = DEFAULT_TIMEOUT_SECONDS) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            raise DynatraceValidationError("DQL query must not be empty.")

        execute_url = f"{self.config.environment_url}/platform/storage/query/v1/query:execute"
        try:
            resp = self._session.post(execute_url, json={"query": query}, timeout=timeout_s)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise DynatraceAPIError(f"Dynatrace DQL execute failed: {exc}") from exc

        payload = resp.json()
        state = payload.get("state")

        if state == "SUCCEEDED":
            return payload.get("result", {}).get("records", [])

        request_token = payload.get("requestToken")
        if not request_token:
            raise DynatraceAPIError(f"Dynatrace DQL execute returned no requestToken: {payload}")

        poll_url = f"{self.config.environment_url}/platform/storage/query/v1/query:poll"
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                poll_resp = self._session.post(
                    poll_url, json={"requestToken": request_token}, timeout=timeout_s
                )
                poll_resp.raise_for_status()
            except requests.RequestException as exc:
                raise DynatraceAPIError(f"Dynatrace DQL poll failed: {exc}") from exc

            poll_payload = poll_resp.json()
            poll_state = poll_payload.get("state")
            if poll_state == "SUCCEEDED":
                return poll_payload.get("result", {}).get("records", [])
            if poll_state not in ("RUNNING", "NOT_STARTED"):
                raise DynatraceAPIError(f"Dynatrace DQL query failed with state '{poll_state}': {poll_payload}")

            time.sleep(self.DEFAULT_POLL_INTERVAL_SECONDS)

        raise DynatraceAPIError(f"Dynatrace DQL query did not complete within {timeout_s}s.")

    # ------------------------------------------------------------------
    # Log search
    # ------------------------------------------------------------------

    def search_logs(
        self,
        *,
        message_contains: Optional[str] = None,
        severity: Optional[str] = None,
        service: Optional[str] = None,
        since: str = "-1h",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if limit <= 0:
            raise DynatraceValidationError("limit must be greater than zero.")

        filters = [f"timestamp >= now() - {since}" if not since.startswith("-") else f"timestamp >= {since}"]
        if message_contains:
            filters.append(f'matchesPhrase(content, "{_dql_escape(message_contains)}")')
        if severity:
            filters.append(f'loglevel == "{_dql_escape(severity.upper())}"')
        if service:
            filters.append(f'matchesPhrase(dt.entity.service, "{_dql_escape(service)}")')

        query = (
            "fetch logs | filter " + " and ".join(filters) +
            f" | sort timestamp desc | limit {limit}"
        )
        return self.execute_dql(query=query)

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------

    def analyze_log_trends(
        self,
        *,
        message_contains: Optional[str] = None,
        service: Optional[str] = None,
        since: str = "-1h",
        bucket: str = "10m",
        facet: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        filters = [f"timestamp >= now() - {since}" if not since.startswith("-") else f"timestamp >= {since}"]
        if message_contains:
            filters.append(f'matchesPhrase(content, "{_dql_escape(message_contains)}")')
        if service:
            filters.append(f'matchesPhrase(dt.entity.service, "{_dql_escape(service)}")')

        by_clause = f"bin(timestamp, {bucket})" + (f", {facet}" if facet else "")
        query = (
            "fetch logs | filter " + " and ".join(filters) +
            f" | summarize count(), by:{{{by_clause}}} | sort timestamp asc"
        )
        return self.execute_dql(query=query)

    # ------------------------------------------------------------------
    # Smartscape dependency traversal
    # ------------------------------------------------------------------

    def trace_service_dependencies(self, *, service: str, since: str = "-1h") -> Dict[str, Any]:
        if not service or not service.strip():
            raise DynatraceValidationError("service must not be empty.")

        entities_url = f"{self.config.environment_url}/api/v2/entities"
        params = {
            "entitySelector": f'type(SERVICE),entityName("{service}")',
            "fields": "fromRelationships,toRelationships",
        }
        try:
            resp = self._session.get(entities_url, params=params, timeout=self.DEFAULT_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise DynatraceAPIError(f"Dynatrace entity lookup failed: {exc}") from exc

        entities = resp.json().get("entities", [])
        if not entities:
            return {
                "service": service,
                "upstream_services": [],
                "downstream_services": [],
                "dependency_graph": {"nodes": [], "edges": []},
                "warning": f"No Smartscape entity found for service '{service}'. "
                           "It may not be monitored or the name may not match exactly.",
            }

        entity = entities[0]
        entity_id = entity.get("entityId")
        upstream = [r for rels in entity.get("fromRelationships", {}).values() for r in rels]
        downstream = [r for rels in entity.get("toRelationships", {}).values() for r in rels]

        nodes = [{"id": entity_id, "name": service}]
        edges = []
        for rel_id in upstream:
            nodes.append({"id": rel_id, "name": rel_id})
            edges.append({"from": rel_id, "to": entity_id})
        for rel_id in downstream:
            nodes.append({"id": rel_id, "name": rel_id})
            edges.append({"from": entity_id, "to": rel_id})

        return {
            "service": service,
            "upstream_services": upstream,
            "downstream_services": downstream,
            "dependency_graph": {"nodes": nodes, "edges": edges},
        }

    # ------------------------------------------------------------------
    # Root cause analysis (Davis-evidence-first, log-pattern fallback)
    # ------------------------------------------------------------------

    def root_cause_analysis(
        self,
        *,
        problem_id: Optional[str] = None,
        service: Optional[str] = None,
        since: str = "-1h",
    ) -> Dict[str, Any]:
        if problem_id:
            problem_url = f"{self.config.environment_url}/api/v2/problems/{problem_id}"
            try:
                resp = self._session.get(problem_url, timeout=self.DEFAULT_TIMEOUT_SECONDS)
                resp.raise_for_status()
                problem = resp.json()
            except requests.RequestException as exc:
                raise DynatraceAPIError(f"Dynatrace problem detail fetch failed: {exc}") from exc

            evidence = problem.get("evidenceDetails", {}).get("details", [])
            root_cause_entity = problem.get("rootCauseEntity")
            if root_cause_entity or evidence:
                return {
                    "evidence_source": "davis_ai",
                    "problem_id": problem_id,
                    "root_cause": root_cause_entity,
                    "impact_analysis": problem.get("impactAnalysis"),
                    "evidence": evidence,
                    "recommendation": "Review Davis AI root cause entity and evidence details above.",
                    "escalation_points": [],
                }

        if not service:
            raise DynatraceValidationError(
                "service must be provided when Davis AI evidence is unavailable or no problem_id was given."
            )

        errors = self.search_logs(severity="ERROR", service=service, since=since, limit=200)
        patterns: Dict[str, int] = {}
        for rec in errors:
            content = str(rec.get("content", ""))
            normalized = content
            for pattern, repl in _NORMALIZE_PATTERNS:
                normalized = pattern.sub(repl, normalized)
            patterns[normalized] = patterns.get(normalized, 0) + 1

        ranked = sorted(patterns.items(), key=lambda kv: kv[1], reverse=True)
        return {
            "evidence_source": "log_pattern_fallback",
            "service": service,
            "root_cause": ranked[0][0] if ranked else None,
            "contributing_factors": [{"pattern": p, "count": c} for p, c in ranked[:10]],
            "recommendation": "Davis AI evidence was unavailable; findings are based on log frequency only. "
                               "Treat confidence as low until corroborated.",
            "escalation_points": [],
        }
