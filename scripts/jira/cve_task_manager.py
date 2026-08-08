#!/usr/bin/env python3
"""Reusable Jira CVE task utilities (search, probe, bulk close)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from bootstrap_shared import bootstrap_paths

JIRA_SKILL_PATH = PROJECT_ROOT / ".github" / "skills" / "jira-issue-operations"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage Jira CVE tickets with safe defaults")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search Jira issues by CVE identifier")
    search.add_argument("--cve", required=True, help="CVE identifier, for example CVE-2026-12345")
    search.add_argument("--project", default=None, help="Optional project key filter")
    search.add_argument("--issue-type", default="Task", help="Issue type filter (default: Task)")
    search.add_argument("--max-results", type=int, default=50, help="Maximum results to return")

    probe = subparsers.add_parser("probe", help="List available transitions and resolutions")
    probe.add_argument("--issue-key", required=True, help="Issue key to inspect, for example DDL-123")

    bulk = subparsers.add_parser("bulk-close", help="Dry-run or close a batch of issues")
    bulk.add_argument("--issue-key", action="append", dest="issue_keys", default=[], help="Issue key (repeatable)")
    bulk.add_argument("--issue-file", default=None, help="File with one issue key per line")
    bulk.add_argument("--duplicate-of", required=True, help="Duplicate reference issue key, for example DDL-40243")
    bulk.add_argument("--execute", action="store_true", help="Apply changes. Default is dry-run.")
    bulk.add_argument("--sleep-ms", type=int, default=250, help="Delay between write calls when executing")

    return parser.parse_args(argv)


def load_config() -> Tuple[str, HTTPBasicAuth]:
    bootstrap_paths(skill_paths=[JIRA_SKILL_PATH], override_env=True)

    host = os.getenv("JIRA_HOST", "").strip().rstrip("/")
    username = os.getenv("JIRA_USERNAME", "").strip()
    api_token = os.getenv("JIRA_API_TOKEN", "").strip()

    missing = [
        name
        for name, value in [
            ("JIRA_HOST", host),
            ("JIRA_USERNAME", username),
            ("JIRA_API_TOKEN", api_token),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing Jira credentials: {', '.join(missing)}")

    return host, HTTPBasicAuth(username, api_token)


def request_json(
    method: str,
    host: str,
    auth: HTTPBasicAuth,
    path: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"

    response = requests.request(
        method,
        f"{host}{path}",
        auth=auth,
        headers=headers,
        json=payload,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    if not response.text:
        return {}
    return response.json()


def run_search(args: argparse.Namespace, host: str, auth: HTTPBasicAuth) -> Dict[str, Any]:
    clauses = [f'summary ~ "{args.cve}"']
    if args.issue_type:
        clauses.insert(0, f'issuetype = "{args.issue_type}"')
    if args.project:
        clauses.insert(0, f'project = "{args.project.upper()}"')
    jql = " AND ".join(clauses) + " ORDER BY updated DESC"

    payload = {
        "jql": jql,
        "maxResults": args.max_results,
        "fields": ["summary", "status", "assignee", "priority", "updated", "issuetype", "labels", "parent", "issuelinks"],
    }
    data = request_json("POST", host, auth, "/rest/api/3/search/jql", payload=payload)

    rows: List[Dict[str, Any]] = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        links = fields.get("issuelinks") or []
        linked_keys = []
        for link in links:
            inward = (link.get("inwardIssue") or {}).get("key")
            outward = (link.get("outwardIssue") or {}).get("key")
            if inward:
                linked_keys.append(inward)
            if outward:
                linked_keys.append(outward)
        rows.append(
            {
                "key": issue.get("key"),
                "summary": fields.get("summary"),
                "status": (fields.get("status") or {}).get("name"),
                "assignee": (fields.get("assignee") or {}).get("displayName"),
                "priority": (fields.get("priority") or {}).get("name"),
                "updated": fields.get("updated"),
                "issue_type": (fields.get("issuetype") or {}).get("name"),
                "labels": fields.get("labels") or [],
                "parent": (fields.get("parent") or {}).get("key"),
                "linked_keys": sorted(set(linked_keys)),
            }
        )

    return {
        "command": "search",
        "jql": jql,
        "total": data.get("total", len(rows)),
        "count": len(rows),
        "issues": rows,
    }


def run_probe(args: argparse.Namespace, host: str, auth: HTTPBasicAuth) -> Dict[str, Any]:
    transitions = request_json("GET", host, auth, f"/rest/api/3/issue/{args.issue_key}/transitions")
    resolutions = request_json("GET", host, auth, "/rest/api/3/resolution")

    return {
        "command": "probe",
        "issue_key": args.issue_key,
        "transitions": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "to": (item.get("to") or {}).get("name"),
            }
            for item in transitions.get("transitions", [])
        ],
        "resolutions": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
            }
            for item in resolutions
        ],
    }


def adf_text(message: str) -> Dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": message}],
            }
        ],
    }


def extract_issue_keys(cli_keys: Iterable[str], issue_file: Optional[str]) -> List[str]:
    keys = [key.strip().upper() for key in cli_keys if key and key.strip()]
    if issue_file:
        with open(issue_file, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip().upper()
                if not stripped or stripped.startswith("#"):
                    continue
                keys.append(stripped)
    return sorted(set(keys))


def comment_exists(host: str, auth: HTTPBasicAuth, issue_key: str, message: str) -> bool:
    payload = request_json("GET", host, auth, f"/rest/api/3/issue/{issue_key}/comment")
    for comment in payload.get("comments", []):
        body = comment.get("body") or {}
        if isinstance(body, str) and message in body:
            return True
        if isinstance(body, dict):
            for block in body.get("content", []):
                for node in block.get("content", []):
                    if message in str(node.get("text") or ""):
                        return True
    return False


def issue_status(host: str, auth: HTTPBasicAuth, issue_key: str) -> str:
    issue = request_json(
        "GET",
        host,
        auth,
        f"/rest/api/3/issue/{issue_key}",
        params={"fields": "status"},
    )
    return str(((issue.get("fields") or {}).get("status") or {}).get("name") or "")


def choose_transition_id(transitions: List[Dict[str, Any]]) -> Optional[str]:
    by_name = {str(item.get("name") or ""): str(item.get("id") or "") for item in transitions}
    for preferred in ("Done", "Close Issue", "Resolve Issue"):
        if by_name.get(preferred):
            return by_name[preferred]
    return None


def choose_resolution_id(resolutions: List[Dict[str, Any]]) -> str:
    by_name = {str(item.get("name") or ""): str(item.get("id") or "") for item in resolutions}
    return by_name.get("Done") or by_name.get("Duplicate") or ""


def run_bulk_close(args: argparse.Namespace, host: str, auth: HTTPBasicAuth) -> Dict[str, Any]:
    issue_keys = extract_issue_keys(args.issue_keys, args.issue_file)
    if not issue_keys:
        raise RuntimeError("No issue keys provided. Use --issue-key or --issue-file.")

    comment_text = f"Closing as duplicate of '{args.duplicate_of.upper()}'"

    probe_data = request_json("GET", host, auth, f"/rest/api/3/issue/{issue_keys[0]}/transitions")
    transitions = probe_data.get("transitions", [])
    transition_id = choose_transition_id(transitions)
    if not transition_id:
        raise RuntimeError("No close-like transition found on sample issue.")

    resolutions = request_json("GET", host, auth, "/rest/api/3/resolution")
    resolution_id = choose_resolution_id(resolutions)

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for issue_key in issue_keys:
        try:
            has_comment = comment_exists(host, auth, issue_key, comment_text)
            status_before = issue_status(host, auth, issue_key)
            is_done = status_before.lower() == "done"

            will_add_comment = not has_comment
            will_transition = not is_done

            comment_action = "already_present" if has_comment else "would_add"
            status_action = "already_done" if is_done else "would_transition"

            if args.execute:
                if will_add_comment:
                    request_json(
                        "POST",
                        host,
                        auth,
                        f"/rest/api/3/issue/{issue_key}/comment",
                        payload={"body": adf_text(comment_text)},
                    )
                    comment_action = "added"
                    time.sleep(max(args.sleep_ms, 0) / 1000.0)

                if will_transition:
                    payload: Dict[str, Any] = {"transition": {"id": transition_id}}
                    if resolution_id:
                        payload["fields"] = {"resolution": {"id": resolution_id}}
                    request_json(
                        "POST",
                        host,
                        auth,
                        f"/rest/api/3/issue/{issue_key}/transitions",
                        payload=payload,
                    )
                    status_action = "transitioned_to_done"
                    time.sleep(max(args.sleep_ms, 0) / 1000.0)

            rows.append(
                {
                    "issue_key": issue_key,
                    "status_before": status_before,
                    "comment_action": comment_action,
                    "status_action": status_action,
                    "execute": bool(args.execute),
                }
            )
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"issue_key": issue_key, "error": str(exc)})

    return {
        "command": "bulk-close",
        "execute": bool(args.execute),
        "duplicate_of": args.duplicate_of.upper(),
        "transition_id": transition_id,
        "resolution_id": resolution_id,
        "issues_total": len(issue_keys),
        "results": rows,
        "errors": errors,
        "summary": {
            "already_fully_closed": sum(
                1
                for row in rows
                if row["comment_action"] == "already_present" and row["status_action"] == "already_done"
            ),
            "comments_added_or_planned": sum(
                1
                for row in rows
                if row["comment_action"] in {"added", "would_add"}
            ),
            "transitions_done_or_planned": sum(
                1
                for row in rows
                if row["status_action"] in {"transitioned_to_done", "would_transition"}
            ),
            "errors": len(errors),
        },
    }


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    host, auth = load_config()

    if args.command == "search":
        output = run_search(args, host, auth)
    elif args.command == "probe":
        output = run_probe(args, host, auth)
    elif args.command == "bulk-close":
        output = run_bulk_close(args, host, auth)
    else:
        raise RuntimeError(f"Unsupported command: {args.command}")

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
