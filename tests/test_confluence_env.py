"""Tests for confluence_env.py — Confluence authentication config loading."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = PROJECT_ROOT / ".github" / "skills" / "confluence-authentication"
if str(AUTH_PATH) not in sys.path:
    sys.path.insert(0, str(AUTH_PATH))

from confluence_env import (
    ConfluenceAuthConfig,
    ConfluenceAuthConfigError,
    load_confluence_auth_config_from_env,
)

VALID_ENV = {
    "JIRA_HOST": "https://example.atlassian.net",
    "JIRA_USERNAME": "alice@example.com",
    "JIRA_API_TOKEN": "mytoken123",
    "CONFLUENCE_SPACE_KEY": "ENG",
}


class TestConfluenceAuthConfigConstruction(unittest.TestCase):
    """Direct construction of ConfluenceAuthConfig."""

    def test_stores_host(self) -> None:
        cfg = ConfluenceAuthConfig("https://example.atlassian.net", "u", "tok", ["ENG"])
        self.assertEqual(cfg.host, "https://example.atlassian.net")

    def test_stores_username(self) -> None:
        cfg = ConfluenceAuthConfig("https://example.atlassian.net", "alice", "tok", ["ENG"])
        self.assertEqual(cfg.username, "alice")

    def test_stores_api_token(self) -> None:
        cfg = ConfluenceAuthConfig("https://example.atlassian.net", "u", "secret", ["ENG"])
        self.assertEqual(cfg.api_token, "secret")

    def test_stores_space_keys(self) -> None:
        cfg = ConfluenceAuthConfig("https://example.atlassian.net", "u", "tok", ["ENG", "OPS"])
        self.assertEqual(cfg.space_keys, ["ENG", "OPS"])


class TestLoadConfluenceAuthConfigMissingFields(unittest.TestCase):
    """load_confluence_auth_config_from_env raises on missing fields."""

    def test_missing_host_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "JIRA_HOST"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfluenceAuthConfigError):
                load_confluence_auth_config_from_env()

    def test_missing_username_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "JIRA_USERNAME"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfluenceAuthConfigError):
                load_confluence_auth_config_from_env()

    def test_missing_api_token_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "JIRA_API_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfluenceAuthConfigError):
                load_confluence_auth_config_from_env()

    def test_missing_space_key_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "CONFLUENCE_SPACE_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfluenceAuthConfigError):
                load_confluence_auth_config_from_env()


class TestLoadConfluenceAuthConfigValidation(unittest.TestCase):
    """load_confluence_auth_config_from_env validates host scheme."""

    def test_invalid_host_scheme_raises(self) -> None:
        env = {**VALID_ENV, "JIRA_HOST": "ftp://example.atlassian.net"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfluenceAuthConfigError):
                load_confluence_auth_config_from_env()

    def test_host_without_scheme_raises(self) -> None:
        env = {**VALID_ENV, "JIRA_HOST": "example.atlassian.net"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfluenceAuthConfigError):
                load_confluence_auth_config_from_env()


class TestLoadConfluenceAuthConfigSuccess(unittest.TestCase):
    """load_confluence_auth_config_from_env returns correct config."""

    def test_valid_config_single_space_key(self) -> None:
        with patch.dict(os.environ, VALID_ENV, clear=True):
            cfg = load_confluence_auth_config_from_env()
        self.assertEqual(cfg.host, "https://example.atlassian.net")
        self.assertEqual(cfg.username, "alice@example.com")
        self.assertEqual(cfg.api_token, "mytoken123")
        self.assertIn("ENG", cfg.space_keys)

    def test_valid_config_multiple_space_keys_uppercased(self) -> None:
        env = {**VALID_ENV, "CONFLUENCE_SPACE_KEY": "eng,ops,dev"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_confluence_auth_config_from_env()
        self.assertEqual(cfg.space_keys, ["ENG", "OPS", "DEV"])

    def test_host_trailing_slash_stripped(self) -> None:
        env = {**VALID_ENV, "JIRA_HOST": "https://example.atlassian.net/"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_confluence_auth_config_from_env()
        self.assertFalse(cfg.host.endswith("/"))

    def test_space_keys_whitespace_trimmed_and_uppercased(self) -> None:
        env = {**VALID_ENV, "CONFLUENCE_SPACE_KEY": "  eng , ops  "}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_confluence_auth_config_from_env()
        self.assertEqual(cfg.space_keys, ["ENG", "OPS"])

    def test_http_scheme_accepted(self) -> None:
        env = {**VALID_ENV, "JIRA_HOST": "http://example.atlassian.net"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_confluence_auth_config_from_env()
        self.assertTrue(cfg.host.startswith("http://"))


if __name__ == "__main__":
    unittest.main()
