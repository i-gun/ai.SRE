"""Unit tests for newrelic_servicenow_alert_orchestrator workflow decisions."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "orchestration"
if str(SCRIPT_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PATH))

from newrelic_servicenow_alert_orchestrator import (  # noqa: E402
    AlertToIncidentOrchestrator,
    OrchestratorConfig,
    format_markdown_report,
)


class _FakeNRClient:
    def __init__(self, alerts_by_account):
        self.alerts_by_account = alerts_by_account

    def fetch_open_alerts(self, **kwargs):
        return self.alerts_by_account

    def resolve_issue_id_from_incident_id(self, *, account_id, incident_id, since):
        return ""

    def acknowledge_issue(self, *, account_id, issue_id):
        return {"status": "success", "issueId": issue_id}


class _FakeSNConfig:
    def __init__(self, assignment_groups):
        self.assignment_groups = assignment_groups


class _FakeSNClient:
    INCIDENT_TABLE_PATH = "/api/now/table/incident"

    def __init__(self, *, existing_incidents=None):
        self.config = _FakeSNConfig(["IT - Epam - Monitoring - ODP"])
        self.existing_incidents = list(existing_incidents or [])
        self.patch_payloads = []
        self.post_payloads = []
        self.get_params = []

    def _request(self, method, path, params=None, json=None):
        if method == "GET":
            self.get_params.append(params or {})
            return {"result": self.existing_incidents}

        if method == "PATCH":
            self.patch_payloads.append(json or {})
            updated = dict(self.existing_incidents[0] if self.existing_incidents else {})
            updated.update(json or {})
            return {"result": updated}

        if method == "POST":
            self.post_payloads.append(json or {})
            created = dict(json or {})
            created["number"] = "INC0099999"
            return {"result": created}

        raise AssertionError(f"Unexpected request: {method} {path}")


class TestAlertOrchestrationDecisions(unittest.TestCase):
    def _config(self):
        return OrchestratorConfig(
            servicenow_user="sn_integration_user",
            caller_id="sn_integration_user",
        )

    def _nr_alerts(self):
        return {
            1679802: [
                {
                    "issueId": "issue-1",
                    "title": "Digital Operations - Checkout errors",
                    "issueLink": "https://one.newrelic.com/alerts/issue-1",
                }
            ]
        }

    def test_existing_assigned_incident_stops_without_update(self):
        sn_client = _FakeSNClient(
            existing_incidents=[
                {
                    "sys_id": "abc",
                    "number": "INC0000123",
                    "assigned_to": "oncall.user",
                    "cmdb_ci": "CI-1",
                    "active": "true",
                }
            ]
        )
        orchestrator = AlertToIncidentOrchestrator(
            newrelic_client=_FakeNRClient(self._nr_alerts()),
            servicenow_client=sn_client,
            config=self._config(),
        )

        result = orchestrator.run()
        self.assertEqual(result["summary"]["open_newrelic_alerts_acknowledged"], 1)
        self.assertEqual(result["summary"]["servicenow_incidents_raised_new"], 0)
        self.assertEqual(
            result["summary"]["servicenow_incidents_acknowledged_only_already_raised"], 1
        )
        self.assertEqual(sn_client.patch_payloads, [])
        self.assertEqual(sn_client.post_payloads, [])

    def test_existing_unassigned_incident_is_assigned_and_enriched(self):
        sn_client = _FakeSNClient(
            existing_incidents=[
                {
                    "sys_id": "def",
                    "number": "INC0000456",
                    "assigned_to": "",
                    "cmdb_ci": "Digital - Existing CI",
                    "active": "true",
                }
            ]
        )
        orchestrator = AlertToIncidentOrchestrator(
            newrelic_client=_FakeNRClient(self._nr_alerts()),
            servicenow_client=sn_client,
            config=self._config(),
        )

        result = orchestrator.run()
        self.assertEqual(result["summary"]["servicenow_incidents_raised_new"], 0)
        self.assertEqual(len(sn_client.patch_payloads), 1)
        patch_payload = sn_client.patch_payloads[0]
        self.assertEqual(patch_payload["assigned_to"], "sn_integration_user")
        self.assertEqual(patch_payload["category"], "Application")
        self.assertEqual(patch_payload["subcategory"], "E-Commerce")
        self.assertEqual(patch_payload["service_offering"], "Digital - Existing CI")

    def test_missing_incident_creates_new_with_required_fields(self):
        sn_client = _FakeSNClient(existing_incidents=None)
        orchestrator = AlertToIncidentOrchestrator(
            newrelic_client=_FakeNRClient(self._nr_alerts()),
            servicenow_client=sn_client,
            config=self._config(),
        )

        result = orchestrator.run()
        self.assertEqual(result["summary"]["servicenow_incidents_raised_new"], 1)
        self.assertEqual(
            result["summary"]["servicenow_incidents_acknowledged_only_already_raised"], 0
        )
        self.assertEqual(len(sn_client.post_payloads), 1)
        payload = sn_client.post_payloads[0]
        self.assertEqual(payload["caller_id"], "sn_integration_user")
        self.assertEqual(payload["contact_type"], "teams")
        self.assertEqual(payload["channel"], "Self-service")
        self.assertEqual(payload["category"], "Application")
        self.assertEqual(payload["subcategory"], "E-Commerce")
        self.assertEqual(payload["service_offering"], "Digital - New Relic Alerts - ODP")
        self.assertEqual(payload["cmdb_ci"], "Digital - New Relic Alerts - ODP")
        self.assertEqual(payload["assignment_group"], "IT - Epam - Monitoring - ODP")
        self.assertEqual(payload["assigned_to"], "sn_integration_user")

    def test_resolved_incident_is_reported_without_update(self):
        sn_client = _FakeSNClient(
            existing_incidents=[
                {
                    "sys_id": "ghi",
                    "number": "INC0000789",
                    "assigned_to": "resolver.user",
                    "active": "false",
                    "state": "Resolved",
                    "close_notes": "Restarted service and confirmed recovery.",
                }
            ]
        )
        orchestrator = AlertToIncidentOrchestrator(
            newrelic_client=_FakeNRClient(self._nr_alerts()),
            servicenow_client=sn_client,
            config=self._config(),
        )

        result = orchestrator.run()
        self.assertEqual(result["summary"]["servicenow_incidents_raised_new"], 0)
        self.assertEqual(
            result["summary"]["servicenow_incidents_acknowledged_only_already_raised"], 1
        )
        self.assertEqual(result["report"][0]["servicenow_incident_number"], "INC0000789")
        self.assertEqual(
            result["report"][0]["servicenow_resolution_notes"],
            "Restarted service and confirmed recovery.",
        )
        self.assertEqual(sn_client.patch_payloads, [])
        self.assertEqual(sn_client.post_payloads, [])

    def test_lookup_query_uses_substring_match_and_time_window(self):
        sn_client = _FakeSNClient(existing_incidents=None)
        orchestrator = AlertToIncidentOrchestrator(
            newrelic_client=_FakeNRClient(self._nr_alerts()),
            servicenow_client=sn_client,
            config=OrchestratorConfig(
                servicenow_user="sn_integration_user",
                caller_id="sn_integration_user",
                since="3 hours ago",
            ),
        )

        query = orchestrator._build_incident_lookup_query(
            alert_title="Digital Operations - Checkout errors",
            now=datetime(2026, 7, 17, 20, 0, 0),
        )
        self.assertIn("short_descriptionLIKEDigital Operations - Checkout errors", query)
        self.assertIn("sys_created_on>=2026-07-17 17:00:00", query)
        self.assertIn("sys_created_on<=2026-07-17 20:00:00", query)

    def test_markdown_format_contains_summary_and_table(self):
        markdown = format_markdown_report(
            {
                "policy_name_starts_with": "Digital Operations",
                "since": "1 hours ago",
                "report": [
                    {
                        "newrelic_alert_title": "Checkout error",
                        "acknowledgement_status": "success",
                        "servicenow_incident_number": "INC0001",
                        "servicenow_assignee": "user1",
                        "servicenow_resolution_notes": "Recovered after restart.",
                    }
                ],
                "summary": {
                    "open_newrelic_alerts_acknowledged": 1,
                    "servicenow_incidents_raised_new": 1,
                    "servicenow_incidents_acknowledged_only_already_raised": 0,
                },
            }
        )
        self.assertIn("# New Relic -> ServiceNow Orchestrator Report", markdown)
        self.assertIn("| New Relic alert title |", markdown)
        self.assertIn("Checkout error", markdown)
        self.assertIn("Recovered after restart.", markdown)
        self.assertIn("Open New Relic alerts acknowledged: **1**", markdown)


if __name__ == "__main__":
    unittest.main()
