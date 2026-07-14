"""Unit tests for New Relic NRQL building, config parsing, severity classification, and RCA scoring."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = PROJECT_ROOT / ".github" / "skills" / "newrelic-log-operations"
AUTH_PATH = PROJECT_ROOT / ".github" / "skills" / "newrelic-authentication"
for _p in (CLIENT_PATH, AUTH_PATH):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from newrelic_client import NewRelicClient, NewRelicConfig, NewRelicValidationError  # noqa: E402
from newrelic_env import NewRelicAuthConfig, NewRelicAuthConfigError  # noqa: E402


# ---------------------------------------------------------------------------
# Config construction
# ---------------------------------------------------------------------------

class TestNewRelicConfig(unittest.TestCase):
    def test_single_account(self) -> None:
        config = NewRelicConfig(api_key="NRAK-abc", account_ids=[123456])
        self.assertEqual(config.account_ids, [123456])
        self.assertEqual(config.api_key, "NRAK-abc")

    def test_multiple_accounts(self) -> None:
        config = NewRelicConfig(api_key="NRAK-abc", account_ids=[111111, 222222, 333333])
        self.assertEqual(len(config.account_ids), 3)
        self.assertIn(222222, config.account_ids)


# ---------------------------------------------------------------------------
# Auth config env parsing (newrelic_env.py)
# ---------------------------------------------------------------------------

class TestNewRelicAuthConfig(unittest.TestCase):
    def test_direct_construction_single(self) -> None:
        cfg = NewRelicAuthConfig(api_key="NRAK-test", account_ids=[999])
        self.assertEqual(cfg.account_ids, [999])

    def test_direct_construction_multiple(self) -> None:
        cfg = NewRelicAuthConfig(api_key="NRAK-test", account_ids=[1, 2, 3])
        self.assertEqual(cfg.account_ids, [1, 2, 3])


# ---------------------------------------------------------------------------
# NRQL builders
# ---------------------------------------------------------------------------

class TestNRQLBuilders(unittest.TestCase):
    def _client(self) -> NewRelicClient:
        return NewRelicClient(NewRelicConfig(api_key="NRAK-test", account_ids=[123456]))

    # Log search

    def test_build_log_search_nrql_minimal(self) -> None:
        nrql = NewRelicClient._build_log_search_nrql(
            message_contains="", severity=None, service=None,
            since="1 hour ago", limit=100,
        )
        self.assertIn("FROM Log", nrql)
        self.assertIn("1 hour ago", nrql)
        self.assertIn("LIMIT 100", nrql)
        self.assertNotIn("WHERE", nrql)

    def test_build_log_search_nrql_message_filter(self) -> None:
        nrql = NewRelicClient._build_log_search_nrql(
            message_contains="timeout", severity=None, service=None,
            since="1 hour ago", limit=50,
        )
        self.assertIn("WHERE", nrql)
        self.assertIn("timeout", nrql)
        self.assertIn("LIKE", nrql)

    def test_build_log_search_nrql_severity_filter(self) -> None:
        nrql = NewRelicClient._build_log_search_nrql(
            message_contains="", severity="ERROR", service=None,
            since="1 hour ago", limit=100,
        )
        self.assertIn("level", nrql)
        self.assertIn("'ERROR'", nrql)

    def test_build_log_search_nrql_service_filter(self) -> None:
        nrql = NewRelicClient._build_log_search_nrql(
            message_contains="", severity=None, service="payment-service",
            since="1 hour ago", limit=100,
        )
        self.assertIn("payment-service", nrql)

    def test_build_log_search_nrql_all_filters(self) -> None:
        nrql = NewRelicClient._build_log_search_nrql(
            message_contains="db conn", severity="CRITICAL", service="auth-api",
            since="30 minutes ago", limit=25,
        )
        self.assertIn("db conn", nrql)
        self.assertIn("CRITICAL", nrql)
        self.assertIn("auth-api", nrql)
        self.assertIn("30 minutes ago", nrql)
        self.assertIn("LIMIT 25", nrql)

    # Trend analysis

    def test_build_trend_nrql_basic(self) -> None:
        nrql = NewRelicClient._build_trend_nrql(
            message_contains="error", service=None,
            since="24 hours ago", timeseries="10 minutes", facet=None,
        )
        self.assertIn("TIMESERIES 10 minutes", nrql)
        self.assertIn("count(*)", nrql)
        self.assertIn("FROM Log", nrql)

    def test_build_trend_nrql_with_facet(self) -> None:
        nrql = NewRelicClient._build_trend_nrql(
            message_contains="", service="checkout-service",
            since="6 hours ago", timeseries="5 minutes", facet="level",
        )
        self.assertIn("FACET level", nrql)
        self.assertIn("checkout-service", nrql)

    def test_build_trend_nrql_no_facet_no_where(self) -> None:
        nrql = NewRelicClient._build_trend_nrql(
            message_contains="", service=None,
            since="1 hour ago", timeseries="1 minute", facet=None,
        )
        self.assertNotIn("WHERE", nrql)
        self.assertNotIn("FACET", nrql)

    # Dependency NRQL

    def test_build_dependency_nrql(self) -> None:
        nrql = NewRelicClient._build_dependency_nrql(
            service="order-service", since="1 hour ago"
        )
        self.assertIn("FROM Span", nrql)
        self.assertIn("order-service", nrql)
        self.assertIn("client", nrql)

    def test_build_upstream_nrql(self) -> None:
        nrql = NewRelicClient._build_upstream_nrql(
            service="inventory-service", since="2 hours ago"
        )
        self.assertIn("FROM Span", nrql)
        self.assertIn("inventory-service", nrql)
        self.assertIn("server", nrql)

    def test_build_error_nrql(self) -> None:
        nrql = NewRelicClient._build_error_nrql(
            service="shipping-service", since="1 hour ago", limit=200
        )
        self.assertIn("FROM Log", nrql)
        self.assertIn("shipping-service", nrql)
        self.assertIn("ERROR", nrql)
        self.assertIn("LIMIT 200", nrql)

    # Alert search

    def test_build_alert_search_nrql_excludes_muted_by_default(self) -> None:
        nrql = NewRelicClient._build_alert_search_nrql(
            policy_name_contains="", priority=None,
            since="1 hour ago", exclude_muted=True, limit=100,
        )
        self.assertIn("FROM NrAiIssue", nrql)
        self.assertIn("muted != 'fullyMuted'", nrql)
        self.assertIn("1 hour ago", nrql)
        self.assertIn("LIMIT 100", nrql)
        self.assertIn("ORDER BY lastModifiedTime DESC", nrql)

    def test_build_alert_search_nrql_includes_muted_when_disabled(self) -> None:
        nrql = NewRelicClient._build_alert_search_nrql(
            policy_name_contains="", priority=None,
            since="1 hour ago", exclude_muted=False, limit=50,
        )
        self.assertIn("FROM NrAiIssue", nrql)
        self.assertNotIn("fullyMuted", nrql)

    def test_build_alert_search_nrql_policy_filter(self) -> None:
        nrql = NewRelicClient._build_alert_search_nrql(
            policy_name_contains="Digital Operations", priority=None,
            since="1 hour ago", exclude_muted=True, limit=100,
        )
        self.assertIn("policyNames LIKE '%Digital Operations%'", nrql)
        self.assertIn("muted != 'fullyMuted'", nrql)

    def test_build_alert_search_nrql_priority_filter(self) -> None:
        nrql = NewRelicClient._build_alert_search_nrql(
            policy_name_contains="", priority="critical",
            since="1 hour ago", exclude_muted=True, limit=100,
        )
        self.assertIn("priority = 'CRITICAL'", nrql)

    def test_build_alert_search_nrql_all_filters(self) -> None:
        nrql = NewRelicClient._build_alert_search_nrql(
            policy_name_contains="Payments", priority="HIGH",
            since="30 minutes ago", exclude_muted=True, limit=25,
        )
        self.assertIn("muted != 'fullyMuted'", nrql)
        self.assertIn("policyNames LIKE '%Payments%'", nrql)
        self.assertIn("priority = 'HIGH'", nrql)
        self.assertIn("30 minutes ago", nrql)
        self.assertIn("LIMIT 25", nrql)

    def test_build_alert_search_nrql_escapes_single_quote_in_policy(self) -> None:
        nrql = NewRelicClient._build_alert_search_nrql(
            policy_name_contains="It's Ops", priority=None,
            since="1 hour ago", exclude_muted=True, limit=100,
        )
        self.assertIn("\\'", nrql)
        self.assertNotIn("It's Ops", nrql)

    def test_build_alert_search_nrql_selected_fields(self) -> None:
        nrql = NewRelicClient._build_alert_search_nrql(
            policy_name_contains="", priority=None,
            since="1 hour ago", exclude_muted=True, limit=100,
        )
        for field in ("issueId", "title", "policyNames", "conditionNames",
                      "priority", "event", "issueLink", "muted",
                      "activateTime", "lastModifiedTime"):
            self.assertIn(field, nrql)

    # NerdGraph multi-account builder

    def test_build_multi_account_nerdgraph_single(self) -> None:
        gql = NewRelicClient._build_multi_account_nerdgraph(
            {123456: "SELECT count(*) FROM Log SINCE 1 hour ago"}
        )
        self.assertIn("a123456", gql)
        self.assertIn("SELECT count(*) FROM Log", gql)
        self.assertIn("actor", gql)
        self.assertIn("nrql", gql)

    def test_build_multi_account_nerdgraph_multiple(self) -> None:
        gql = NewRelicClient._build_multi_account_nerdgraph(
            {111: "SELECT 1 FROM Log", 222: "SELECT 2 FROM Log"}
        )
        self.assertIn("a111", gql)
        self.assertIn("a222", gql)

    def test_build_multi_account_nerdgraph_empty_raises(self) -> None:
        with self.assertRaises(NewRelicValidationError):
            NewRelicClient._build_multi_account_nerdgraph({})


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

class TestSeverityClassification(unittest.TestCase):
    def test_critical_and_fatal(self) -> None:
        self.assertEqual(NewRelicClient._classify_severity("CRITICAL"), "CRITICAL")
        self.assertEqual(NewRelicClient._classify_severity("FATAL"), "CRITICAL")
        self.assertEqual(NewRelicClient._classify_severity("critical"), "CRITICAL")

    def test_error(self) -> None:
        self.assertEqual(NewRelicClient._classify_severity("ERROR"), "HIGH")
        self.assertEqual(NewRelicClient._classify_severity("error"), "HIGH")
        self.assertEqual(NewRelicClient._classify_severity("ERR"), "HIGH")

    def test_warn(self) -> None:
        self.assertEqual(NewRelicClient._classify_severity("WARN"), "MEDIUM")
        self.assertEqual(NewRelicClient._classify_severity("WARNING"), "MEDIUM")

    def test_low_levels(self) -> None:
        self.assertEqual(NewRelicClient._classify_severity("INFO"), "LOW")
        self.assertEqual(NewRelicClient._classify_severity("DEBUG"), "LOW")
        self.assertEqual(NewRelicClient._classify_severity("TRACE"), "LOW")
        self.assertEqual(NewRelicClient._classify_severity("unknown"), "LOW")


# ---------------------------------------------------------------------------
# Message normalization and pattern extraction
# ---------------------------------------------------------------------------

class TestErrorPatternExtraction(unittest.TestCase):
    def test_groups_similar_messages(self) -> None:
        results = [
            {"message": "Connection timeout for user 12345", "level": "ERROR"},
            {"message": "Connection timeout for user 99999", "level": "ERROR"},
            {"message": "NullPointerException in PaymentService", "level": "CRITICAL"},
        ]
        patterns = NewRelicClient._extract_error_patterns(results)
        total = sum(p["count"] for p in patterns)
        self.assertEqual(total, 3)
        self.assertGreaterEqual(len(patterns), 1)

    def test_counts_correctly(self) -> None:
        results = [{"message": "DB connection failed", "level": "ERROR"}] * 5
        patterns = NewRelicClient._extract_error_patterns(results)
        self.assertEqual(patterns[0]["count"], 5)

    def test_empty_results_returns_empty(self) -> None:
        patterns = NewRelicClient._extract_error_patterns([])
        self.assertEqual(patterns, [])

    def test_sorted_by_count_desc(self) -> None:
        results = (
            [{"message": "rare error XYZ", "level": "ERROR"}]
            + [{"message": "frequent error ABC", "level": "ERROR"}] * 10
        )
        patterns = NewRelicClient._extract_error_patterns(results)
        self.assertGreater(patterns[0]["count"], patterns[-1]["count"])


# ---------------------------------------------------------------------------
# RCA scoring
# ---------------------------------------------------------------------------

class TestRCAScoring(unittest.TestCase):
    def test_candidates_sorted_by_confidence(self) -> None:
        patterns = [
            {"template": "Connection timeout", "count": 10, "severity_level": "ERROR", "samples": []},
            {"template": "NullPointerException", "count": 2, "severity_level": "CRITICAL", "samples": []},
        ]
        candidates = NewRelicClient._score_rca_candidates(patterns, {}, [])
        self.assertGreater(len(candidates), 0)
        for i in range(len(candidates) - 1):
            self.assertGreaterEqual(candidates[i]["confidence"], candidates[i + 1]["confidence"])

    def test_novel_errors_score_higher(self) -> None:
        patterns = [
            {"template": "new error", "count": 5, "severity_level": "ERROR", "samples": []},
            {"template": "old error", "count": 5, "severity_level": "ERROR", "samples": []},
        ]
        baseline = {"old error": 5}
        candidates = NewRelicClient._score_rca_candidates(patterns, baseline, [])
        new_candidate = next(c for c in candidates if "new error" in c["description"])
        old_candidate = next(c for c in candidates if "old error" in c["description"])
        self.assertGreater(new_candidate["confidence"], old_candidate["confidence"])

    def test_dependency_failures_appear_as_candidates(self) -> None:
        dep_errors = [{"service": "payment-api", "error_count": 20, "accounts": [123]}]
        candidates = NewRelicClient._score_rca_candidates([], {}, dep_errors)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["category"], "dependency_failure")

    def test_no_errors_returns_empty(self) -> None:
        candidates = NewRelicClient._score_rca_candidates([], {}, [])
        self.assertEqual(candidates, [])


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

class TestUtilityHelpers(unittest.TestCase):
    def test_resolve_account_ids_uses_override(self) -> None:
        ids = NewRelicClient._resolve_account_ids([100, 200], [300, 400])
        self.assertEqual(ids, [300, 400])

    def test_resolve_account_ids_falls_back_to_config(self) -> None:
        ids = NewRelicClient._resolve_account_ids([100, 200], None)
        self.assertEqual(ids, [100, 200])

    def test_resolve_account_ids_raises_when_empty_config(self) -> None:
        with self.assertRaises(NewRelicValidationError):
            NewRelicClient._resolve_account_ids([], None)

    def test_previous_window_hours(self) -> None:
        self.assertEqual(NewRelicClient._previous_window("1 hour ago"), "2 hours ago")
        self.assertEqual(NewRelicClient._previous_window("2 hours ago"), "4 hours ago")

    def test_previous_window_minutes(self) -> None:
        self.assertEqual(NewRelicClient._previous_window("30 minutes ago"), "60 minutes ago")

    def test_previous_window_unknown_falls_back(self) -> None:
        result = NewRelicClient._previous_window("last week")
        self.assertEqual(result, "2 hours ago")

    def test_estimate_rate_per_minute_hours(self) -> None:
        rate = NewRelicClient._estimate_rate_per_minute(120, "2 hours ago")
        self.assertAlmostEqual(rate, 1.0)

    def test_estimate_rate_per_minute_minutes(self) -> None:
        rate = NewRelicClient._estimate_rate_per_minute(50, "10 minutes ago")
        self.assertAlmostEqual(rate, 5.0)


if __name__ == "__main__":
    unittest.main()
