"""CLI and utility tests for New Relic helper scripts."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NEWRELIC_SCRIPTS = PROJECT_ROOT / "scripts" / "newrelic"


def _load_module(module_name: str, path: Path):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestGenerateServiceCatalogScript(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = _load_module(
            "generate_service_catalog",
            NEWRELIC_SCRIPTS / "generate_service_catalog.py",
        )

    def test_parse_args_defaults(self):
        args = self.module.parse_args([])
        self.assertEqual(args.account_id, 1679802)
        self.assertEqual(args.since, "30 days ago")
        self.assertEqual(args.output_dir, "data")
        self.assertFalse(args.pretty_json)

    def test_extract_strings_from_rows_handles_scalar_and_list_values(self):
        rows = [
            {"uniques.entity.name": ["alpha", "beta", ""]},
            {"service.name": "gamma"},
            {"ignored": 123},
            {"mixed": ["delta", 7, None]},
        ]
        result = self.module._extract_strings_from_rows(rows)
        self.assertEqual(result, {"alpha", "beta", "gamma", "delta"})


if __name__ == "__main__":
    unittest.main()
