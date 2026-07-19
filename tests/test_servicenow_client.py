"""Unit tests for servicenow_client.py — no real network access."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-incident-operations"
if str(CLIENT_PATH) not in sys.path:
    sys.path.insert(0, str(CLIENT_PATH))

from servicenow_client import (  # noqa: E402
    ServiceNowClient,
    ServiceNowConfig,
    ServiceNowConfigError,
    ServiceNowValidationError,
)


def _make_client(groups=None):
    config = ServiceNowConfig(
        host="https://example.service-now.com",
        username="user",
        password="pass",
        assignment_groups=groups or ["Group A", "Group B"],
    )
    return ServiceNowClient(config)


# ---------------------------------------------------------------------------
# TestServiceNowConfig
# ---------------------------------------------------------------------------

class TestServiceNowConfig(unittest.TestCase):

    def test_config_stores_fields(self):
        config = ServiceNowConfig(
            host="https://example.service-now.com",
            username="user",
            password="secret",
            assignment_groups=["Team X"],
        )
        self.assertEqual(config.host, "https://example.service-now.com")
        self.assertEqual(config.username, "user")
        self.assertEqual(config.password, "secret")
        self.assertEqual(config.assignment_groups, ["Team X"])

    def test_config_host_trailing_slash_stripped(self):
        env = {
            "SERVICENOW_HOST": "https://example.service-now.com/",
            "SERVICENOW_USERNAME": "user",
            "SERVICENOW_PASSWORD": "pass",
            "SERVICENOW_ASSIGNMENT_GROUPS": "Group A",
        }
        with patch.dict(os.environ, env, clear=False):
            config = ServiceNowConfig.from_env()
        self.assertEqual(config.host, "https://example.service-now.com")

    def test_parse_assignment_groups_single(self):
        result = ServiceNowConfig._parse_assignment_groups("Group A")
        self.assertEqual(result, ["Group A"])

    def test_parse_assignment_groups_multiple(self):
        result = ServiceNowConfig._parse_assignment_groups("Group A,Group B,Group C")
        self.assertEqual(result, ["Group A", "Group B", "Group C"])

    def test_parse_assignment_groups_deduplicates(self):
        result = ServiceNowConfig._parse_assignment_groups("Group A,Group A,Group B")
        self.assertEqual(result, ["Group A", "Group B"])

    def test_parse_assignment_groups_strips_whitespace(self):
        result = ServiceNowConfig._parse_assignment_groups("  Group A  ,  Group B  ")
        self.assertEqual(result, ["Group A", "Group B"])

    def test_parse_assignment_groups_empty_string_returns_empty(self):
        result = ServiceNowConfig._parse_assignment_groups("")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# TestDesignatedGroupMethods
# ---------------------------------------------------------------------------

class TestDesignatedGroupMethods(unittest.TestCase):

    def setUp(self):
        self.client = _make_client(["Group A", "Group B"])

    def test_is_designated_group_string_match(self):
        incident = {"assignment_group": "Group A"}
        self.assertTrue(self.client._is_designated_assignment_group(incident))

    def test_is_designated_group_dict_value_match(self):
        incident = {"assignment_group": {"value": "Group A"}}
        self.assertTrue(self.client._is_designated_assignment_group(incident))

    def test_is_designated_group_dict_display_value_match(self):
        incident = {"assignment_group": {"display_value": "Group B"}}
        self.assertTrue(self.client._is_designated_assignment_group(incident))

    def test_is_designated_group_non_matching_returns_false(self):
        incident = {"assignment_group": "Other Group"}
        self.assertFalse(self.client._is_designated_assignment_group(incident))

    def test_is_designated_group_none_returns_false(self):
        incident = {"assignment_group": None}
        self.assertFalse(self.client._is_designated_assignment_group(incident))

    def test_validate_scope_raises_for_outside_group(self):
        incident = {"assignment_group": "Unauthorized Group"}
        with self.assertRaises(ServiceNowValidationError):
            self.client._validate_incident_assignment_group_scope(incident)

    def test_validate_scope_passes_for_inside_group(self):
        incident = {"assignment_group": "Group A"}
        # Should not raise
        self.client._validate_incident_assignment_group_scope(incident)

    def test_designated_query_clause_format(self):
        clause = self.client._designated_assignment_group_query_clause()
        self.assertIn("assignment_group.nameIN", clause)
        self.assertIn("Group A", clause)
        self.assertIn("Group B", clause)


# ---------------------------------------------------------------------------
# TestPriorityMatrix
# ---------------------------------------------------------------------------

class TestPriorityMatrix(unittest.TestCase):

    def test_priority_matrix_p1_p1_gives_1(self):
        self.assertEqual(ServiceNowClient.PRIORITY_MATRIX[("1", "1")], "1")

    def test_priority_matrix_p2_p3_gives_4(self):
        self.assertEqual(ServiceNowClient.PRIORITY_MATRIX[("2", "3")], "4")

    def test_priority_matrix_p3_p3_gives_5(self):
        self.assertEqual(ServiceNowClient.PRIORITY_MATRIX[("3", "3")], "5")

    def test_priority_default_impact_urgency_p1(self):
        self.assertEqual(ServiceNowClient.PRIORITY_DEFAULT_IMPACT_URGENCY["1"], ("1", "1"))

    def test_priority_default_impact_urgency_p5(self):
        self.assertEqual(ServiceNowClient.PRIORITY_DEFAULT_IMPACT_URGENCY["5"], ("3", "3"))


# ---------------------------------------------------------------------------
# TestNormalizePriorityRequest
# ---------------------------------------------------------------------------

class TestNormalizePriorityRequest(unittest.TestCase):

    def test_accepts_bare_digits_1_to_5(self):
        for digit in ("1", "2", "3", "4", "5"):
            with self.subTest(digit=digit):
                self.assertEqual(ServiceNowClient._normalize_priority_request(digit), digit)

    def test_accepts_p_prefix_p1_to_p5(self):
        for i in range(1, 6):
            with self.subTest(i=i):
                result = ServiceNowClient._normalize_priority_request(f"P{i}")
                self.assertEqual(result, str(i))

    def test_accepts_priority_word_format(self):
        result = ServiceNowClient._normalize_priority_request("priority 3")
        self.assertEqual(result, "3")

    def test_rejects_invalid_string(self):
        with self.assertRaises(ServiceNowValidationError):
            ServiceNowClient._normalize_priority_request("critical")

    def test_rejects_empty_string(self):
        with self.assertRaises(ServiceNowValidationError):
            ServiceNowClient._normalize_priority_request("")

    def test_case_insensitive_p_prefix(self):
        self.assertEqual(ServiceNowClient._normalize_priority_request("p2"), "2")
        self.assertEqual(ServiceNowClient._normalize_priority_request("P4"), "4")


# ---------------------------------------------------------------------------
# TestExtractReferenceValue
# ---------------------------------------------------------------------------

class TestExtractReferenceValue(unittest.TestCase):

    def test_extracts_dict_value_key(self):
        result = ServiceNowClient._extract_reference_value({"value": "abc123"})
        self.assertEqual(result, "abc123")

    def test_extracts_dict_display_value_key_when_no_value(self):
        result = ServiceNowClient._extract_reference_value({"display_value": "Some Name"})
        self.assertEqual(result, "Some Name")

    def test_extracts_plain_string(self):
        result = ServiceNowClient._extract_reference_value("plain string")
        self.assertEqual(result, "plain string")

    def test_returns_empty_for_none(self):
        result = ServiceNowClient._extract_reference_value(None)
        self.assertEqual(result, "")

    def test_returns_empty_for_empty_dict(self):
        result = ServiceNowClient._extract_reference_value({})
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# TestSafeErrorDetail
# ---------------------------------------------------------------------------

class TestSafeErrorDetail(unittest.TestCase):

    def _mock_response(self, json_data=None, text="", raises_json=False):
        mock_resp = MagicMock()
        mock_resp.text = text
        if raises_json:
            mock_resp.json.side_effect = ValueError("not JSON")
        else:
            mock_resp.json.return_value = json_data
        return mock_resp

    def test_extracts_error_key_from_json(self):
        response = self._mock_response(json_data={"error": "bad request"})
        detail = ServiceNowClient._safe_error_detail(response)
        self.assertIn("bad request", detail)

    def test_extracts_message_key_from_json(self):
        response = self._mock_response(json_data={"message": "something went wrong"})
        detail = ServiceNowClient._safe_error_detail(response)
        self.assertIn("something went wrong", detail)

    def test_handles_non_json_response(self):
        response = self._mock_response(raises_json=True, text="Internal Server Error")
        detail = ServiceNowClient._safe_error_detail(response)
        self.assertIn("Internal Server Error", detail)

    def test_handles_empty_text_response(self):
        response = self._mock_response(raises_json=True, text="")
        detail = ServiceNowClient._safe_error_detail(response)
        self.assertEqual(detail, "Unknown error")


# ---------------------------------------------------------------------------
# TestCreateIncidentValidation
# ---------------------------------------------------------------------------

class TestCreateIncidentValidation(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def _patch_request(self):
        return patch.object(
            self.client,
            "_request",
            return_value={"result": {"assignment_group": "Group A"}},
        )

    def test_raises_when_short_description_missing(self):
        with self._patch_request():
            with self.assertRaises(ServiceNowValidationError):
                self.client.create_incident(
                    short_description="",
                    description="Some details",
                    caller_id="jdoe",
                )

    def test_raises_when_description_missing(self):
        with self._patch_request():
            with self.assertRaises(ServiceNowValidationError):
                self.client.create_incident(
                    short_description="Login broken",
                    description="",
                    caller_id="jdoe",
                )

    def test_raises_when_caller_id_missing(self):
        with self._patch_request():
            with self.assertRaises(ServiceNowValidationError):
                self.client.create_incident(
                    short_description="Login broken",
                    description="Users cannot log in",
                    caller_id="",
                )

    def test_raises_when_impact_invalid(self):
        with self._patch_request():
            with self.assertRaises(ServiceNowValidationError):
                self.client.create_incident(
                    short_description="Login broken",
                    description="Users cannot log in",
                    caller_id="jdoe",
                    impact="9",
                )

    def test_raises_when_urgency_invalid(self):
        with self._patch_request():
            with self.assertRaises(ServiceNowValidationError):
                self.client.create_incident(
                    short_description="Login broken",
                    description="Users cannot log in",
                    caller_id="jdoe",
                    urgency="0",
                )

    def test_raises_when_assignment_group_not_in_designated(self):
        with self._patch_request():
            with self.assertRaises(ServiceNowValidationError):
                self.client.create_incident(
                    short_description="Login broken",
                    description="Users cannot log in",
                    caller_id="jdoe",
                    assignment_group="Unauthorized Group",
                )


# ---------------------------------------------------------------------------
# TestListIncidentsValidation
# ---------------------------------------------------------------------------

class TestListIncidentsValidation(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def _patch_request(self):
        return patch.object(
            self.client,
            "_request",
            return_value={"result": []},
        )

    def test_raises_when_limit_zero(self):
        with self._patch_request():
            with self.assertRaises(ServiceNowValidationError):
                self.client.list_incidents(limit=0)

    def test_raises_when_limit_exceeds_500(self):
        with self._patch_request():
            with self.assertRaises(ServiceNowValidationError):
                self.client.list_incidents(limit=501)

    def test_raises_when_assignment_group_not_in_designated(self):
        with self._patch_request():
            with self.assertRaises(ServiceNowValidationError):
                self.client.list_incidents(assignment_group="Unlisted Group")


# ---------------------------------------------------------------------------
# TestIssueRoutingFromProblem
# ---------------------------------------------------------------------------

class TestIssueRoutingFromProblem(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def test_detect_capability_requires_valid_project(self):
        with patch.object(self.client, "_find_problem", return_value={"number": "PRB1"}):
            with self.assertRaises(ServiceNowValidationError):
                self.client.detect_native_jira_from_problem_capability(
                    problem_number="PRB1",
                    routing_project="INVALID",
                )

    def test_detect_capability_unavailable_when_probe_fails(self):
        with patch.object(self.client, "_find_problem", return_value={"number": "PRB1"}):
            with patch.object(
                self.client,
                "_request",
                side_effect=Exception("forbidden"),
            ):
                result = self.client.detect_native_jira_from_problem_capability(
                    problem_number="PRB1",
                    routing_project="DDL",
                )
        self.assertEqual(result["availability"], "unavailable")
        self.assertEqual(result["recommended_route"], "jira_agent_delegation")

    def test_detect_capability_conditionally_available_with_signals(self):
        with patch.object(self.client, "_find_problem", return_value={"number": "PRB1"}):
            with patch.object(
                self.client,
                "_request",
                return_value={
                    "result": [
                        {
                            "number": "PTASK1",
                            "u_jira_project": "DDL",
                            "u_jira_ticket_creation_status": "",
                        }
                    ]
                },
            ):
                result = self.client.detect_native_jira_from_problem_capability(
                    problem_number="PRB1",
                    routing_project="DDL",
                )
        self.assertEqual(result["availability"], "conditionally_available")

    def test_create_issue_with_routing_returns_handoff_when_unavailable(self):
        with patch.object(
            self.client,
            "detect_native_jira_from_problem_capability",
            return_value={
                "availability": "unavailable",
                "mode": "unavailable",
                "recommended_route": "jira_agent_delegation",
            },
        ):
            with patch.object(
                self.client,
                "_find_problem",
                return_value={
                    "number": "PRB0001",
                    "origin_task": "INC0001",
                    "problem_statement": "Short",
                    "description": "Long",
                },
            ):
                routed = self.client.create_issue_from_problem_with_routing(
                    problem_number="PRB0001",
                    routing_project="DDL",
                )
        self.assertEqual(routed["route_used"], "jira_agent_delegation")
        self.assertEqual(routed["handoff"]["required_issue_type"], "Problem")

    def test_create_issue_with_routing_uses_native_when_available(self):
        with patch.object(
            self.client,
            "detect_native_jira_from_problem_capability",
            return_value={"availability": "available", "mode": "native_via_ptask"},
        ):
            with patch.object(
                self.client,
                "create_native_jira_issue_from_problem",
                return_value={"route_used": "servicenow_native_jira", "issue_number_or_key": "DDL-1"},
            ) as native_call:
                routed = self.client.create_issue_from_problem_with_routing(
                    problem_number="PRB0001",
                    routing_project="DDL",
                )
        self.assertEqual(routed["route_used"], "servicenow_native_jira")
        native_call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
