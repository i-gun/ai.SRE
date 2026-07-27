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

    def test_list_fields_include_vendor_ticket_fields(self):
        self.assertIn("u_vendor_ticket", ServiceNowClient.LIST_FIELDS)
        self.assertIn("vendor_ticket", ServiceNowClient.LIST_FIELDS)


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

    def test_create_incident_includes_optional_operational_fields(self):
        with patch.object(
            self.client,
            "_request",
            return_value={"result": {"assignment_group": "Group A"}},
        ) as mock_request:
            self.client.create_incident(
                short_description="Login broken",
                description="Users cannot log in",
                caller_id="jdoe",
                assignment_group="Group A",
                assigned_to="sn.user",
                service_offering="Digital - Alerts",
                cmdb_ci="Digital - Alerts",
                contact="teams",
                contact_type="Self-service",
            )

        payload = mock_request.call_args.kwargs["json"]
        self.assertEqual(payload["assigned_to"], "sn.user")
        self.assertEqual(payload["service_offering"], "Digital - Alerts")
        self.assertEqual(payload["cmdb_ci"], "Digital - Alerts")
        self.assertEqual(payload["u_contact"], "teams")
        self.assertEqual(payload["contact_type"], "Self-service")


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

    def test_list_incidents_uses_assigned_to_user_name_for_username(self):
        with patch.object(self.client, "_request", return_value={"result": []}) as mock_request:
            self.client.list_incidents(assigned_to="Igor.Gunia")

        params = mock_request.call_args.kwargs["params"]
        self.assertIn("assigned_to.user_name=Igor.Gunia", params["sysparm_query"])

    def test_list_incidents_uses_assigned_to_for_sys_id(self):
        sys_id = "0123456789abcdef0123456789abcdef"
        with patch.object(self.client, "_request", return_value={"result": []}) as mock_request:
            self.client.list_incidents(assigned_to=sys_id)

        params = mock_request.call_args.kwargs["params"]
        self.assertIn(f"assigned_to={sys_id}", params["sysparm_query"])

    def test_query_incidents_applies_scope_and_custom_parts(self):
        with patch.object(self.client, "_request", return_value={"result": []}) as mock_request:
            self.client.query_incidents(
                query_parts=["active=true", "short_descriptionSTARTSWITHTriggered : "],
                limit=25,
                fields=["sys_id", "number"],
                exclude_resolved=True,
            )

        params = mock_request.call_args.kwargs["params"]
        self.assertIn("assignment_group.nameIN", params["sysparm_query"])
        self.assertIn("active=true", params["sysparm_query"])
        self.assertIn("state!=6", params["sysparm_query"])
        self.assertEqual(params["sysparm_fields"], "sys_id,number")


# ---------------------------------------------------------------------------
# TestIncidentUpdateHelpers
# ---------------------------------------------------------------------------

class TestIncidentUpdateHelpers(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def test_update_incident_fields_rejects_empty_fields(self):
        with self.assertRaises(ServiceNowValidationError):
            self.client.update_incident_fields(incident_number="INC0012345", fields={})

    def test_update_incident_fields_rejects_resolved_incident_when_forbidden(self):
        incident = {
            "sys_id": "a" * 32,
            "assignment_group": "Group A",
            "state": "Resolved",
            "active": "false",
        }
        with patch.object(self.client, "_find_incident", return_value=incident):
            with self.assertRaises(ServiceNowValidationError):
                self.client.update_incident_fields(
                    incident_number="INC0012345",
                    fields={"category": "Application"},
                    forbid_resolved=True,
                )

    def test_update_incident_fields_patches_payload(self):
        incident = {
            "sys_id": "a" * 32,
            "assignment_group": "Group A",
            "state": "In Progress",
            "active": "true",
        }
        updated = {
            "sys_id": "a" * 32,
            "assignment_group": "Group A",
            "category": "Application",
        }
        with patch.object(self.client, "_find_incident", return_value=incident):
            with patch.object(self.client, "_request", return_value={"result": updated}) as mock_request:
                result = self.client.update_incident_fields(
                    incident_number="INC0012345",
                    fields={"category": "Application", "work_notes": "note"},
                )

        self.assertEqual(result["category"], "Application")
        self.assertEqual(mock_request.call_args.args[0], "PATCH")
        self.assertEqual(mock_request.call_args.kwargs["json"]["category"], "Application")

    def test_resolve_incident_with_updates_sets_vendor_ticket_fields(self):
        incident = {
            "sys_id": "a" * 32,
            "assignment_group": "Group A",
            "state": "In Progress",
            "active": "true",
        }
        updated = {
            "sys_id": "a" * 32,
            "assignment_group": "Group A",
            "state": "Resolved",
            "u_vendor_ticket": "DDL-29601",
            "vendor_ticket": "DDL-29601",
        }
        with patch.object(self.client, "_find_incident", return_value=incident):
            with patch.object(self.client, "_request", return_value={"result": updated}) as mock_request:
                result = self.client.resolve_incident_with_updates(
                    incident_number="INC0012345",
                    close_code="Fixed",
                    close_notes="Implemented remediation and verified recovery for the affected service.",
                    vendor_ticket="DDL-29601",
                    category="Application",
                )

        payload = mock_request.call_args.kwargs["json"]
        self.assertEqual(payload["u_vendor_ticket"], "DDL-29601")
        self.assertEqual(payload["vendor_ticket"], "DDL-29601")
        self.assertEqual(result["state"], "Resolved")


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

    def test_problem_fields_include_origin_task_for_jira_handoff(self):
        self.assertIn("origin_task", ServiceNowClient.PROBLEM_FIELDS)

    def test_derive_incident_number_from_problem_prefers_origin_task(self):
        problem = {"origin_task": "INC0001234", "description": "Raised from incident INC9999999"}
        self.assertEqual(
            ServiceNowClient._derive_incident_number_from_problem(problem),
            "INC0001234",
        )

    def test_derive_incident_number_from_problem_falls_back_to_description(self):
        problem = {
            "origin_task": "",
            "description": "Raised from incident INC0054908. Investigation required.",
        }
        self.assertEqual(
            ServiceNowClient._derive_incident_number_from_problem(problem),
            "INC0054908",
        )

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

    def test_create_issue_with_routing_derives_incident_number_when_origin_task_missing(self):
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
                    "origin_task": "",
                    "short_description": "Problem from INC0054908: sample",
                    "problem_statement": "",
                    "description": "Raised from incident INC0054908.",
                },
            ):
                routed = self.client.create_issue_from_problem_with_routing(
                    problem_number="PRB0001",
                    routing_project="DDL",
                )
        self.assertEqual(routed["handoff"]["incident_number"], "INC0054908")

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

class TestProblemCreationMapping(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def test_create_problem_from_incident_sets_origin_task_with_incident_sys_id(self):
        incident_sys_id = "a" * 32
        incident = {
            "sys_id": incident_sys_id,
            "number": "INC0054908",
            "short_description": "Payment webhook failures",
            "description": "Repeated payment callback failures from provider.",
            "assignment_group": "Group A",
            "cmdb_ci": "Digital - New Relic Alerts - ODP",
        }

        created_problem_response = {
            "result": {
                "sys_id": "b" * 32,
                "number": "PRB0040370",
                "origin_task": {
                    "value": incident_sys_id,
                    "display_value": "INC0054908",
                },
            }
        }
        updated_incident_response = {
            "result": {
                "sys_id": incident_sys_id,
                "number": "INC0054908",
                "problem_id": "b" * 32,
            }
        }

        with patch.object(self.client, "_find_incident", return_value=incident):
            with patch.object(
                self.client,
                "_request",
                side_effect=[created_problem_response, updated_incident_response],
            ) as request_mock:
                result = self.client.create_problem_from_incident(incident_number="INC0054908")

        first_call = request_mock.call_args_list[0]
        self.assertEqual(first_call.args[0], "POST")
        self.assertEqual(first_call.args[1], ServiceNowClient.PROBLEM_TABLE_PATH)
        self.assertEqual(first_call.kwargs["json"]["origin_task"], incident_sys_id)
        self.assertEqual(
            first_call.kwargs["params"]["sysparm_input_display_value"],
            "true",
        )

        self.assertEqual(
            result["problem"]["origin_task"]["display_value"],
            "INC0054908",
        )


if __name__ == "__main__":
    unittest.main()
