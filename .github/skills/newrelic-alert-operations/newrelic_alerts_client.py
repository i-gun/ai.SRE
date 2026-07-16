"""New Relic NerdGraph client for alert fetching and acknowledgment operations."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests


class NewRelicConfigError(Exception):
    """Raised when New Relic configuration is invalid."""


class NewRelicValidationError(Exception):
    """Raised when operation inputs fail validation checks."""


class NewRelicAPIError(Exception):
    """Raised when New Relic API calls fail."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class NewRelicAlertsConfig:
    api_key: str
    account_ids: List[int] = field(default_factory=list)
    username: str = ""

    @classmethod
    def from_env(cls) -> "NewRelicAlertsConfig":
        api_key = os.getenv("NEWRELIC_API_KEY", "").strip()
        account_ids_raw = os.getenv("NEWRELIC_ACCOUNT_IDS", "").strip()
        username = os.getenv("NEWRELIC_USERNAME", "").strip()

        missing = [
            name
            for name, value in [
                ("NEWRELIC_API_KEY", api_key),
                ("NEWRELIC_ACCOUNT_IDS", account_ids_raw),
                ("NEWRELIC_USERNAME", username),
            ]
            if not value
        ]

        if missing:
            raise NewRelicConfigError(
                "Missing required New Relic environment variables: " + ", ".join(missing)
            )

        account_ids: List[int] = []
        for raw in account_ids_raw.split(","):
            token = raw.strip()
            if not token:
                continue
            if not token.lstrip("-").isdigit() or int(token) <= 0:
                raise NewRelicConfigError(
                    f"NEWRELIC_ACCOUNT_IDS contains invalid account ID: '{token}'. "
                    "Each ID must be a positive integer."
                )
            account_ids.append(int(token))

        if not account_ids:
            raise NewRelicConfigError(
                "NEWRELIC_ACCOUNT_IDS must contain at least one positive integer account ID."
            )

        return cls(api_key=api_key, account_ids=account_ids, username=username)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class NewRelicAlertsClient:
    """Client for New Relic alert search and acknowledgment operations."""

    NERDGRAPH_URL = "https://api.newrelic.com/graphql"
    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(self, config: NewRelicAlertsConfig) -> None:
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "API-Key": config.api_key,
            }
        )

    @classmethod
    def from_env(cls) -> "NewRelicAlertsClient":
        return cls(NewRelicAlertsConfig.from_env())

    # ------------------------------------------------------------------
    # Core NerdGraph transport
    # ------------------------------------------------------------------

    def _nerdgraph(self, graphql_query: str) -> Dict[str, Any]:
        try:
            response = self._session.post(
                self.NERDGRAPH_URL,
                json={"query": graphql_query},
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise NewRelicAPIError(f"New Relic request failed: {exc}") from exc

        if response.status_code >= 400:
            raise NewRelicAPIError(
                f"New Relic API error ({response.status_code}): {response.text[:300]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise NewRelicAPIError("New Relic returned non-JSON response") from exc

        errors = payload.get("errors")
        if errors:
            messages = "; ".join(e.get("message", str(e)) for e in errors)
            raise NewRelicAPIError(f"NerdGraph errors: {messages}")

        return payload

    # ------------------------------------------------------------------
    # NRQL execution
    # ------------------------------------------------------------------

    def run_nrql(self, *, account_id: int, nrql: str) -> List[Dict[str, Any]]:
        """Execute a single NRQL query against one account."""
        if not nrql.strip():
            raise NewRelicValidationError("NRQL query must not be empty.")
        gql = self._build_multi_account_nerdgraph({account_id: nrql})
        data = self._nerdgraph(gql).get("data", {}).get("actor", {})
        return data.get(f"a{account_id}", {}).get("nrql", {}).get("results", [])

    def run_nrql_across_accounts(
        self,
        *,
        nrql: str,
        account_ids: Optional[List[int]] = None,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Execute the same NRQL query across multiple accounts in one request."""
        if not nrql.strip():
            raise NewRelicValidationError("NRQL query must not be empty.")
        ids = self._resolve_account_ids(self.config.account_ids, account_ids)
        gql = self._build_multi_account_nerdgraph({aid: nrql for aid in ids})
        actor = self._nerdgraph(gql).get("data", {}).get("actor", {})
        return {
            aid: actor.get(f"a{aid}", {}).get("nrql", {}).get("results", [])
            for aid in ids
        }

    # ------------------------------------------------------------------
    # Alert search
    # ------------------------------------------------------------------

    def fetch_open_alerts(
        self,
        *,
        policy_name_contains: str = "",
        priority: Optional[str] = None,
        limit: int = 100,
        account_ids: Optional[List[int]] = None,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Search NrAiIssue alert events across one or more accounts.

        Filters by policy name (substring match) and returns open,
        unacknowledged issues. Muted alerts are always excluded.

        Args:
            policy_name_contains: Substring to match against policyNames
            priority: Optional priority filter (e.g., 'CRITICAL', 'HIGH')
            limit: Maximum results per account
            account_ids: Override configured account IDs

        Returns:
            Dict mapping account_id to list of alert dicts with:
            - issueId: Unique identifier for the issue
            - title: Issue title/description
            - policyNames: Policy name(s)
            - priority: Alert severity level
            - activateTime: When issue activated
            - lastModifiedTime: Last update time
            - issueLink: Link to issue in New Relic UI
        """
        if limit <= 0:
            raise NewRelicValidationError("Limit must be greater than zero.")
        if not policy_name_contains.strip():
            raise NewRelicValidationError("Policy name filter must not be empty.")

        nrql = self._build_alert_search_nrql(
            policy_name_contains=policy_name_contains,
            priority=priority,
            limit=limit,
        )
        return self.run_nrql_across_accounts(nrql=nrql, account_ids=account_ids)

    # ------------------------------------------------------------------
    # Alert acknowledgment
    # ------------------------------------------------------------------

    def acknowledge_issue(
        self,
        *,
        account_id: int,
        issue_id: str,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Acknowledge an issue by issueId using NerdGraph mutation.

        Args:
            account_id: New Relic account ID
            issue_id: Issue ID returned from fetch_open_alerts
            username: Optional username override. Uses configured NEWRELIC_USERNAME when omitted.

        Returns:
            Dict with:
            - status: 'success' or error message
            - issueId: The acknowledged issue ID
            - acknowledgedBy: Username
            - acknowledgedAt: Timestamp (if available)
        """
        if not account_id or account_id <= 0:
            raise NewRelicValidationError("Account ID must be a positive integer.")
        if not issue_id.strip():
            raise NewRelicValidationError("Issue ID must not be empty.")
        resolved_username = username.strip() if isinstance(username, str) else self.config.username
        if not resolved_username:
            raise NewRelicValidationError("Username must not be empty.")

        mutation = self._build_acknowledge_mutation(
            account_id=account_id,
            issue_id=issue_id,
            username=resolved_username,
        )

        try:
            response = self._nerdgraph(mutation)
            data = response.get("data", {})

            # Extract mutation response from nested structure
            mutation_result = (
                data.get("aiIssuesAcknowledgeIssue", {})
                or data.get("error", {})
                or {"status": "unknown response structure"}
            )

            if "error" in mutation_result:
                return {
                    "status": f"error: {mutation_result['error']}",
                    "issueId": issue_id,
                    "acknowledgedBy": resolved_username,
                }

            return {
                "status": "success",
                "issueId": issue_id,
                "acknowledgedBy": resolved_username,
                "acknowledgedAt": mutation_result.get("acknowledgedAt", ""),
            }
        except NewRelicAPIError as exc:
            return {
                "status": f"api_error: {str(exc)}",
                "issueId": issue_id,
                "acknowledgedBy": resolved_username,
            }

    def fetch_and_acknowledge_open_alerts(
        self,
        *,
        policy_name_contains: str,
        priority: Optional[str] = None,
        limit: int = 100,
        account_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Fetch open unacknowledged alerts and acknowledge each using configured username."""
        alerts_by_account = self.fetch_open_alerts(
            policy_name_contains=policy_name_contains,
            priority=priority,
            limit=limit,
            account_ids=account_ids,
        )

        acknowledged: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        for account_id, alerts in alerts_by_account.items():
            for alert in alerts:
                issue_id = str(alert.get("issueId") or "").strip()
                if not issue_id:
                    failed.append(
                        {
                            "account_id": account_id,
                            "title": alert.get("title", ""),
                            "status": "error: missing issueId in alert payload",
                        }
                    )
                    continue

                result = self.acknowledge_issue(
                    account_id=account_id,
                    issue_id=issue_id,
                )
                outcome = {
                    "account_id": account_id,
                    "issue_id": issue_id,
                    "title": alert.get("title", ""),
                    **result,
                }
                if result.get("status") == "success":
                    acknowledged.append(outcome)
                else:
                    failed.append(outcome)

        return {
            "policy_name_contains": policy_name_contains,
            "time_window": "SINCE 1 hour ago UNTIL now",
            "muted_excluded": True,
            "acknowledged_by": self.config.username,
            "alerts_found": sum(len(items) for items in alerts_by_account.values()),
            "acknowledged_count": len(acknowledged),
            "failed_count": len(failed),
            "acknowledged": acknowledged,
            "failed": failed,
            "alerts_by_account": alerts_by_account,
        }

    # ------------------------------------------------------------------
    # NRQL and Mutation builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_alert_search_nrql(
        *,
        policy_name_contains: str,
        priority: Optional[str],
        limit: int,
    ) -> str:
        """Build a NRQL query targeting NrAiIssue alert events.

        Filters by policy name (substring match) and optionally by priority.
        Always excludes muted alerts and searches from 1 hour ago until now.
        """
        clauses: List[str] = ["muted != 'fullyMuted'", "event = 'ACTIVATED'"]
        if policy_name_contains:
            escaped = policy_name_contains.replace("'", "\\'")
            clauses.append(f"policyNames LIKE '%{escaped}%'")
        if priority:
            clauses.append(f"priority = '{priority.upper()}'")

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return (
            f"SELECT issueId, title, policyNames, conditionNames, priority, "
            f"activateTime, lastModifiedTime, issueLink, muted "
            f"FROM NrAiIssue{where} SINCE 1 hour ago UNTIL now "
            f"ORDER BY lastModifiedTime DESC LIMIT {limit}"
        )

    @staticmethod
    def _build_acknowledge_mutation(
        *,
        account_id: int,
        issue_id: str,
        username: str,
    ) -> str:
        """Build a NerdGraph mutation to acknowledge an issue.

        The mutation calls aiIssuesAcknowledgeIssue with the issue ID
        and records acknowledgment with the provided username.
        """
        escaped_id = issue_id.replace('"', '\\"')
        escaped_user = username.replace('"', '\\"')
        return (
            f"mutation {{\n"
            f'  aiIssuesAcknowledgeIssue(accountId: {account_id}, issueId: "{escaped_id}", acknowledgedBy: "{escaped_user}") {{\n'
            f"    issueId\n"
            f"    acknowledgedBy\n"
            f"    acknowledgedAt\n"
            f"  }}\n"
            f"}}"
        )

    @staticmethod
    def _build_multi_account_nerdgraph(account_nrql_map: Dict[int, str]) -> str:
        if not account_nrql_map:
            raise NewRelicValidationError("account_nrql_map must not be empty.")
        fragments: List[str] = []
        for account_id, nrql in account_nrql_map.items():
            escaped_nrql = nrql.replace("\\", "\\\\").replace('"', '\\"')
            fragments.append(
                f'  a{account_id}: account(id: {account_id}) {{\n'
                f'    nrql(query: "{escaped_nrql}") {{ results }}\n'
                f'  }}'
            )
        return "{ actor {\n" + "\n".join(fragments) + "\n} }"

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_account_ids(
        config_ids: List[int],
        override: Optional[List[int]],
    ) -> List[int]:
        ids = override if override is not None else config_ids
        if not ids:
            raise NewRelicValidationError(
                "No account IDs available. Configure NEWRELIC_ACCOUNT_IDS or pass account_ids explicitly."
            )
        return ids
