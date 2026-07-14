"""Azure DevOps Git read-only repository discovery, code search, and analysis client."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import requests


class AzureGitConfigError(Exception):
    """Raised when AzureGit configuration is invalid."""


class AzureGitValidationError(Exception):
    """Raised when AzureGit operation inputs fail validation checks."""


class AzureGitAPIError(Exception):
    """Raised when Azure DevOps API calls fail."""


@dataclass
class AzureGitConfig:
    organization: str
    projects: List[str] = field(default_factory=list)
    pat: str = ""
    api_version: str = "7.1"

    @classmethod
    def from_env(cls) -> "AzureGitConfig":
        organization = os.getenv("AZURE_ORG", "").strip()
        projects_raw = os.getenv("AZURE_PROJECT", "").strip()
        pat = os.getenv("AZURE_PAT", "").strip()
        api_version = cls._normalize_api_version(os.getenv("AZURE_API_VERSION", ""))

        missing = [
            name
            for name, value in [
                ("AZURE_ORG", organization),
                ("AZURE_PROJECT", projects_raw),
                ("AZURE_PAT", pat),
            ]
            if not value
        ]
        if missing:
            raise AzureGitConfigError(
                "Missing required AzureGit environment variables: " + ", ".join(missing)
            )

        projects = cls._parse_projects(projects_raw)
        if not projects:
            raise AzureGitConfigError("AZURE_PROJECT must include at least one project.")

        return cls(
            organization=organization,
            projects=projects,
            pat=pat,
            api_version=api_version,
        )

    @staticmethod
    def _parse_projects(raw_value: str) -> List[str]:
        parsed: List[str] = []
        seen: Set[str] = set()
        for item in raw_value.split(","):
            value = item.strip()
            if not value or value in seen:
                continue
            parsed.append(value)
            seen.add(value)
        return parsed

    @staticmethod
    def _normalize_api_version(raw_value: str) -> str:
        value = (raw_value or "").strip()
        return value or "7.1"


class AzureGitClient:
    """Read-only Azure DevOps Git client for repository discovery and code analysis."""

    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 1000

    def __init__(self, config: AzureGitConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = ("", config.pat)
        self.session.headers.update({"Accept": "application/json"})

    @classmethod
    def from_env(cls) -> "AzureGitClient":
        return cls(AzureGitConfig.from_env())

    def _url(self, project: str, path: str) -> str:
        return f"https://dev.azure.com/{self.config.organization}/{project}/_apis{path}"

    def _request(
        self,
        method: str,
        *,
        project: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if method.upper() != "GET":
            raise AzureGitValidationError(
                "AzureGit client is read-only. Only GET operations are allowed."
            )

        try:
            response = self.session.request(
                method=method,
                url=self._url(project, path),
                params=params,
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise AzureGitAPIError(f"Azure DevOps request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = self._safe_error_detail(response)
            raise AzureGitAPIError(
                f"Azure DevOps API error ({response.status_code}): {detail}"
            )

        if not response.text.strip():
            return {}

        try:
            payload = response.json()
        except ValueError as exc:
            raise AzureGitAPIError("Azure DevOps returned non-JSON response") from exc

        if not isinstance(payload, dict):
            raise AzureGitAPIError("Azure DevOps returned an unexpected response shape")

        return payload

    @staticmethod
    def _safe_error_detail(response: requests.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text[:300] if response.text else "Unknown error"
        return str(body)[:300]

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        if limit <= 0:
            raise AzureGitValidationError("limit must be greater than zero.")
        if limit > AzureGitClient.MAX_LIMIT:
            raise AzureGitValidationError(
                f"limit must be <= {AzureGitClient.MAX_LIMIT}."
            )
        return limit

    def _resolve_projects(self, project: Optional[str]) -> List[str]:
        if project is None:
            return list(self.config.projects)
        value = project.strip()
        if not value:
            raise AzureGitValidationError("project override must not be empty.")
        if value not in self.config.projects:
            raise AzureGitValidationError(
                f"Project '{value}' is outside configured AZURE_PROJECT scope."
            )
        return [value]

    @staticmethod
    def _normalize_extensions(file_extensions: Optional[List[str]]) -> Set[str]:
        normalized: Set[str] = set()
        if not file_extensions:
            return normalized
        for ext in file_extensions:
            value = (ext or "").strip().lower()
            if not value:
                continue
            if not value.startswith("."):
                value = f".{value}"
            normalized.add(value)
        return normalized

    @staticmethod
    def _build_match_preview(content: str, query: str) -> str:
        lowered = query.lower()
        for line in content.splitlines():
            text = line.strip()
            if lowered in text.lower():
                return text[:220]
        return content.strip()[:220]

    @staticmethod
    def _file_extension(path: str) -> str:
        filename = path.rsplit("/", 1)[-1]
        if "." not in filename:
            return "<none>"
        return f".{filename.rsplit('.', 1)[-1].lower()}"

    @staticmethod
    def _top_level_dir(path: str) -> str:
        if not path or path == "/":
            return "/"
        normalized = path.lstrip("/")
        if "/" not in normalized:
            return "/"
        return normalized.split("/", 1)[0]

    def list_repositories(
        self,
        *,
        project: Optional[str] = None,
        name_contains: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
    ) -> Dict[str, List[Dict[str, Any]]]:
        bounded_limit = self._normalize_limit(limit)
        projects = self._resolve_projects(project)
        name_filter = (name_contains or "").strip().lower()

        results: Dict[str, List[Dict[str, Any]]] = {}
        for project_name in projects:
            payload = self._request(
                "GET",
                project=project_name,
                path="/git/repositories",
                params={"api-version": self.config.api_version},
            )
            repositories = payload.get("value", [])
            if not isinstance(repositories, list):
                raise AzureGitAPIError("Azure DevOps returned invalid repositories shape.")

            normalized: List[Dict[str, Any]] = []
            for repo in repositories:
                if not isinstance(repo, dict):
                    continue
                repo_name = str(repo.get("name", ""))
                if name_filter and name_filter not in repo_name.lower():
                    continue
                normalized.append(
                    {
                        "id": repo.get("id"),
                        "name": repo_name,
                        "project": project_name,
                        "defaultBranch": repo.get("defaultBranch"),
                        "size": repo.get("size"),
                        "remoteUrl": repo.get("remoteUrl"),
                        "url": repo.get("url"),
                    }
                )
                if len(normalized) >= bounded_limit:
                    break
            results[project_name] = normalized

        return results

    def get_repository(
        self,
        *,
        project: str,
        repository_id_or_name: str,
    ) -> Dict[str, Any]:
        target = (repository_id_or_name or "").strip()
        if not target:
            raise AzureGitValidationError("repository_id_or_name is required.")

        projects = self._resolve_projects(project)
        project_name = projects[0]
        payload = self._request(
            "GET",
            project=project_name,
            path=f"/git/repositories/{target}",
            params={"api-version": self.config.api_version},
        )
        return {
            "id": payload.get("id"),
            "name": payload.get("name"),
            "project": project_name,
            "defaultBranch": payload.get("defaultBranch"),
            "size": payload.get("size"),
            "remoteUrl": payload.get("remoteUrl"),
            "url": payload.get("url"),
        }

    def list_repository_items(
        self,
        *,
        project: str,
        repository_id: str,
        scope_path: str = "/",
        recursion_level: str = "Full",
        branch: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        bounded_limit = self._normalize_limit(limit)
        projects = self._resolve_projects(project)
        project_name = projects[0]
        repo_id = (repository_id or "").strip()
        if not repo_id:
            raise AzureGitValidationError("repository_id is required.")

        params: Dict[str, Any] = {
            "scopePath": scope_path or "/",
            "recursionLevel": recursion_level,
            "includeContentMetadata": "true",
            "api-version": self.config.api_version,
        }
        if branch and branch.strip():
            params["versionDescriptor.version"] = branch.strip()

        payload = self._request(
            "GET",
            project=project_name,
            path=f"/git/repositories/{repo_id}/items",
            params=params,
        )
        items = payload.get("value", [])
        if not isinstance(items, list):
            raise AzureGitAPIError("Azure DevOps returned invalid repository items shape.")

        normalized: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "path": item.get("path"),
                    "gitObjectType": item.get("gitObjectType"),
                    "size": item.get("size"),
                    "objectId": item.get("objectId"),
                    "url": item.get("url"),
                }
            )
            if len(normalized) >= bounded_limit:
                break
        return normalized

    def fetch_file_content(
        self,
        *,
        project: str,
        repository_id: str,
        file_path: str,
        branch: Optional[str] = None,
    ) -> str:
        projects = self._resolve_projects(project)
        project_name = projects[0]
        repo_id = (repository_id or "").strip()
        path = (file_path or "").strip()
        if not repo_id:
            raise AzureGitValidationError("repository_id is required.")
        if not path:
            raise AzureGitValidationError("file_path is required.")

        params: Dict[str, Any] = {
            "scopePath": path,
            "includeContent": "true",
            "resolveLfs": "true",
            "api-version": self.config.api_version,
        }
        if branch and branch.strip():
            params["versionDescriptor.version"] = branch.strip()

        payload = self._request(
            "GET",
            project=project_name,
            path=f"/git/repositories/{repo_id}/items",
            params=params,
        )
        content = payload.get("content")
        if not isinstance(content, str):
            raise AzureGitAPIError(
                f"Unable to read text content for '{path}'. File may be binary or unavailable."
            )
        return content

    def search_code(
        self,
        *,
        query: str,
        project: Optional[str] = None,
        repository_id: Optional[str] = None,
        path_prefix: Optional[str] = None,
        file_extensions: Optional[List[str]] = None,
        branch: Optional[str] = None,
        limit: int = 20,
        max_files_per_repo: int = 300,
    ) -> List[Dict[str, Any]]:
        needle = (query or "").strip()
        if not needle:
            raise AzureGitValidationError("query must not be empty.")

        bounded_limit = self._normalize_limit(limit)
        bounded_repo_scan = self._normalize_limit(max_files_per_repo)
        projects = self._resolve_projects(project)
        extensions = self._normalize_extensions(file_extensions)
        prefix = (path_prefix or "").strip().lower()

        matches: List[Dict[str, Any]] = []
        for project_name in projects:
            if repository_id and repository_id.strip():
                repositories = [self.get_repository(project=project_name, repository_id_or_name=repository_id)]
            else:
                repositories = self.list_repositories(project=project_name)[project_name]

            for repository in repositories:
                repo_id = str(repository.get("id", "")).strip()
                if not repo_id:
                    continue
                items = self.list_repository_items(
                    project=project_name,
                    repository_id=repo_id,
                    branch=branch,
                    limit=bounded_repo_scan,
                )
                for item in items:
                    if item.get("gitObjectType") != "blob":
                        continue
                    item_path = str(item.get("path", ""))
                    if not item_path:
                        continue
                    if prefix and not item_path.lower().startswith(prefix):
                        continue
                    if extensions and self._file_extension(item_path) not in extensions:
                        continue
                    try:
                        content = self.fetch_file_content(
                            project=project_name,
                            repository_id=repo_id,
                            file_path=item_path,
                            branch=branch,
                        )
                    except AzureGitAPIError:
                        continue

                    if needle.lower() not in content.lower():
                        continue
                    matches.append(
                        {
                            "project": project_name,
                            "repository": repository.get("name"),
                            "repository_id": repo_id,
                            "path": item_path,
                            "preview": self._build_match_preview(content, needle),
                            "url": item.get("url"),
                        }
                    )
                    if len(matches) >= bounded_limit:
                        return matches

        return matches

    def analyze_repository_structure(
        self,
        *,
        project: str,
        repository_id: str,
        branch: Optional[str] = None,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        items = self.list_repository_items(
            project=project,
            repository_id=repository_id,
            branch=branch,
            limit=limit,
        )
        files = [item for item in items if item.get("gitObjectType") == "blob"]

        extension_counts = Counter(self._file_extension(str(item.get("path", ""))) for item in files)
        directory_counts = Counter(
            self._top_level_dir(str(item.get("path", ""))) for item in files
        )

        return {
            "project": project,
            "repository_id": repository_id,
            "item_count": len(items),
            "file_count": len(files),
            "extensions": [
                {"extension": key, "count": value}
                for key, value in extension_counts.most_common()
            ],
            "top_directories": [
                {"directory": key, "count": value}
                for key, value in directory_counts.most_common()
            ],
        }
