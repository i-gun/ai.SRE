"""Confluence Cloud page discovery and service-flow analysis client."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from html import unescape
from typing import Any, Dict, List, Optional, Set, Tuple

import requests


class ConfluenceConfigError(Exception):
    """Raised when Confluence configuration is invalid."""


class ConfluenceValidationError(Exception):
    """Raised when Confluence operation inputs fail validation checks."""


class ConfluenceAPIError(Exception):
    """Raised when Confluence API calls fail."""


@dataclass
class ConfluenceConfig:
    host: str
    username: str
    api_token: str
    space_keys: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "ConfluenceConfig":
        host = os.getenv("JIRA_HOST", "").strip()
        username = os.getenv("JIRA_USERNAME", "").strip()
        api_token = os.getenv("JIRA_API_TOKEN", "").strip()
        space_keys_raw = os.getenv("CONFLUENCE_SPACE_KEY", "").strip()

        missing = [
            name
            for name, value in [
                ("JIRA_HOST", host),
                ("JIRA_USERNAME", username),
                ("JIRA_API_TOKEN", api_token),
                ("CONFLUENCE_SPACE_KEY", space_keys_raw),
            ]
            if not value
        ]

        if missing:
            raise ConfluenceConfigError(
                "Missing required Confluence environment variables: " + ", ".join(missing)
            )

        if not (host.startswith("https://") or host.startswith("http://")):
            raise ConfluenceConfigError("JIRA_HOST must start with http:// or https://")

        space_keys = [k.strip().upper() for k in space_keys_raw.split(",") if k.strip()]
        if not space_keys:
            raise ConfluenceConfigError(
                "CONFLUENCE_SPACE_KEY must contain at least one non-empty space key."
            )

        return cls(
            host=host.rstrip("/"),
            username=username,
            api_token=api_token,
            space_keys=space_keys,
        )


class ConfluenceClient:
    """Client wrapper for Confluence page discovery and service-flow analysis."""

    CONTENT_PATH = "/wiki/rest/api/content"
    SEARCH_PATH = "/wiki/rest/api/content/search"
    DEFAULT_TIMEOUT_SECONDS = 30

    DEFAULT_EXPAND = [
        "space",
        "version",
        "ancestors",
        "body.storage",
    ]

    SERVICE_TOKEN_BLACKLIST = {
        "a",
        "an",
        "and",
        "api",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "of",
        "on",
        "or",
        "service",
        "system",
        "the",
        "to",
        "via",
        "with",
    }

    SERVICE_NAME_PATTERNS = [
        re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:Service|API|Gateway|Worker|Processor))\b"),
        re.compile(r"\b([A-Za-z0-9._-]+-(?:service|api|gateway|worker|processor))\b", re.IGNORECASE),
    ]

    RELATION_PATTERNS = [
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+calls\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "calls"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+invokes\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "calls"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+depends on\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "depends_on"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+uses\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "depends_on"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+integrates with\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "integrates_with"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+publishes to\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "publishes_to"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+emits to\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "emits_to"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+consumes from\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "consumes_from"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+sends to\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "sends_to"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+reads from\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "reads_from"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s+writes to\s+([A-Za-z0-9._-]+)\b", re.IGNORECASE), "writes_to"),
        (re.compile(r"\b([A-Za-z0-9._-]+)\s*(?:->|=>|-->)\s*([A-Za-z0-9._-]+)\b"), "flows_to"),
    ]

    def __init__(self, config: ConfluenceConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.username, config.api_token)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def from_env(cls) -> "ConfluenceClient":
        return cls(ConfluenceConfig.from_env())

    def _url(self, path: str) -> str:
        return f"{self.config.host}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            response = self.session.request(
                method=method,
                url=self._url(path),
                params=params,
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise ConfluenceAPIError(f"Confluence request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = self._safe_error_detail(response)
            raise ConfluenceAPIError(
                f"Confluence API error ({response.status_code}): {detail}"
            )

        if response.status_code == 204 or not response.text.strip():
            return {}

        try:
            payload = response.json()
        except ValueError as exc:
            raise ConfluenceAPIError("Confluence returned non-JSON response") from exc

        if not isinstance(payload, dict):
            raise ConfluenceAPIError("Confluence returned an unexpected response shape")

        return payload

    @staticmethod
    def _safe_error_detail(response: requests.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text[:300] if response.text else "Unknown error"

        if isinstance(body, dict):
            messages: List[str] = []
            message = body.get("message")
            if message:
                messages.append(str(message))

            data = body.get("data")
            if isinstance(data, dict):
                authorized = data.get("authorized")
                if authorized is False:
                    messages.append("Request was not authorized")

            if messages:
                return "; ".join(messages)

            return str(body)

        return str(body)

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        if limit <= 0:
            raise ConfluenceValidationError("Limit must be greater than zero.")
        return limit

    @staticmethod
    def _normalize_page_id(page_id: str) -> str:
        normalized = page_id.strip()
        if not normalized:
            raise ConfluenceValidationError("Page ID is required.")
        return normalized

    @staticmethod
    def _normalize_cql(cql: str) -> str:
        normalized = cql.strip()
        if not normalized:
            raise ConfluenceValidationError("CQL is required for content search.")
        return normalized

    def list_space_pages(
        self,
        *,
        limit: int = 25,
        start: int = 0,
        space_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if start < 0:
            raise ConfluenceValidationError("Start offset must be zero or positive.")

        keys = [space_key.strip().upper()] if space_key else self.config.space_keys
        all_results: List[Dict[str, Any]] = []

        for key in keys:
            payload = self._request(
                "GET",
                self.CONTENT_PATH,
                params={
                    "spaceKey": key,
                    "type": "page",
                    "limit": self._normalize_limit(limit),
                    "start": start,
                    "expand": ",".join(["space", "version"]),
                },
            )
            results = payload.get("results", [])
            if not isinstance(results, list):
                raise ConfluenceAPIError("Confluence content list returned unexpected shape")
            all_results.extend(results)

        return all_results

    def search_content(self, *, cql: str, limit: int = 25, start: int = 0) -> List[Dict[str, Any]]:
        if start < 0:
            raise ConfluenceValidationError("Start offset must be zero or positive.")

        scoped_cql = self._scope_cql_to_space(self._normalize_cql(cql))
        payload = self._request(
            "GET",
            self.SEARCH_PATH,
            params={
                "cql": scoped_cql,
                "limit": self._normalize_limit(limit),
                "start": start,
                "expand": "content.space,content.version",
            },
        )
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise ConfluenceAPIError("Confluence content search returned unexpected shape")
        return results

    def get_page(
        self,
        *,
        page_id: str,
        expand: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        normalized_page_id = self._normalize_page_id(page_id)
        return self._request(
            "GET",
            f"{self.CONTENT_PATH}/{normalized_page_id}",
            params={"expand": ",".join(expand or self.DEFAULT_EXPAND)},
        )

    def find_page_by_title(self, *, title: str, space_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        normalized_title = title.strip()
        if not normalized_title:
            raise ConfluenceValidationError("Title is required.")

        keys = [space_key.strip().upper()] if space_key else self.config.space_keys

        for key in keys:
            payload = self._request(
                "GET",
                self.CONTENT_PATH,
                params={
                    "spaceKey": key,
                    "type": "page",
                    "title": normalized_title,
                    "expand": "space,version",
                    "limit": 1,
                },
            )
            results = payload.get("results", [])
            if not isinstance(results, list):
                raise ConfluenceAPIError("Confluence page lookup returned unexpected shape")
            if results:
                return results[0]

        return None

    def extract_service_relationships(
        self,
        *,
        page_ids: Optional[List[str]] = None,
        pages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        normalized_pages = self._resolve_pages_for_analysis(page_ids=page_ids, pages=pages)

        services: Set[str] = set()
        edges: List[Dict[str, Any]] = []

        for page in normalized_pages:
            page_id = str(page.get("id", ""))
            title = str(page.get("title", "Untitled"))
            body = self._extract_storage_body(page)
            text = self._to_text(body)

            services.update(self._extract_service_names(text))

            for pattern, relation in self.RELATION_PATTERNS:
                for match in pattern.finditer(text):
                    source = self._normalize_service_label(match.group(1))
                    target = self._normalize_service_label(match.group(2))
                    if not self._is_service_like(source) or not self._is_service_like(target):
                        continue
                    services.add(source)
                    services.add(target)
                    edges.append(
                        {
                            "from": source,
                            "to": target,
                            "relation": relation,
                            "evidence": {
                                "page_id": page_id,
                                "page_title": title,
                                "excerpt": match.group(0),
                            },
                        }
                    )

        unique_edges = self._deduplicate_edges(edges)

        return {
            "space_keys": self.config.space_keys,
            "services": sorted(services),
            "edges": unique_edges,
            "page_count": len(normalized_pages),
        }

    def build_service_flow_graph(
        self,
        *,
        page_ids: Optional[List[str]] = None,
        pages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        relationships = self.extract_service_relationships(page_ids=page_ids, pages=pages)
        services = relationships["services"]
        edges = relationships["edges"]

        adjacency: Dict[str, List[str]] = {service: [] for service in services}
        for edge in edges:
            adjacency.setdefault(edge["from"], [])
            if edge["to"] not in adjacency[edge["from"]]:
                adjacency[edge["from"]].append(edge["to"])

        isolated_nodes = [
            node
            for node, outgoing in adjacency.items()
            if not outgoing and node not in {edge["to"] for edge in edges}
        ]

        mermaid_lines = ["flowchart LR"]
        for edge in edges:
            label = edge["relation"].replace("_", " ")
            mermaid_lines.append(f"    {self._node_id(edge['from'])}[\"{edge['from']}\"] -->|{label}| {self._node_id(edge['to'])}[\"{edge['to']}\"]")

        if len(mermaid_lines) == 1:
            mermaid_lines.append("    EmptyGraph[\"No service relationships detected\"]")

        return {
            "space_keys": self.config.space_keys,
            "nodes": services,
            "edges": edges,
            "adjacency": adjacency,
            "summary": {
                "node_count": len(services),
                "edge_count": len(edges),
                "isolated_nodes": isolated_nodes,
            },
            "mermaid": "\n".join(mermaid_lines),
        }

    def _resolve_pages_for_analysis(
        self,
        *,
        page_ids: Optional[List[str]] = None,
        pages: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if pages is not None:
            if not pages:
                raise ConfluenceValidationError("Pages list cannot be empty.")
            return pages

        if not page_ids:
            raise ConfluenceValidationError(
                "Provide page_ids or pre-fetched pages for relationship analysis."
            )

        resolved_pages: List[Dict[str, Any]] = []
        for page_id in page_ids:
            resolved_pages.append(self.get_page(page_id=page_id))
        return resolved_pages

    def _scope_cql_to_space(self, cql: str) -> str:
        if re.search(r"\bspace\s*=", cql, flags=re.IGNORECASE):
            return cql
        if len(self.config.space_keys) == 1:
            return f'space = "{self.config.space_keys[0]}" AND ({cql})'
        space_clauses = " OR ".join(f'space = "{key}"' for key in self.config.space_keys)
        return f"({space_clauses}) AND ({cql})"

    @staticmethod
    def _extract_storage_body(page: Dict[str, Any]) -> str:
        body = page.get("body")
        if not isinstance(body, dict):
            return ""

        storage = body.get("storage")
        if not isinstance(storage, dict):
            return ""

        value = storage.get("value")
        if not isinstance(value, str):
            return ""

        return value

    @staticmethod
    def _to_text(storage_body: str) -> str:
        text = re.sub(r"<[^>]+>", " ", storage_body)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_service_names(self, text: str) -> Set[str]:
        names: Set[str] = set()
        for pattern in self.SERVICE_NAME_PATTERNS:
            for match in pattern.finditer(text):
                candidate = self._normalize_service_label(match.group(1))
                if self._is_service_like(candidate):
                    names.add(candidate)
        return names

    @staticmethod
    def _normalize_service_label(raw: str) -> str:
        normalized = raw.strip().strip(".,:;()[]{}<>'\"")
        normalized = re.sub(r"\s+", "", normalized) if " " in normalized else normalized
        return normalized

    @classmethod
    def _is_service_like(cls, token: str) -> bool:
        lowered = token.lower()
        if not token:
            return False
        if lowered in cls.SERVICE_TOKEN_BLACKLIST:
            return False
        if lowered.isdigit():
            return False
        # Accept identifiers with common service suffixes or mixed-case/hyphenated names.
        if re.search(r"(service|api|gateway|worker|processor|bus)$", lowered):
            return True
        if any(ch.isupper() for ch in token[1:]):
            return True
        if "-" in token or "_" in token:
            return True
        return len(token) >= 5

    @staticmethod
    def _node_id(label: str) -> str:
        compact = re.sub(r"[^A-Za-z0-9_]", "_", label)
        if not compact:
            return "node"
        if compact[0].isdigit():
            compact = f"n_{compact}"
        return compact

    @staticmethod
    def _deduplicate_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: Set[Tuple[str, str, str, str]] = set()
        unique: List[Dict[str, Any]] = []

        for edge in edges:
            evidence = edge.get("evidence", {})
            key = (
                edge.get("from", ""),
                edge.get("to", ""),
                edge.get("relation", ""),
                str(evidence.get("page_id", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(edge)

        return unique
