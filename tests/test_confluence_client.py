"""Unit tests for Confluence service-link extraction and graph building."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = PROJECT_ROOT / ".github" / "skills" / "confluence-knowledge-operations"
if str(CLIENT_PATH) not in sys.path:
    sys.path.insert(0, str(CLIENT_PATH))

from confluence_client import ConfluenceClient, ConfluenceConfig  # noqa: E402


class ConfluenceClientExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        config = ConfluenceConfig(
            host="https://example.atlassian.net",
            username="test@example.com",
            api_token="token",
            space_keys=["PLATFORM"],
        )
        self.client = ConfluenceClient(config)

    def _make_client(self, space_keys):
        config = ConfluenceConfig(
            host="https://example.atlassian.net",
            username="test@example.com",
            api_token="token",
            space_keys=space_keys,
        )
        return ConfluenceClient(config)

    def test_extract_service_relationships_from_pages(self) -> None:
        pages = [
            {
                "id": "101",
                "title": "Checkout Flow",
                "body": {
                    "storage": {
                        "value": (
                            "<p>CheckoutService calls PaymentAPI.</p>"
                            "<p>OrderService -> InventoryService</p>"
                            "<p>OrderService emits to EventBus</p>"
                        )
                    }
                },
            }
        ]

        result = self.client.extract_service_relationships(pages=pages)

        self.assertIn("CheckoutService", result["services"])
        self.assertIn("PaymentAPI", result["services"])
        self.assertIn("OrderService", result["services"])
        self.assertIn("InventoryService", result["services"])

        edge_triplets = {(e["from"], e["relation"], e["to"]) for e in result["edges"]}
        self.assertIn(("CheckoutService", "calls", "PaymentAPI"), edge_triplets)
        self.assertIn(("OrderService", "flows_to", "InventoryService"), edge_triplets)
        self.assertIn(("OrderService", "emits_to", "EventBus"), edge_triplets)

    def test_build_graph_returns_summary_and_mermaid(self) -> None:
        pages = [
            {
                "id": "202",
                "title": "Notifications",
                "body": {
                    "storage": {
                        "value": "<p>NotificationService depends on EmailGateway</p>"
                    }
                },
            }
        ]

        graph = self.client.build_service_flow_graph(pages=pages)

        self.assertEqual(graph["summary"]["node_count"], len(graph["nodes"]))
        self.assertEqual(graph["summary"]["edge_count"], len(graph["edges"]))
        self.assertIn("flowchart LR", graph["mermaid"])
        self.assertIn("depends on", graph["mermaid"])

    def test_graph_returns_space_keys_list(self) -> None:
        pages = [
            {
                "id": "303",
                "title": "Empty",
                "body": {"storage": {"value": ""}},
            }
        ]
        graph = self.client.build_service_flow_graph(pages=pages)
        self.assertIn("space_keys", graph)
        self.assertEqual(graph["space_keys"], ["PLATFORM"])

    def test_extract_returns_space_keys_list(self) -> None:
        pages = [{"id": "404", "title": "Empty", "body": {"storage": {"value": ""}}}]
        result = self.client.extract_service_relationships(pages=pages)
        self.assertIn("space_keys", result)
        self.assertEqual(result["space_keys"], ["PLATFORM"])

    # CQL scoping — single space key

    def test_scope_cql_to_space_when_missing_space_filter(self) -> None:
        scoped = self.client._scope_cql_to_space("type = page AND text ~ \"schema\"")
        self.assertEqual(scoped, 'space = "PLATFORM" AND (type = page AND text ~ "schema")')

    def test_scope_cql_preserves_existing_space_filter(self) -> None:
        cql = 'space = "ANOTHER" AND type = page'
        self.assertEqual(self.client._scope_cql_to_space(cql), cql)

    # CQL scoping — multiple space keys

    def test_scope_cql_multiple_space_keys(self) -> None:
        client = self._make_client(["PLATFORM", "DEV", "OPS"])
        scoped = client._scope_cql_to_space("type = page")
        self.assertEqual(
            scoped,
            '(space = "PLATFORM" OR space = "DEV" OR space = "OPS") AND (type = page)',
        )

    def test_scope_cql_multiple_space_keys_preserves_existing_filter(self) -> None:
        client = self._make_client(["PLATFORM", "DEV"])
        cql = 'space = "CUSTOM" AND type = page'
        self.assertEqual(client._scope_cql_to_space(cql), cql)

    # ConfluenceConfig.from_env — space_keys parsing

    def test_config_space_keys_single(self) -> None:
        config = ConfluenceConfig(
            host="https://example.atlassian.net",
            username="u",
            api_token="t",
            space_keys=["PLATFORM"],
        )
        self.assertEqual(config.space_keys, ["PLATFORM"])

    def test_config_space_keys_multiple(self) -> None:
        config = ConfluenceConfig(
            host="https://example.atlassian.net",
            username="u",
            api_token="t",
            space_keys=["PLATFORM", "DEV", "OPS"],
        )
        self.assertEqual(config.space_keys, ["PLATFORM", "DEV", "OPS"])


if __name__ == "__main__":
    unittest.main()
