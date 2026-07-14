"""Tests for azuregit_env.py — AzureGit authentication config loading."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = PROJECT_ROOT / ".github" / "skills" / "azuregit-authentication"
if str(AUTH_PATH) not in sys.path:
    sys.path.insert(0, str(AUTH_PATH))

from azuregit_env import (  # noqa: E402
    AzureGitAuthConfig,
    AzureGitAuthConfigError,
    _normalize_api_version,
    _parse_projects,
    load_azuregit_auth_config_from_env,
)


VALID_ENV = {
    "AZURE_ORG": "my-org",
    "AZURE_PROJECT": "project_1,project_2",
    "AZURE_PAT": "pat-value",
}


class TestAzureGitAuthConfigConstruction(unittest.TestCase):
    def test_stores_fields(self) -> None:
        cfg = AzureGitAuthConfig(
            organization="my-org",
            projects=["project_1", "project_2"],
            pat="pat-value",
            api_version="7.1",
        )
        self.assertEqual(cfg.organization, "my-org")
        self.assertEqual(cfg.projects, ["project_1", "project_2"])
        self.assertEqual(cfg.api_version, "7.1")


class TestParseProjects(unittest.TestCase):
    def test_single_project(self) -> None:
        self.assertEqual(_parse_projects("project_1"), ["project_1"])

    def test_multiple_projects(self) -> None:
        self.assertEqual(
            _parse_projects("project_1,project_2,project_3"),
            ["project_1", "project_2", "project_3"],
        )

    def test_strips_whitespace(self) -> None:
        self.assertEqual(
            _parse_projects("  project_1 ,  project_2  "),
            ["project_1", "project_2"],
        )

    def test_deduplicates(self) -> None:
        self.assertEqual(
            _parse_projects("project_1,project_2,project_1"),
            ["project_1", "project_2"],
        )

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(_parse_projects(""), [])


class TestNormalizeApiVersion(unittest.TestCase):
    def test_defaults_to_7_1_when_empty(self) -> None:
        self.assertEqual(_normalize_api_version(""), "7.1")

    def test_trims_value(self) -> None:
        self.assertEqual(_normalize_api_version(" 7.2-preview.1 "), "7.2-preview.1")


class TestLoadAzureGitAuthConfigFromEnv(unittest.TestCase):
    def test_missing_org_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "AZURE_ORG"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(AzureGitAuthConfigError):
                load_azuregit_auth_config_from_env()

    def test_missing_project_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "AZURE_PROJECT"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(AzureGitAuthConfigError):
                load_azuregit_auth_config_from_env()

    def test_missing_pat_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "AZURE_PAT"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(AzureGitAuthConfigError):
                load_azuregit_auth_config_from_env()

    def test_empty_parsed_projects_raises(self) -> None:
        env = {**VALID_ENV, "AZURE_PROJECT": " ,  , "}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(AzureGitAuthConfigError):
                load_azuregit_auth_config_from_env()

    def test_valid_config_builds(self) -> None:
        with patch.dict(os.environ, VALID_ENV, clear=True):
            cfg = load_azuregit_auth_config_from_env()
        self.assertEqual(cfg.organization, "my-org")
        self.assertEqual(cfg.projects, ["project_1", "project_2"])
        self.assertEqual(cfg.api_version, "7.1")

    def test_api_version_override(self) -> None:
        env = {**VALID_ENV, "AZURE_API_VERSION": "7.2-preview.1"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_azuregit_auth_config_from_env()
        self.assertEqual(cfg.api_version, "7.2-preview.1")


if __name__ == "__main__":
    unittest.main()
