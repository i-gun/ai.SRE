"""Policy and CLI tests for core ServiceNow operational scripts."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICENOW_SCRIPTS = PROJECT_ROOT / "scripts" / "servicenow"


def _load_module(module_name: str, path: Path):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestBatchResolveScriptCLI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = _load_module(
            "batch_resolve_triggered_incidents",
            SERVICENOW_SCRIPTS / "batch_resolve_triggered_incidents.py",
        )

    def test_parse_args_defaults_to_read_only(self):
        args = self.module.parse_args(
            [
                "--service-offering",
                "Adobe RTCDP - CTC",
                "--vendor-ticket",
                "DDL-29601",
                "--close-notes",
                "Validated remediation.",
            ]
        )
        self.assertFalse(args.execute)
        self.assertEqual(args.short_description_prefix, self.module.DEFAULT_SHORT_DESC_PREFIX)

    def test_parse_args_rejects_empty_prefix(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.module.parse_args(
                    [
                        "--service-offering",
                        "Adobe RTCDP - CTC",
                        "--vendor-ticket",
                        "DDL-29601",
                        "--close-notes",
                        "Validated remediation.",
                        "--short-description-prefix",
                        "   ",
                    ]
                )


class TestCreateIssueFromProblemCLI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = _load_module(
            "create_issue_from_problem",
            SERVICENOW_SCRIPTS / "create_issue_from_problem.py",
        )

    def test_parse_args_defaults_to_read_only(self):
        args = self.module.parse_args(["--problem-number", "PRB0040185"])
        self.assertFalse(args.execute)
        self.assertEqual(args.problem_number, "PRB0040185")

    def test_parse_args_rejects_invalid_problem_number(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.module.parse_args(["--problem-number", "problem-1"])


class TestServiceNowScriptPolicy(unittest.TestCase):

    def test_core_scripts_do_not_contain_hardcoded_operational_ids(self):
        disallowed_assignment = re.compile(
            r"(?:^|\n)\s*[A-Z_][A-Z0-9_]*\s*=\s*[\"'](?:INC\d{7}|PRB\d{7}|DDL-\d+)[\"']"
        )
        checked = []
        for path in SERVICENOW_SCRIPTS.glob("*.py"):
            if path.name == "common.py":
                continue
            checked.append(path.name)
            content = path.read_text(encoding="utf-8")
            self.assertIsNone(
                disallowed_assignment.search(content),
                msg=f"{path.name} contains a hardcoded assigned operational identifier.",
            )
        self.assertTrue(checked)


if __name__ == "__main__":
    unittest.main()