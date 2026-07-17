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

    @classmethod
    def from_env(cls) -> "NewRelicAlertsConfig":
        api_key = os.getenv("NEWRELIC_API_KEY", "").strip()
        account_ids_raw = os.getenv("NEWRELIC_ACCOUNT_IDS", "").strip()

        missing = [
            name
            for name, value in [
                ("NEWRELIC_API_KEY", api_key),
                ("NEWRELIC_ACCOUNT_IDS", account_ids_raw),
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

        return cls(api_key=api_key, account_ids=account_ids)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class NewRelicAlertsClient:
    """Client for New Relic alert search and acknowledgment operations."""

    NERDGRAPH_URL = "https://api.newrelic.com/graphql"
    DEFAULT_TIMEOUT_SECONDS = 30
    SCOPED_ACCOUNT_ID = 1679802
    DEFAULT_POLICY_NAME_PREFIX = "Digital Operations"
    DEFAULT_SINCE = "3 hours ago"
    ALERT_EVENT_TYPES = ("NrAiIssue", "NrAiIncident")

    def __init__(self, config: NewRelicAlertsConfig) -> None:
        self.config = config
        self._resolved_username: Optional[str] = None
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
        policy_name_starts_with: str = DEFAULT_POLICY_NAME_PREFIX,
        priority: Optional[str] = None,
        since: str = DEFAULT_SINCE,
        limit: int = 100,
        account_ids: Optional[List[int]] = None,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Search NrAiIssue alert events across one or more accounts.

        Filters by policy name prefix and returns open,
        unacknowledged issues. Muted alerts are always excluded.

        Args:
            policy_name_starts_with: Prefix to match against policyNames
            priority: Optional priority filter (e.g., 'CRITICAL', 'HIGH')
            since: Time window start expression (e.g., '3 hours ago')
            limit: Maximum results per account
            account_ids: Optional account override, restricted to 1679802

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
        if not policy_name_starts_with.strip():
            raise NewRelicValidationError("Policy name prefix must not be empty.")
        if not since.strip():
            raise NewRelicValidationError("Since value must not be empty.")

        scoped_account_ids = self._resolve_scoped_account_ids(account_ids)
        collected: Dict[int, List[Dict[str, Any]]] = {
            aid: [] for aid in scoped_account_ids
        }
        seen_ids_by_account: Dict[int, set[str]] = {
            aid: set() for aid in scoped_account_ids
        }

        for event_type in self.ALERT_EVENT_TYPES:
            nrql = self._build_alert_search_nrql(
                event_type=event_type,
                policy_name_starts_with=policy_name_starts_with,
                priority=priority,
                since=since,
                limit=limit,
            )
            by_account = self.run_nrql_across_accounts(nrql=nrql, account_ids=scoped_account_ids)

            for aid, rows in by_account.items():
                for row in rows:
                    normalized = self._normalize_alert_row(row)
                    dedupe_id = str(
                        normalized.get("issueId") or normalized.get("incidentId") or ""
                    ).strip()
                    if not dedupe_id:
                        continue
                    if dedupe_id in seen_ids_by_account[aid]:
                        continue
                    seen_ids_by_account[aid].add(dedupe_id)
                    collected[aid].append(normalized)

        return collected

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
            username: Optional username override. Uses platform-resolved user when omitted.

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
        resolved_username = (
            username.strip()
            if isinstance(username, str) and username.strip()
            else self.get_platform_username()
        )
        if not resolved_username:
            raise NewRelicValidationError("Username must not be empty.")

        mutation = self._build_acknowledge_mutation(
            account_id=account_id,
            issue_id=issue_id,
        )

        try:
            response = self._nerdgraph(mutation)
            data = response.get("data", {})

            mutation_result = data.get("aiIssuesAckIssue")
            if not isinstance(mutation_result, dict):
                return {
                    "status": "error: missing aiIssuesAckIssue response payload",
                    "issueId": issue_id,
                    "acknowledgedBy": resolved_username,
                }

            if mutation_result.get("error"):
                return {
                    "status": f"error: {mutation_result['error']}",
                    "issueId": issue_id,
                    "acknowledgedBy": resolved_username,
                }

            result_payload = mutation_result.get("result") or {}
            return {
                "status": "success",
                "issueId": str(result_payload.get("issueId") or issue_id),
                "acknowledgedBy": resolved_username,
                "acknowledgedAt": "",
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
        policy_name_starts_with: str = DEFAULT_POLICY_NAME_PREFIX,
        priority: Optional[str] = None,
        since: str = DEFAULT_SINCE,
        limit: int = 100,
        account_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Fetch open unacknowledged alerts and acknowledge each using platform identity."""
        alerts_by_account = self.fetch_open_alerts(
            policy_name_starts_with=policy_name_starts_with,
            priority=priority,
            since=since,
            limit=limit,
            account_ids=account_ids,
        )

        acknowledged: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        for account_id, alerts in alerts_by_account.items():
            for alert in alerts:
                issue_id = str(alert.get("issueId") or "").strip()
                incident_id = str(alert.get("incidentId") or "").strip()

                if not issue_id and incident_id:
                    issue_id = self.resolve_issue_id_from_incident_id(
                        account_id=account_id,
                        incident_id=incident_id,
                        since=since,
                    )

                if not issue_id:
                    failed.append(
                        {
                            "account_id": account_id,
                            "title": alert.get("title", ""),
                            "incident_id": incident_id,
                            "status": "error: unable to resolve issueId for acknowledgment",
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
                    "incident_id": incident_id,
                    "ack_id_source": "issueId"
                    if alert.get("issueId")
                    else "resolved_from_incidentId",
                    "title": alert.get("title", ""),
                    **result,
                }
                if result.get("status") == "success":
                    acknowledged.append(outcome)
                else:
                    failed.append(outcome)

        return {
            "policy_name_starts_with": policy_name_starts_with,
            "time_window": f"SINCE {since} UNTIL now",
            "account_scope": [self.SCOPED_ACCOUNT_ID],
            "muted_excluded": True,
            "acknowledged_by": self.get_platform_username(),
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
        event_type: str,
        policy_name_starts_with: str,
        priority: Optional[str],
        since: str,
        limit: int,
    ) -> str:
        """Build a NRQL query targeting NrAiIssue alert events.

        Filters by policy name prefix and optionally by priority.
        Always excludes muted alerts and searches from the requested window until now.
        """
        if event_type == "NrAiIncident":
            clauses: List[str] = [
                "muted = false",
                "(closeTime IS NULL OR closeTime = 0)",
            ]
            if policy_name_starts_with:
                escaped = policy_name_starts_with.replace("'", "\\'")
                clauses.append(f"(policyName LIKE '{escaped}%' OR policyNames LIKE '{escaped}%')")
            if priority:
                clauses.append(f"priority = '{priority.upper()}'")

            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            return (
                f"SELECT incidentId, issueId, title, description, interpolatedTitleTemplate, "
                f"policyName, policyNames, conditionName, conditionNames, priority, event, "
                f"incidentLink, issueLink, muted, openTime, closeTime, timestamp "
                f"FROM NrAiIncident{where} SINCE {since} UNTIL now "
                f"ORDER BY openTime DESC LIMIT {limit}"
            )

        clauses = [
            "("
            "muted IS NULL OR muted = false OR muted = 0 OR "
            "muted = 'notMuted' OR muted = 'NOT_MUTED' OR "
            "muted = 'partiallyMuted' OR muted = 'PARTIALLY_MUTED'"
            ")",
            "(event = 'ACTIVATED' OR event = 'OPEN' OR event = 'CREATED')",
        ]
        if policy_name_starts_with:
            escaped = policy_name_starts_with.replace("'", "\\'")
            clauses.append(f"(policyNames LIKE '{escaped}%' OR policyName LIKE '{escaped}%')")
        if priority:
            clauses.append(f"priority = '{priority.upper()}'")

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return (
            f"SELECT issueId, incidentId, title, description, interpolatedTitleTemplate, "
            f"policyNames, policyName, conditionNames, conditionName, priority, event, "
            f"issueLink, incidentLink, muted, activateTime, openTime, lastModifiedTime, timestamp "
            f"FROM NrAiIssue{where} SINCE {since} UNTIL now "
            f"ORDER BY lastModifiedTime DESC LIMIT {limit}"
        )

    @staticmethod
    def _build_acknowledge_mutation(
        *,
        account_id: int,
        issue_id: str,
    ) -> str:
        """Build a NerdGraph mutation to acknowledge an issue.

        The mutation calls aiIssuesAckIssue with the issue ID.
        Username is derived from authenticated API user and is not a mutation argument.
        """
        escaped_id = issue_id.replace('"', '\\"')
        return (
            f"mutation {{\n"
            f'  aiIssuesAckIssue(accountId: {account_id}, issueId: "{escaped_id}") {{\n'
            f"    error\n"
            f"    result {{\n"
            f"      accountId\n"
            f"      action\n"
            f"      issueId\n"
            f"    }}\n"
            f"  }}\n"
            f"}}"
        )

    def resolve_issue_id_from_incident_id(
        self,
        *,
        account_id: int,
        incident_id: str,
        since: str,
    ) -> str:
        """Resolve issueId from incidentId using NrAiIssue incidentIds array."""
        escaped_incident_id = incident_id.replace("\\", "\\\\").replace("'", "\\'")
        nrql = (
            "SELECT issueId, closeTime, muted, lastModifiedTime "
            "FROM NrAiIssue "
            f"WHERE contains(incidentIds, '{escaped_incident_id}') "
            "AND (closeTime IS NULL OR closeTime = 0) "
            "AND muted != 'fullyMuted' "
            f"SINCE {since} UNTIL now "
            "ORDER BY lastModifiedTime DESC LIMIT 1"
        )
        rows = self.run_nrql(account_id=account_id, nrql=nrql)
        if not rows:
            return ""

        return str(rows[0].get("issueId") or "").strip()

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

    def get_platform_username(self) -> str:
        """Resolve the authenticated New Relic user identity from NerdGraph."""
        if self._resolved_username:
            return self._resolved_username

        payload = self._nerdgraph("{ actor { user { email name id } } }")
        user = payload.get("data", {}).get("actor", {}).get("user")
        if not isinstance(user, dict):
            raise NewRelicConfigError(
                "Unable to resolve New Relic username from API key. "
                "Ensure NEWRELIC_API_KEY is a valid user key with NerdGraph user access."
            )

        for field_name in ("email", "name", "id"):
            value = str(user.get(field_name) or "").strip()
            if value:
                self._resolved_username = value
                return value

        raise NewRelicConfigError(
            "Unable to resolve New Relic username from platform response. "
            "Verify API key permissions."
        )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _resolve_scoped_account_ids(
        self,
        override: Optional[List[int]],
    ) -> List[int]:
        """Restrict all alert lookups to the dedicated scoped account."""
        if self.SCOPED_ACCOUNT_ID not in self.config.account_ids:
            raise NewRelicValidationError(
                f"Scoped account {self.SCOPED_ACCOUNT_ID} is not configured in NEWRELIC_ACCOUNT_IDS."
            )

        if override is None:
            return [self.SCOPED_ACCOUNT_ID]

        if self.SCOPED_ACCOUNT_ID not in override:
            raise NewRelicValidationError(
                f"Only account {self.SCOPED_ACCOUNT_ID} is allowed for this skill."
            )

        return [self.SCOPED_ACCOUNT_ID]

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

    @staticmethod
    def _normalize_alert_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize NrAiIssue/NrAiIncident field variants into one alert shape."""
        issue_id = row.get("issueId")
        incident_id = row.get("incidentId")
        title = (
            row.get("title")
            or row.get("interpolatedTitleTemplate")
            or row.get("description")
            or ""
        )
        policy_names = row.get("policyNames") or row.get("policyName") or ""
        condition_names = row.get("conditionNames") or row.get("conditionName") or ""
        issue_link = row.get("issueLink") or row.get("incidentLink") or ""
        activate_time = row.get("activateTime") or row.get("openTime") or row.get("timestamp") or ""
        last_modified_time = row.get("lastModifiedTime") or row.get("timestamp") or ""

        return {
            "issueId": issue_id,
            "incidentId": incident_id,
            "title": title,
            "policyNames": policy_names,
            "conditionNames": condition_names,
            "priority": row.get("priority", ""),
            "event": row.get("event", ""),
            "activateTime": activate_time,
            "lastModifiedTime": last_modified_time,
            "issueLink": issue_link,
            "muted": row.get("muted"),
        }
