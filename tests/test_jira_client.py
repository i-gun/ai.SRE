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


if __name__ == "__main__":
    unittest.main()
