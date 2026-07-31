"""Unit tests for AzureGit config parsing and read-only client helper behavior."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = PROJECT_ROOT / ".github" / "skills" / "azuregit-repository-operations"
if str(CLIENT_PATH) not in sys.path:
    sys.path.insert(0, str(CLIENT_PATH))

from azuregit_client import (  # noqa: E402
    AzureGitClient,
    AzureGitConfig,
    AzureGitConfigError,
    AzureGitValidationError,
)


VALID_ENV = {
    "AZURE_ORG": "my-org",
    "AZURE_PROJECT": "project_1,project_2",
    "AZURE_PAT": "pat-value",
}


def _make_client() -> AzureGitClient:
    return AzureGitClient(
        AzureGitConfig(
            organization="my-org",
            projects=["project_1", "project_2"],
            pat="pat-value",
            api_version="7.1",
        )
    )


class TestAzureGitConfig(unittest.TestCase):
    def test_from_env_valid(self) -> None:
        with patch.dict(os.environ, VALID_ENV, clear=True):
            cfg = AzureGitConfig.from_env()
        self.assertEqual(cfg.organization, "my-org")
        self.assertEqual(cfg.projects, ["project_1", "project_2"])
        self.assertEqual(cfg.api_version, "7.1")

    def test_from_env_missing_org_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "AZURE_ORG"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(AzureGitConfigError):
                AzureGitConfig.from_env()

    def test_from_env_missing_project_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "AZURE_PROJECT"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(AzureGitConfigError):
                AzureGitConfig.from_env()

    def test_from_env_missing_pat_raises(self) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != "AZURE_PAT"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(AzureGitConfigError):
                AzureGitConfig.from_env()

    def test_from_env_api_version_override(self) -> None:
        env = {**VALID_ENV, "AZURE_API_VERSION": "7.2-preview.1"}
        with patch.dict(os.environ, env, clear=True):
            cfg = AzureGitConfig.from_env()
        self.assertEqual(cfg.api_version, "7.2-preview.1")


class TestAzureGitClientValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _make_client()

    def test_resolve_projects_without_override(self) -> None:
        self.assertEqual(
            self.client._resolve_projects(None),
            ["project_1", "project_2"],
        )

    def test_resolve_projects_with_valid_override(self) -> None:
        self.assertEqual(self.client._resolve_projects("project_2"), ["project_2"])

    def test_resolve_projects_out_of_scope_raises(self) -> None:
        with self.assertRaises(AzureGitValidationError):
            self.client._resolve_projects("project_3")

    def test_normalize_limit_rejects_zero(self) -> None:
        with self.assertRaises(AzureGitValidationError):
            AzureGitClient._normalize_limit(0)

    def test_normalize_limit_rejects_too_large(self) -> None:
        with self.assertRaises(AzureGitValidationError):
            AzureGitClient._normalize_limit(5000)

    def test_normalize_extensions(self) -> None:
        exts = AzureGitClient._normalize_extensions(["py", ".md", "  JS  "])
        self.assertEqual(exts, {".py", ".md", ".js"})

    def test_build_match_preview_returns_matching_line(self) -> None:
        content = "first line\nimportant marker line\nlast line"
        preview = AzureGitClient._build_match_preview(content, "marker")
        self.assertEqual(preview, "important marker line")

    def test_file_extension_detection(self) -> None:
        self.assertEqual(AzureGitClient._file_extension("/a/b/main.py"), ".py")
        self.assertEqual(AzureGitClient._file_extension("/README"), "<none>")

    def test_top_level_dir_detection(self) -> None:
        self.assertEqual(AzureGitClient._top_level_dir("/src/app/main.py"), "src")
        self.assertEqual(AzureGitClient._top_level_dir("/README.md"), "/")

    def test_search_code_empty_query_raises(self) -> None:
        with self.assertRaises(AzureGitValidationError):
            self.client.search_code(query="   ")


class TestAzureGitClientRepositoryMethods(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _make_client()

    @patch.object(AzureGitClient, "_request")
    def test_list_repositories_applies_name_filter(self, mock_request) -> None:
        mock_request.return_value = {
            "value": [
                {"id": "1", "name": "core-api", "defaultBranch": "refs/heads/main"},
                {"id": "2", "name": "web-portal", "defaultBranch": "refs/heads/main"},
            ]
        }

        result = self.client.list_repositories(project="project_1", name_contains="core")
        repos = result["project_1"]

        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0]["name"], "core-api")

    @patch.object(AzureGitClient, "list_repository_items")
    @patch.object(AzureGitClient, "fetch_file_content")
    @patch.object(AzureGitClient, "list_repositories")
    def test_search_code_returns_matches(
        self,
        mock_list_repositories,
        mock_fetch_file_content,
        mock_list_repository_items,
    ) -> None:
        mock_list_repositories.return_value = {
            "project_1": [{"id": "repo-1", "name": "repo-name"}]
        }
        mock_list_repository_items.return_value = [
            {"path": "/src/app.py", "gitObjectType": "blob", "url": "u1"},
            {"path": "/README.md", "gitObjectType": "blob", "url": "u2"},
        ]
        mock_fetch_file_content.side_effect = [
            "raise ValueError('target marker here')",
            "No match here",
        ]

        result = self.client.search_code(query="target marker", project="project_1")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["path"], "/src/app.py")


class TestAzureGitRepositoryMap(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _make_client()

    @patch.object(AzureGitClient, "list_repositories")
    def test_generate_repository_map_returns_expected_shape(self, mock_list_repositories) -> None:
        mock_list_repositories.return_value = {
            "project_1": [
                {
                    "id": "repo-1",
                    "name": "repo-one",
                    "defaultBranch": "refs/heads/main",
                    "size": 123,
                    "remoteUrl": "https://example/repo-one",
                }
            ]
        }

        mapping = self.client.generate_repository_map()

        self.assertEqual(mapping["organization"], "my-org")
        self.assertIn("generated_at", mapping)
        self.assertIn("project_1", mapping["projects"])
        self.assertEqual(mapping["projects"]["project_1"][0]["name"], "repo-one")

    @patch.object(AzureGitClient, "generate_repository_map")
    def test_ensure_repository_map_uses_fresh_cache(self, mock_generate_repository_map) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "map.json"
            fresh = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "organization": "my-org",
                "projects": {"project_1": []},
            }
            output.write_text(json.dumps(fresh), encoding="utf-8")

            mapping = self.client.ensure_repository_map(
                output_file=output,
                force_refresh=False,
                max_age_hours=24,
            )

        self.assertEqual(mapping["organization"], "my-org")
        mock_generate_repository_map.assert_not_called()

    @patch.object(AzureGitClient, "generate_repository_map")
    def test_ensure_repository_map_refreshes_when_stale(self, mock_generate_repository_map) -> None:
        stale = {
            "generated_at": (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
            "organization": "my-org",
            "projects": {"project_1": []},
        }
        refreshed = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "organization": "my-org",
            "projects": {"project_1": [{"id": "new"}]},
        }
        mock_generate_repository_map.return_value = refreshed

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "map.json"
            output.write_text(json.dumps(stale), encoding="utf-8")

            mapping = self.client.ensure_repository_map(
                output_file=output,
                force_refresh=False,
                max_age_hours=1,
            )

            persisted = output.read_text(encoding="utf-8")

        self.assertEqual(mapping["projects"]["project_1"][0]["id"], "new")
        self.assertIn('"id": "new"', persisted)
        mock_generate_repository_map.assert_called_once()


if __name__ == "__main__":
    unittest.main()
