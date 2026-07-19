"""Unit tests for jira_client.py — no real network access."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = PROJECT_ROOT / ".github" / "skills" / "jira-issue-operations"
if str(CLIENT_PATH) not in sys.path:
    sys.path.insert(0, str(CLIENT_PATH))

from jira_client import JiraAPIError, JiraClient, JiraConfig, JiraValidationError  # noqa: E402


def _make_client():
    return JiraClient(
        JiraConfig(
            host="https://example.atlassian.net",
            username="user",
            api_token="token",
        )
    )


# ---------------------------------------------------------------------------
# TestJiraConfig
# ---------------------------------------------------------------------------

class TestJiraConfig(unittest.TestCase):

    def test_config_stores_fields(self):
        config = JiraConfig(
            host="https://example.atlassian.net",
            username="user",
            api_token="mytoken",
        )
        self.assertEqual(config.host, "https://example.atlassian.net")
        self.assertEqual(config.username, "user")
        self.assertEqual(config.api_token, "mytoken")

    def test_config_host_trailing_slash_stripped(self):
        env = {
            "JIRA_HOST": "https://example.atlassian.net/",
            "JIRA_USERNAME": "user",
            "JIRA_API_TOKEN": "token",
        }
        with patch.dict(os.environ, env, clear=False):
            config = JiraConfig.from_env()
        self.assertEqual(config.host, "https://example.atlassian.net")


# ---------------------------------------------------------------------------
# TestNormalizeHelpers
# ---------------------------------------------------------------------------

class TestNormalizeHelpers(unittest.TestCase):

    def test_normalize_issue_key_strips_whitespace(self):
        result = JiraClient._normalize_issue_key("  TEST-1  ")
        self.assertEqual(result, "TEST-1")

    def test_normalize_issue_key_empty_raises(self):
        with self.assertRaises(JiraValidationError):
            JiraClient._normalize_issue_key("   ")

    def test_normalize_limit_valid(self):
        self.assertEqual(JiraClient._normalize_limit(10), 10)

    def test_normalize_limit_zero_raises(self):
        with self.assertRaises(JiraValidationError):
            JiraClient._normalize_limit(0)

    def test_normalize_limit_negative_raises(self):
        with self.assertRaises(JiraValidationError):
            JiraClient._normalize_limit(-5)


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

    def test_extracts_error_messages_list(self):
        response = self._mock_response(json_data={"errorMessages": ["Not found"]})
        detail = JiraClient._safe_error_detail(response)
        self.assertIn("Not found", detail)

    def test_extracts_errors_dict(self):
        response = self._mock_response(json_data={"errors": {"field": "required"}})
        detail = JiraClient._safe_error_detail(response)
        self.assertIn("field", detail)
        self.assertIn("required", detail)

    def test_handles_non_json_response(self):
        response = self._mock_response(raises_json=True, text="Bad Gateway")
        detail = JiraClient._safe_error_detail(response)
        self.assertIn("Bad Gateway", detail)

    def test_handles_empty_body(self):
        response = self._mock_response(raises_json=True, text="")
        detail = JiraClient._safe_error_detail(response)
        self.assertEqual(detail, "Unknown error")


# ---------------------------------------------------------------------------
# TestCreateIssueValidation
# ---------------------------------------------------------------------------

class TestCreateIssueValidation(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def _patch_request(self, return_value=None):
        return patch.object(
            self.client,
            "_request",
            return_value=return_value or {"id": "10001", "key": "TEST-1"},
        )

    def _patch_issue_type_preflight(self, issue_types=None):
        return patch.object(
            self.client,
            "get_project_issue_types",
            return_value=issue_types or ["Bug", "Task", "Problem"],
        )

    def test_raises_when_project_key_empty(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.create_issue(
                    project_key="",
                    issue_type="Bug",
                    summary="Something broke",
                )

    def test_raises_when_issue_type_empty(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.create_issue(
                    project_key="TEST",
                    issue_type="",
                    summary="Something broke",
                )

    def test_raises_when_summary_empty(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.create_issue(
                    project_key="TEST",
                    issue_type="Bug",
                    summary="",
                )

    def test_calls_request_with_correct_fields(self):
        with self._patch_issue_type_preflight():
            with self._patch_request() as mock_req:
                self.client.create_issue(
                    project_key="TEST",
                    issue_type="Bug",
                    summary="Something broke",
                )
        _, kwargs = mock_req.call_args
        fields = kwargs["json"]["fields"]
        self.assertEqual(fields["project"], {"key": "TEST"})
        self.assertEqual(fields["issuetype"], {"name": "Bug"})
        self.assertEqual(fields["summary"], "Something broke")

    def test_optional_fields_included_when_provided(self):
        with self._patch_issue_type_preflight(issue_types=["Story", "Problem"]):
            with self._patch_request() as mock_req:
                self.client.create_issue(
                    project_key="TEST",
                    issue_type="Story",
                    summary="New feature",
                    description="Full description here",
                    assignee="user123",
                    priority="High",
                    labels=["backend", "urgent"],
                    components=["API"],
                )
        _, kwargs = mock_req.call_args
        fields = kwargs["json"]["fields"]
        self.assertIn("description", fields)
        self.assertEqual(fields["assignee"], {"id": "user123"})
        self.assertEqual(fields["priority"], {"name": "High"})
        self.assertIn("backend", fields["labels"])
        self.assertEqual(fields["components"], [{"name": "API"}])

    def test_preflight_rejects_unavailable_issue_type(self):
        with self._patch_issue_type_preflight(issue_types=["Bug", "Task"]):
            with self.assertRaises(JiraValidationError):
                self.client.create_issue(
                    project_key="TEST",
                    issue_type="Problem",
                    summary="Escalation should fail fast",
                )

    def test_can_skip_preflight_when_explicitly_disabled(self):
        with self._patch_request() as mock_req:
            self.client.create_issue(
                project_key="TEST",
                issue_type="Problem",
                summary="Skip preflight by policy override",
                verify_issue_type_available=False,
            )
        mock_req.assert_called_once()


# ---------------------------------------------------------------------------
# TestIssueTypePreflight
# ---------------------------------------------------------------------------

class TestIssueTypePreflight(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def test_get_project_issue_types_from_list_payload(self):
        payload = [
            {"name": "Bug"},
            {"name": "Problem"},
            {"name": "Problem"},
        ]
        with patch.object(self.client, "_request", return_value=payload):
            issue_types = self.client.get_project_issue_types(project_key="DDL")
        self.assertEqual(issue_types, ["Bug", "Problem"])

    def test_ensure_issue_type_available_passes_on_case_insensitive_match(self):
        with patch.object(self.client, "get_project_issue_types", return_value=["Problem", "Task"]):
            self.client.ensure_issue_type_available(project_key="DDL", issue_type="problem")

    def test_ensure_issue_type_available_raises_when_missing(self):
        with patch.object(self.client, "get_project_issue_types", return_value=["Task", "Bug"]):
            with self.assertRaises(JiraValidationError):
                self.client.ensure_issue_type_available(project_key="DDL", issue_type="Problem")


# ---------------------------------------------------------------------------
# TestUpdateIssueValidation
# ---------------------------------------------------------------------------

class TestUpdateIssueValidation(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def _patch_request(self):
        return patch.object(self.client, "_request", return_value={})

    def test_raises_when_empty_fields_dict(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.update_issue("TEST-1", fields={})

    def test_raises_when_issue_key_empty(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.update_issue("   ", fields={"summary": "New title"})


# ---------------------------------------------------------------------------
# TestAddCommentValidation
# ---------------------------------------------------------------------------

class TestAddCommentValidation(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def _patch_request(self):
        return patch.object(self.client, "_request", return_value={"id": "1"})

    def test_raises_when_comment_empty(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.add_comment("TEST-1", comment="   ")

    def test_raises_when_issue_key_empty(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.add_comment("", comment="This is a comment")


# ---------------------------------------------------------------------------
# TestLinkIssuesValidation
# ---------------------------------------------------------------------------

class TestLinkIssuesValidation(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def _patch_request(self):
        return patch.object(self.client, "_request", return_value={})

    def test_raises_when_inward_key_empty(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.link_issues(
                    inward_issue_key="",
                    outward_issue_key="TEST-2",
                )

    def test_raises_when_outward_key_empty(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.link_issues(
                    inward_issue_key="TEST-1",
                    outward_issue_key="",
                )

    def test_default_link_type_is_relates(self):
        with self._patch_request() as mock_req:
            self.client.link_issues(
                inward_issue_key="TEST-1",
                outward_issue_key="TEST-2",
            )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["json"]["type"]["name"], "Relates")

    def test_custom_link_type_used(self):
        with self._patch_request() as mock_req:
            self.client.link_issues(
                inward_issue_key="TEST-1",
                outward_issue_key="TEST-2",
                link_type="Blocks",
            )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["json"]["type"]["name"], "Blocks")


# ---------------------------------------------------------------------------
# TestSearchIssuesValidation
# ---------------------------------------------------------------------------

class TestSearchIssuesValidation(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def _patch_request(self):
        return patch.object(
            self.client,
            "_request",
            return_value={"issues": []},
        )

    def test_raises_when_jql_empty(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.search_issues(jql="   ")

    def test_raises_when_limit_zero(self):
        with self._patch_request():
            with self.assertRaises(JiraValidationError):
                self.client.search_issues(jql="project = TEST", limit=0)

    def test_uses_default_fields_when_none_provided(self):
        with self._patch_request() as mock_req:
            self.client.search_issues(jql="project = TEST")
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["json"]["fields"], JiraClient.DEFAULT_ISSUE_FIELDS)


# ---------------------------------------------------------------------------
# TestTeamFieldOperations
# ---------------------------------------------------------------------------

class TestTeamFieldOperations(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

    def test_resolve_team_id_from_project_history_returns_matching_uuid(self):
        payload = {
            "issues": [
                {
                    "fields": {
                        "customfield_11002": {
                            "id": "1111-aaaa",
                            "name": "Payments",
                        }
                    }
                },
                {
                    "fields": {
                        "customfield_11002": {
                            "id": "472b84df-0340-44a7-91ee-fc748691daa7",
                            "name": "Site Reliability Engineering",
                        }
                    }
                },
            ]
        }

        with patch.object(self.client, "_request", return_value=payload) as mock_req:
            team_id = self.client.resolve_team_id_from_project_history(
                project_key="DDL",
                team_name="Site Reliability Engineering",
            )

        self.assertEqual(team_id, "472b84df-0340-44a7-91ee-fc748691daa7")
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["json"]["fields"], ["customfield_11002"])

    def test_resolve_team_id_from_project_history_raises_when_not_found(self):
        payload = {
            "issues": [
                {
                    "fields": {
                        "customfield_11002": {
                            "id": "1111-aaaa",
                            "name": "Payments",
                        }
                    }
                }
            ]
        }
        with patch.object(self.client, "_request", return_value=payload):
            with self.assertRaises(JiraValidationError):
                self.client.resolve_team_id_from_project_history(
                    project_key="DDL",
                    team_name="Site Reliability Engineering",
                )

    def test_set_issue_team_with_direct_team_id_updates_and_verifies(self):
        with patch.object(self.client, "update_issue", return_value={}) as mock_update:
            with patch.object(
                self.client,
                "get_issue",
                return_value={
                    "fields": {
                        "customfield_11002": {
                            "id": "472b84df-0340-44a7-91ee-fc748691daa7",
                            "name": "Site Reliability Engineering",
                        }
                    }
                },
            ) as mock_get:
                result = self.client.set_issue_team(
                    issue_key="DDL-1",
                    team_id="472b84df-0340-44a7-91ee-fc748691daa7",
                )

        self.assertEqual(result["team_id"], "472b84df-0340-44a7-91ee-fc748691daa7")
        self.assertEqual(result["team_name"], "Site Reliability Engineering")
        mock_update.assert_called_once_with(
            "DDL-1",
            fields={"customfield_11002": "472b84df-0340-44a7-91ee-fc748691daa7"},
        )
        mock_get.assert_called_once_with("DDL-1", fields=["customfield_11002"])

    def test_set_issue_team_resolves_from_name_when_team_id_missing(self):
        with patch.object(
            self.client,
            "resolve_team_id_from_project_history",
            return_value="472b84df-0340-44a7-91ee-fc748691daa7",
        ) as mock_resolve:
            with patch.object(self.client, "update_issue", return_value={}):
                with patch.object(
                    self.client,
                    "get_issue",
                    return_value={
                        "fields": {
                            "customfield_11002": {
                                "id": "472b84df-0340-44a7-91ee-fc748691daa7",
                                "name": "Site Reliability Engineering",
                            }
                        }
                    },
                ):
                    result = self.client.set_issue_team(
                        issue_key="DDL-2",
                        team_name="Site Reliability Engineering",
                        project_key="DDL",
                    )

        self.assertEqual(result["team_id"], "472b84df-0340-44a7-91ee-fc748691daa7")
        mock_resolve.assert_called_once_with(
            project_key="DDL",
            team_name="Site Reliability Engineering",
        )

    def test_set_issue_team_raises_on_verification_mismatch(self):
        with patch.object(self.client, "update_issue", return_value={}):
            with patch.object(
                self.client,
                "get_issue",
                return_value={
                    "fields": {
                        "customfield_11002": {
                            "id": "different-id",
                            "name": "Different Team",
                        }
                    }
                },
            ):
                with self.assertRaises(JiraValidationError):
                    self.client.set_issue_team(
                        issue_key="DDL-3",
                        team_id="472b84df-0340-44a7-91ee-fc748691daa7",
                    )


if __name__ == "__main__":
    unittest.main()
