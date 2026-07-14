"""Tests for servicenow_env.py — ServiceNow authentication config loading."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = PROJECT_ROOT / ".github" / "skills" / "servicenow-authentication"
if str(AUTH_PATH) not in sys.path:
    sys.path.insert(0, str(AUTH_PATH))

from servicenow_env import (
    ServiceNowAuthConfig,
    ServiceNowAuthConfigError,
    _parse_assignment_groups,
    load_servicenow_auth_config_from_env,
)

VALID_ENV = {
    "SERVICENOW_HOST": "https://example.service-now.com",
    "SERVICENOW_USERNAME": "admin",
    "SERVICENOW_PASSWORD": "secret",
    "SERVICENOW_ASSIGNMENT_GROUPS": "IT Support",
}


class TestServiceNowAuthConfigConstruction(unittest.TestCase):
    """Direct construction of ServiceNowAuthConfig."""

    def test_stores_host(self) -> None:
        cfg = ServiceNowAuthConfig("https://host.example.com", "u", "p", ["G1"])
        self.assertEqual(cfg.host, "https://host.example.com")

    def test_stores_username(self) -> None:
        cfg = ServiceNowAuthConfig("https://host.example.com", "alice", "p", ["G1"])
        self.assertEqual(cfg.username, "alice")

    def test_stores_password(self) -> None:
        cfg = ServiceNowAuthConfig("https://host.example.com", "u", "hunter2", ["G1"])
        self.assertEqual(cfg.password, "hunter2")

    def test_stores_assignment_groups(self) -> None:
        cfg = ServiceNowAuthConfig("https://host.example.com", "u", "p", ["G1", "G2"])
        self.assertEqual(cfg.assignment_groups, ["G1", "G2"])


class TestParseAssignmentGroups(unittest.TestCase):
    """Tests for _parse_assignment_groups."""

    def test_single_group(self) -> None:
        self.assertEqual(_parse_assignment_groups("IT Support"), ["IT Support"])

    def test_multiple_groups(self) -> None:
        result = _parse_assignment_groups("G1,G2,G3")
        self.assertEqual(result, ["G1", "G2", "G3"])

    def test_whitespace_around_commas(self) -> None:
        result = _parse_assignment_groups("  G1 , G2 , G3  ")
        self.assertEqual(result, ["G1", "G2", "G3"])

    def test_deduplication(self) -> None:
        result = _parse_assignment_groups("G1,G2,G1")
        self.assertEqual(len(result), 2)
        self.assertIn("G1", result)
        self.assertIn("G2", result)

    def test_empty_string_returns_empty_list(self) -> None:
        self.assertEqual(_parse_assignment_groups(""), [])


class TestLoadServiceNowAuthConfigMissingFields(unittest.TestCase):
    """load_servicenow_auth_config_from_env raises on missing fields."""

    def test_missing_host_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "SERVICENOW_HOST"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ServiceNowAuthConfigError):
                load_servicenow_auth_config_from_env()

    def test_missing_username_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "SERVICENOW_USERNAME"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ServiceNowAuthConfigError):
                load_servicenow_auth_config_from_env()

    def test_missing_password_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "SERVICENOW_PASSWORD"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ServiceNowAuthConfigError):
                load_servicenow_auth_config_from_env()

    def test_missing_assignment_groups_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "SERVICENOW_ASSIGNMENT_GROUPS"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ServiceNowAuthConfigError):
                load_servicenow_auth_config_from_env()

    def test_all_missing_raises(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ServiceNowAuthConfigError):
                load_servicenow_auth_config_from_env()


class TestLoadServiceNowAuthConfigValidation(unittest.TestCase):
    """load_servicenow_auth_config_from_env validates host scheme."""

    def test_invalid_host_scheme_raises(self) -> None:
        env = {**VALID_ENV, "SERVICENOW_HOST": "ftp://example.service-now.com"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ServiceNowAuthConfigError):
                load_servicenow_auth_config_from_env()

    def test_host_without_scheme_raises(self) -> None:
        env = {**VALID_ENV, "SERVICENOW_HOST": "example.service-now.com"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ServiceNowAuthConfigError):
                load_servicenow_auth_config_from_env()


class TestLoadServiceNowAuthConfigSuccess(unittest.TestCase):
    """load_servicenow_auth_config_from_env returns correct config."""

    def test_valid_config_constructs_correctly(self) -> None:
        with patch.dict(os.environ, VALID_ENV, clear=True):
            cfg = load_servicenow_auth_config_from_env()
        self.assertEqual(cfg.host, "https://example.service-now.com")
        self.assertEqual(cfg.username, "admin")
        self.assertEqual(cfg.password, "secret")
        self.assertIn("IT Support", cfg.assignment_groups)

    def test_host_trailing_slash_stripped(self) -> None:
        env = {**VALID_ENV, "SERVICENOW_HOST": "https://example.service-now.com/"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_servicenow_auth_config_from_env()
        self.assertFalse(cfg.host.endswith("/"))

    def test_assignment_groups_parsed_correctly(self) -> None:
        env = {**VALID_ENV, "SERVICENOW_ASSIGNMENT_GROUPS": "G1, G2, G3"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_servicenow_auth_config_from_env()
        self.assertEqual(cfg.assignment_groups, ["G1", "G2", "G3"])

    def test_http_scheme_accepted(self) -> None:
        env = {**VALID_ENV, "SERVICENOW_HOST": "http://example.service-now.com"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_servicenow_auth_config_from_env()
        self.assertTrue(cfg.host.startswith("http://"))


if __name__ == "__main__":
    unittest.main()
