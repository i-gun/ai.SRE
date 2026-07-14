"""New Relic NerdGraph/NRQL client for log search, trend analysis, dependency traversal, and RCA."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests


class NewRelicConfigError(Exception):
    """Raised when New Relic configuration is invalid."""


class NewRelicValidationError(Exception):
    """Raised when operation inputs fail validation checks."""


class NewRelicAPIError(Exception):
    """Raised when New Relic API calls fail."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class NewRelicConfig:
    api_key: str
    account_ids: List[int] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "NewRelicConfig":
        api_key = os.getenv("NEWRELIC_API_KEY", "").strip()
        account_ids_raw = os.getenv("NEWRELIC_ACCOUNT_IDS", "").strip()

        missing = [
            name
            for name, value in [
                ("NEWRELIC_API_KEY", api_key),
                ("NEWRELIC_ACCOUNT_IDS", account_ids_raw),
            ]
            if not value
        ]

        if missing:
            raise NewRelicConfigError(
                "Missing required New Relic environment variables: " + ", ".join(missing)
            )

        account_ids: List[int] = []
        for raw in account_ids_raw.split(","):
            token = raw.strip()
            if not token:
                continue
            if not token.lstrip("-").isdigit() or int(token) <= 0:
                raise NewRelicConfigError(
                    f"NEWRELIC_ACCOUNT_IDS contains invalid account ID: '{token}'. "
                    "Each ID must be a positive integer."
                )
            account_ids.append(int(token))

        if not account_ids:
            raise NewRelicConfigError(
                "NEWRELIC_ACCOUNT_IDS must contain at least one positive integer account ID."
            )

        return cls(api_key=api_key, account_ids=account_ids)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class NewRelicClient:
    """Client for New Relic log search, trend analysis, dependency traversal, and RCA."""

    NERDGRAPH_URL = "https://api.newrelic.com/graphql"
    DEFAULT_TIMEOUT_SECONDS = 30

    # Log severity normalization to internal priority tier.
    _SEVERITY_MAP: Dict[str, str] = {
        "fatal": "CRITICAL",
        "critical": "CRITICAL",
        "error": "HIGH",
        "err": "HIGH",
        "warn": "MEDIUM",
        "warning": "MEDIUM",
        "info": "LOW",
        "debug": "LOW",
        "trace": "LOW",
    }

    # Patterns used to normalize repetitive error message variants.
    _NORMALIZE_PATTERNS: List[Tuple[re.Pattern, str]] = [
        (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
        (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<ip>"),
        (re.compile(r"\b\d+\b"), "<n>"),
        (re.compile(r'"[^"]{32,}"'), '"<value>"'),
    ]

    def __init__(self, config: NewRelicConfig) -> None:
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "API-Key": config.api_key,
            }
        )

    @classmethod
    def from_env(cls) -> "NewRelicClient":
        return cls(NewRelicConfig.from_env())

    # ------------------------------------------------------------------
    # Core NerdGraph transport
    # ------------------------------------------------------------------

    def _nerdgraph(self, graphql_query: str) -> Dict[str, Any]:
        try:
            response = self._session.post(
                self.NERDGRAPH_URL,
                json={"query": graphql_query},
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise NewRelicAPIError(f"New Relic request failed: {exc}") from exc

        if response.status_code >= 400:
            raise NewRelicAPIError(
                f"New Relic API error ({response.status_code}): {response.text[:300]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise NewRelicAPIError("New Relic returned non-JSON response") from exc

        errors = payload.get("errors")
        if errors:
            messages = "; ".join(e.get("message", str(e)) for e in errors)
            raise NewRelicAPIError(f"NerdGraph errors: {messages}")

        return payload

    # ------------------------------------------------------------------
    # NRQL execution
    # ------------------------------------------------------------------

    def run_nrql(self, *, account_id: int, nrql: str) -> List[Dict[str, Any]]:
        """Execute a single NRQL query against one account."""
        if not nrql.strip():
            raise NewRelicValidationError("NRQL query must not be empty.")
        gql = self._build_multi_account_nerdgraph({account_id: nrql})
        data = self._nerdgraph(gql).get("data", {}).get("actor", {})
        return data.get(f"a{account_id}", {}).get("nrql", {}).get("results", [])

    def run_nrql_across_accounts(
        self,
        *,
        nrql: str,
        account_ids: Optional[List[int]] = None,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Execute the same NRQL query across multiple accounts in one request."""
        if not nrql.strip():
            raise NewRelicValidationError("NRQL query must not be empty.")
        ids = self._resolve_account_ids(self.config.account_ids, account_ids)
        gql = self._build_multi_account_nerdgraph({aid: nrql for aid in ids})
        actor = self._nerdgraph(gql).get("data", {}).get("actor", {})
        return {
            aid: actor.get(f"a{aid}", {}).get("nrql", {}).get("results", [])
            for aid in ids
        }

    # ------------------------------------------------------------------
    # Log search
    # ------------------------------------------------------------------

    def search_logs(
        self,
        *,
        message_contains: str = "",
        severity: Optional[str] = None,
        service: Optional[str] = None,
        since: str = "1 hour ago",
        limit: int = 100,
        account_ids: Optional[List[int]] = None,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Search Log events across one or more accounts."""
        if limit <= 0:
            raise NewRelicValidationError("Limit must be greater than zero.")
        nrql = self._build_log_search_nrql(
            message_contains=message_contains,
            severity=severity,
            service=service,
            since=since,
            limit=limit,
        )
        return self.run_nrql_across_accounts(nrql=nrql, account_ids=account_ids)

    # ------------------------------------------------------------------
    # Alert search
    # ------------------------------------------------------------------

    def search_alerts(
        self,
        *,
        policy_name_contains: str = "",
        priority: Optional[str] = None,
        since: str = "1 hour ago",
        exclude_muted: bool = True,
        limit: int = 100,
        account_ids: Optional[List[int]] = None,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Search NrAiIssue alert events across one or more accounts.

        By default (``exclude_muted=True``) fully-muted issues are excluded from
        results so that only actionable alerts are returned.  Pass
        ``exclude_muted=False`` to include muted issues.
        """
        if limit <= 0:
            raise NewRelicValidationError("Limit must be greater than zero.")
        nrql = self._build_alert_search_nrql(
            policy_name_contains=policy_name_contains,
            priority=priority,
            since=since,
            exclude_muted=exclude_muted,
            limit=limit,
        )
        return self.run_nrql_across_accounts(nrql=nrql, account_ids=account_ids)

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------

    def analyze_log_trends(
        self,
        *,
        message_contains: str = "",
        service: Optional[str] = None,
        since: str = "24 hours ago",
        timeseries: str = "10 minutes",
        facet: Optional[str] = None,
        account_ids: Optional[List[int]] = None,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Return time-series log counts, optionally faceted, across accounts."""
        nrql = self._build_trend_nrql(
            message_contains=message_contains,
            service=service,
            since=since,
            timeseries=timeseries,
            facet=facet,
        )
        return self.run_nrql_across_accounts(nrql=nrql, account_ids=account_ids)

    # ------------------------------------------------------------------
    # Dependency traversal
    # ------------------------------------------------------------------

    def trace_service_dependencies(
        self,
        *,
        service: str,
        since: str = "1 hour ago",
        account_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Discover upstream callers and downstream dependencies of a service
        by querying Span data across all configured accounts.
        """
        if not service.strip():
            raise NewRelicValidationError("Service name must not be empty.")

        downstream_nrql = self._build_dependency_nrql(service=service, since=since)
        upstream_nrql = self._build_upstream_nrql(service=service, since=since)

        downstream_results = self.run_nrql_across_accounts(nrql=downstream_nrql, account_ids=account_ids)
        upstream_results = self.run_nrql_across_accounts(nrql=upstream_nrql, account_ids=account_ids)

        downstream: List[str] = []
        upstream: List[str] = []
        databases: List[str] = []

        for results in downstream_results.values():
            for row in results:
                for key in ("service.name", "serviceName", "db.system", "dbSystem"):
                    val = row.get(key)
                    if val and isinstance(val, str) and val != service:
                        if key in ("db.system", "dbSystem"):
                            if val not in databases:
                                databases.append(val)
                        elif val not in downstream:
                            downstream.append(val)

        for results in upstream_results.values():
            for row in results:
                for key in ("service.name", "serviceName", "entity.name", "entityName"):
                    val = row.get(key)
                    if val and isinstance(val, str) and val != service:
                        if val not in upstream:
                            upstream.append(val)

        all_nodes = list({service} | set(upstream) | set(downstream))
        edges = (
            [{"from": u, "to": service} for u in upstream]
            + [{"from": service, "to": d} for d in downstream]
        )

        return {
            "service": service,
            "since": since,
            "accounts_queried": self._resolve_account_ids(self.config.account_ids, account_ids),
            "upstream_services": sorted(upstream),
            "downstream_services": sorted(downstream),
            "databases": sorted(databases),
            "dependency_graph": {
                "nodes": sorted(all_nodes),
                "edges": edges,
            },
        }

    # ------------------------------------------------------------------
    # Root cause analysis
    # ------------------------------------------------------------------

    def root_cause_analysis(
        self,
        *,
        service: str,
        since: str = "1 hour ago",
        account_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze log errors for a service, score root-cause candidates,
        and return findings with recommendations and escalation points.
        """
        if not service.strip():
            raise NewRelicValidationError("Service name must not be empty.")

        ids = self._resolve_account_ids(self.config.account_ids, account_ids)

        # 1. Collect errors in the current window.
        error_nrql = self._build_error_nrql(service=service, since=since, limit=500)
        error_results_by_account = self.run_nrql_across_accounts(nrql=error_nrql, account_ids=ids)

        all_errors: List[Dict[str, Any]] = []
        for results in error_results_by_account.values():
            all_errors.extend(results)

        # 2. Collect errors in the baseline window (previous equal period).
        baseline_nrql = self._build_error_nrql(
            service=service,
            since=self._previous_window(since),
            limit=500,
        )
        baseline_by_account = self.run_nrql_across_accounts(nrql=baseline_nrql, account_ids=ids)
        baseline_errors: List[Dict[str, Any]] = []
        for results in baseline_by_account.values():
            baseline_errors.extend(results)

        # 3. Extract and score error patterns.
        patterns = self._extract_error_patterns(all_errors)
        baseline_counts = self._extract_baseline_counts(baseline_errors)
        dep_errors = self._collect_dependency_errors(
            service=service, since=since, account_ids=ids
        )
        candidates = self._score_rca_candidates(patterns, baseline_counts, dep_errors)

        # 4. Build severity breakdown.
        severity_breakdown: Dict[str, int] = {}
        for err in all_errors:
            level = str(err.get("level") or err.get("severity") or "UNKNOWN").upper()
            severity_breakdown[level] = severity_breakdown.get(level, 0) + 1

        top_messages = [
            {"message": p["template"], "count": p["count"]}
            for p in sorted(patterns, key=lambda x: x["count"], reverse=True)[:5]
        ]

        root_cause_summary = candidates[0]["description"] if candidates else "No clear root cause identified."
        recommendation = self._generate_recommendation(candidates)
        escalation_points = self._generate_escalation_points(candidates, dep_errors)

        return {
            "service": service,
            "since": since,
            "accounts_queried": ids,
            "error_summary": {
                "total_errors": len(all_errors),
                "error_rate_per_minute": self._estimate_rate_per_minute(len(all_errors), since),
                "top_error_messages": top_messages,
                "severity_breakdown": severity_breakdown,
            },
            "dependency_issues": dep_errors,
            "rca_candidates": candidates,
            "root_cause": root_cause_summary,
            "recommendation": recommendation,
            "escalation_points": escalation_points,
        }

    # ------------------------------------------------------------------
    # NRQL builders (static — fully testable without network)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_log_search_nrql(
        *,
        message_contains: str,
        severity: Optional[str],
        service: Optional[str],
        since: str,
        limit: int,
    ) -> str:
        clauses: List[str] = []
        if message_contains:
            escaped = message_contains.replace("'", "\\'")
            clauses.append(f"message LIKE '%{escaped}%'")
        if severity:
            clauses.append(f"level = '{severity.upper()}'")
        if service:
            escaped_svc = service.replace("'", "\\'")
            clauses.append(
                f"(service.name = '{escaped_svc}' OR `entity.name` = '{escaped_svc}')"
            )
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return (
            f"SELECT timestamp, message, level, service.name, hostname, error.message, traceId "
            f"FROM Log{where} SINCE {since} LIMIT {limit}"
        )

    @staticmethod
    def _build_alert_search_nrql(
        *,
        policy_name_contains: str,
        priority: Optional[str],
        since: str,
        exclude_muted: bool,
        limit: int,
    ) -> str:
        """Build a NRQL query targeting NrAiIssue alert events.

        When ``exclude_muted`` is ``True`` (the default), the clause
        ``muted != 'fullyMuted'`` is prepended so that suppressed issues are
        not included in results.
        """
        clauses: List[str] = []
        if exclude_muted:
            clauses.append("muted != 'fullyMuted'")
        if policy_name_contains:
            escaped = policy_name_contains.replace("'", "\\'")
            clauses.append(f"policyNames LIKE '%{escaped}%'")
        if priority:
            clauses.append(f"priority = '{priority.upper()}'")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return (
            f"SELECT issueId, title, policyNames, conditionNames, priority, event, "
            f"issueLink, muted, activateTime, lastModifiedTime "
            f"FROM NrAiIssue{where} SINCE {since} "
            f"ORDER BY lastModifiedTime DESC LIMIT {limit}"
        )

    @staticmethod
    def _build_trend_nrql(
        *,
        message_contains: str,
        service: Optional[str],
        since: str,
        timeseries: str,
        facet: Optional[str],
    ) -> str:
        clauses: List[str] = []
        if message_contains:
            escaped = message_contains.replace("'", "\\'")
            clauses.append(f"message LIKE '%{escaped}%'")
        if service:
            escaped_svc = service.replace("'", "\\'")
            clauses.append(
                f"(service.name = '{escaped_svc}' OR `entity.name` = '{escaped_svc}')"
            )
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        facet_clause = f" FACET {facet}" if facet else ""
        return (
            f"SELECT count(*) FROM Log{where}"
            f"{facet_clause} TIMESERIES {timeseries} SINCE {since}"
        )

    @staticmethod
    def _build_dependency_nrql(*, service: str, since: str) -> str:
        escaped = service.replace("'", "\\'")
        return (
            f"SELECT uniques(service.name), uniques(db.system) "
            f"FROM Span "
            f"WHERE (entity.name = '{escaped}' OR service.name = '{escaped}') "
            f"AND span.kind = 'client' "
            f"SINCE {since} LIMIT MAX"
        )

    @staticmethod
    def _build_upstream_nrql(*, service: str, since: str) -> str:
        escaped = service.replace("'", "\\'")
        return (
            f"SELECT uniques(entity.name) "
            f"FROM Span "
            f"WHERE (service.name = '{escaped}' OR `peer.service` = '{escaped}') "
            f"AND span.kind = 'server' "
            f"SINCE {since} LIMIT MAX"
        )

    @staticmethod
    def _build_error_nrql(*, service: str, since: str, limit: int) -> str:
        escaped = service.replace("'", "\\'")
        return (
            f"SELECT timestamp, message, level, error.message, traceId "
            f"FROM Log "
            f"WHERE (service.name = '{escaped}' OR `entity.name` = '{escaped}') "
            f"AND level IN ('ERROR', 'CRITICAL', 'FATAL', 'error', 'critical', 'fatal') "
            f"SINCE {since} LIMIT {limit}"
        )

    @staticmethod
    def _build_multi_account_nerdgraph(account_nrql_map: Dict[int, str]) -> str:
        if not account_nrql_map:
            raise NewRelicValidationError("account_nrql_map must not be empty.")
        fragments: List[str] = []
        for account_id, nrql in account_nrql_map.items():
            escaped_nrql = nrql.replace("\\", "\\\\").replace('"', '\\"')
            fragments.append(
                f'  a{account_id}: account(id: {account_id}) {{\n'
                f'    nrql(query: "{escaped_nrql}") {{ results }}\n'
                f'  }}'
            )
        return "{ actor {\n" + "\n".join(fragments) + "\n} }"

    # ------------------------------------------------------------------
    # Analysis helpers (static — fully testable without network)
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_severity(level: str) -> str:
        """Map raw log level string to internal severity tier."""
        return NewRelicClient._SEVERITY_MAP.get(level.lower().strip(), "LOW")

    @staticmethod
    def _normalize_message(message: str) -> str:
        """Replace variable tokens to produce a groupable message template."""
        normalized = message
        for pattern, replacement in NewRelicClient._NORMALIZE_PATTERNS:
            normalized = pattern.sub(replacement, normalized)
        # Trim after first newline (stack traces).
        normalized = normalized.split("\n")[0].strip()
        return normalized

    @staticmethod
    def _extract_error_patterns(
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Group error log results by normalized message template."""
        groups: Dict[str, Dict[str, Any]] = {}
        for row in results:
            raw_msg = str(row.get("message") or row.get("error.message") or "")
            template = NewRelicClient._normalize_message(raw_msg)
            if not template:
                template = "<empty message>"
            if template not in groups:
                groups[template] = {
                    "template": template,
                    "count": 0,
                    "severity_level": str(row.get("level") or "ERROR").upper(),
                    "samples": [],
                }
            groups[template]["count"] += 1
            if len(groups[template]["samples"]) < 3:
                groups[template]["samples"].append(raw_msg)
        return sorted(groups.values(), key=lambda g: g["count"], reverse=True)

    @staticmethod
    def _extract_baseline_counts(baseline_results: List[Dict[str, Any]]) -> Dict[str, int]:
        """Return message template → count mapping from baseline window results."""
        counts: Dict[str, int] = {}
        for row in baseline_results:
            raw_msg = str(row.get("message") or row.get("error.message") or "")
            template = NewRelicClient._normalize_message(raw_msg)
            counts[template] = counts.get(template, 0) + 1
        return counts

    @staticmethod
    def _score_rca_candidates(
        error_patterns: List[Dict[str, Any]],
        baseline_counts: Dict[str, int],
        dependency_errors: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Score and rank root-cause candidates from error patterns and dependency failures."""
        severity_weights = {"CRITICAL": 4.0, "FATAL": 4.0, "HIGH": 2.0, "ERROR": 2.0, "MEDIUM": 1.0, "LOW": 0.5}
        raw_candidates: List[Dict[str, Any]] = []

        for pattern in error_patterns:
            weight = severity_weights.get(pattern["severity_level"], 1.0)
            baseline = baseline_counts.get(pattern["template"], 0)
            if baseline == 0:
                novelty = 2.0
            elif pattern["count"] >= baseline * 2:
                novelty = 1.5
            else:
                novelty = 1.0
            score = pattern["count"] * weight * novelty
            raw_candidates.append(
                {
                    "category": "service_error",
                    "description": f"Repeated error: {pattern['template'][:120]}",
                    "evidence": pattern["samples"][:2],
                    "severity": NewRelicClient._classify_severity(pattern["severity_level"]),
                    "_score": score,
                }
            )

        for dep in dependency_errors:
            score = dep.get("error_count", 0) * 1.5
            raw_candidates.append(
                {
                    "category": "dependency_failure",
                    "description": f"Dependency '{dep['service']}' reported {dep['error_count']} errors",
                    "evidence": [f"Account(s): {dep.get('accounts', [])}"],
                    "severity": "HIGH" if dep.get("error_count", 0) >= 10 else "MEDIUM",
                    "_score": score,
                }
            )

        raw_candidates.sort(key=lambda c: c["_score"], reverse=True)
        total_score = sum(c["_score"] for c in raw_candidates) or 1.0
        candidates: List[Dict[str, Any]] = []
        for c in raw_candidates:
            candidates.append(
                {
                    "category": c["category"],
                    "description": c["description"],
                    "evidence": c["evidence"],
                    "confidence": round(c["_score"] / total_score, 3),
                    "severity": c["severity"],
                }
            )
        for c in candidates:
            c.pop("_score", None)
        return candidates

    @staticmethod
    def _generate_recommendation(candidates: List[Dict[str, Any]]) -> str:
        if not candidates:
            return (
                "No error patterns detected in the specified time window. "
                "Broaden the time range or check that the service name matches "
                "the `service.name` attribute in your logs."
            )
        top = candidates[0]
        if top["category"] == "dependency_failure":
            dep = top["description"].split("'")[1] if "'" in top["description"] else "the upstream dependency"
            return (
                f"The most likely root cause is a failure in a downstream dependency ({dep}). "
                "Investigate that service's logs and health status. "
                "Consider circuit-breaker activation or fallback routing while it recovers."
            )
        return (
            f"The most frequent error pattern is: \"{top['description']}\". "
            "Review the service's recent deployments, configuration changes, and resource usage. "
            "Check the `traceId` field in the error samples to trace individual request failures end-to-end."
        )

    @staticmethod
    def _generate_escalation_points(
        candidates: List[Dict[str, Any]],
        dependency_errors: List[Dict[str, Any]],
    ) -> List[str]:
        points: List[str] = []
        critical = [c for c in candidates if c.get("severity") == "CRITICAL"]
        if critical:
            points.append("Escalate to on-call engineer — CRITICAL severity errors detected.")
        if dependency_errors:
            deps = ", ".join(d["service"] for d in dependency_errors[:3])
            points.append(f"Notify owners of dependent services: {deps}.")
        if len(candidates) >= 3:
            points.append(
                "Multiple concurrent error patterns detected — consider full incident declaration."
            )
        if not points:
            points.append("No immediate escalation required; monitor trends over the next 30 minutes.")
        return points

    def _collect_dependency_errors(
        self,
        *,
        service: str,
        since: str,
        account_ids: List[int],
    ) -> List[Dict[str, Any]]:
        """Query error counts for services that have been recently called by the target service."""
        dep_info = self.trace_service_dependencies(service=service, since=since, account_ids=account_ids)
        dep_errors: List[Dict[str, Any]] = []

        for dep_service in dep_info.get("downstream_services", []):
            error_nrql = self._build_error_nrql(service=dep_service, since=since, limit=200)
            try:
                results_by_acct = self.run_nrql_across_accounts(nrql=error_nrql, account_ids=account_ids)
            except NewRelicAPIError:
                continue
            count = sum(len(r) for r in results_by_acct.values())
            if count > 0:
                dep_errors.append(
                    {
                        "service": dep_service,
                        "error_count": count,
                        "accounts": [aid for aid, r in results_by_acct.items() if r],
                    }
                )

        return dep_errors

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_account_ids(
        config_ids: List[int],
        override: Optional[List[int]],
    ) -> List[int]:
        ids = override if override is not None else config_ids
        if not ids:
            raise NewRelicValidationError(
                "No account IDs available. Configure NEWRELIC_ACCOUNT_IDS or pass account_ids explicitly."
            )
        return ids

    @staticmethod
    def _previous_window(since: str) -> str:
        """Return a SINCE clause that covers the equivalent period before the current window."""
        match = re.match(r"(\d+)\s+(minute|hour|day)s?\s+ago", since, re.IGNORECASE)
        if not match:
            return "2 hours ago"
        amount = int(match.group(1))
        unit = match.group(2).lower()
        return f"{amount * 2} {unit}s ago"

    @staticmethod
    def _estimate_rate_per_minute(count: int, since: str) -> float:
        match = re.match(r"(\d+)\s+(minute|hour|day)s?\s+ago", since, re.IGNORECASE)
        if not match:
            return 0.0
        amount = int(match.group(1))
        unit = match.group(2).lower()
        minutes = {"minute": 1, "hour": 60, "day": 1440}.get(unit, 1) * amount
        return round(count / max(minutes, 1), 2)
