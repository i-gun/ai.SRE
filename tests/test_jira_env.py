"""Tests for jira_env.py — Jira authentication config loading."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = PROJECT_ROOT / ".github" / "skills" / "jira-authentication"
if str(AUTH_PATH) not in sys.path:
    sys.path.insert(0, str(AUTH_PATH))

from jira_env import JiraAuthConfig, JiraAuthConfigError, load_jira_auth_config_from_env

VALID_ENV = {
    "JIRA_HOST": "https://example.atlassian.net",
    "JIRA_USERNAME": "alice@example.com",
    "JIRA_API_TOKEN": "mytoken123",
}


class TestJiraAuthConfigConstruction(unittest.TestCase):
    """Direct construction of JiraAuthConfig."""

    def test_stores_host(self) -> None:
        cfg = JiraAuthConfig("https://example.atlassian.net", "u", "tok")
        self.assertEqual(cfg.host, "https://example.atlassian.net")

    def test_stores_username(self) -> None:
        cfg = JiraAuthConfig("https://example.atlassian.net", "alice", "tok")
        self.assertEqual(cfg.username, "alice")

    def test_stores_api_token(self) -> None:
        cfg = JiraAuthConfig("https://example.atlassian.net", "u", "secret-token")
        self.assertEqual(cfg.api_token, "secret-token")


class TestLoadJiraAuthConfigMissingFields(unittest.TestCase):
    """load_jira_auth_config_from_env raises on missing fields."""

    def test_missing_host_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "JIRA_HOST"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(JiraAuthConfigError):
                load_jira_auth_config_from_env()

    def test_missing_username_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "JIRA_USERNAME"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(JiraAuthConfigError):
                load_jira_auth_config_from_env()

    def test_missing_api_token_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "JIRA_API_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(JiraAuthConfigError):
                load_jira_auth_config_from_env()

    def test_all_missing_raises(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(JiraAuthConfigError):
                load_jira_auth_config_from_env()


class TestLoadJiraAuthConfigValidation(unittest.TestCase):
    """load_jira_auth_config_from_env validates host scheme."""

    def test_invalid_host_scheme_raises(self) -> None:
        env = {**VALID_ENV, "JIRA_HOST": "ftp://example.atlassian.net"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(JiraAuthConfigError):
                load_jira_auth_config_from_env()

    def test_host_without_scheme_raises(self) -> None:
        env = {**VALID_ENV, "JIRA_HOST": "example.atlassian.net"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(JiraAuthConfigError):
                load_jira_auth_config_from_env()


class TestLoadJiraAuthConfigSuccess(unittest.TestCase):
    """load_jira_auth_config_from_env returns correct config."""

    def test_valid_config_constructs_correctly(self) -> None:
        with patch.dict(os.environ, VALID_ENV, clear=True):
            cfg = load_jira_auth_config_from_env()
        self.assertEqual(cfg.host, "https://example.atlassian.net")
        self.assertEqual(cfg.username, "alice@example.com")
        self.assertEqual(cfg.api_token, "mytoken123")

    def test_host_trailing_slash_stripped(self) -> None:
        env = {**VALID_ENV, "JIRA_HOST": "https://example.atlassian.net/"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_jira_auth_config_from_env()
        self.assertFalse(cfg.host.endswith("/"))

    def test_whitespace_trimmed_from_values(self) -> None:
        env = {
            "JIRA_HOST": "  https://example.atlassian.net  ",
            "JIRA_USERNAME": "  alice@example.com  ",
            "JIRA_API_TOKEN": "  mytoken123  ",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = load_jira_auth_config_from_env()
        self.assertEqual(cfg.host, "https://example.atlassian.net")
        self.assertEqual(cfg.username, "alice@example.com")
        self.assertEqual(cfg.api_token, "mytoken123")

    def test_http_scheme_accepted(self) -> None:
        env = {**VALID_ENV, "JIRA_HOST": "http://example.atlassian.net"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_jira_auth_config_from_env()
        self.assertTrue(cfg.host.startswith("http://"))


if __name__ == "__main__":
    unittest.main()
