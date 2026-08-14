"""Unit tests for the shared resolution_matrix artifact utility."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "common" / "resolution_matrix.py"


def _load_module():
    if str(MODULE_PATH.parent) not in sys.path:
        sys.path.insert(0, str(MODULE_PATH.parent))
    spec = importlib.util.spec_from_file_location("resolution_matrix", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


rm = _load_module()


def _sample_rows():
    return [
        {
            "entity_key": {"kind": "CDS", "cve_id": "GHSA-1"},
            "classification": "report_only",
            "existing": {"ddl_key": "DDL-1", "bet_key": "BET-1", "incident_number": None, "problem_number": None},
        }
    ]


class TestBuildAndWriteMatrix(unittest.TestCase):
    def test_build_matrix_rejects_invalid_domain(self):
        with self.assertRaises(rm.ResolutionMatrixError):
            rm.build_matrix(domain="bogus", generated_by="test", window={}, rows=_sample_rows())

    def test_build_matrix_rejects_invalid_classification(self):
        rows = _sample_rows()
        rows[0]["classification"] = "not_a_real_value"
        with self.assertRaises(rm.ResolutionMatrixError):
            rm.build_matrix(domain="cve", generated_by="test", window={}, rows=rows)

    def test_build_matrix_success(self):
        matrix = rm.build_matrix(domain="cve", generated_by="test", window={"start": "a", "end": "b"}, rows=_sample_rows())
        self.assertEqual(matrix["schema_version"], rm.SCHEMA_VERSION)
        self.assertEqual(matrix["domain"], "cve")
        self.assertEqual(len(matrix["rows"]), 1)
        self.assertIn("source_data_fingerprint", matrix)

    def test_write_and_load_roundtrip(self):
        matrix = rm.build_matrix(domain="secrets", generated_by="test", window={}, rows=_sample_rows())
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            path = rm.write_matrix(matrix, out_dir=out_dir)
            self.assertTrue(path.exists())
            loaded = rm.load_matrix(path, expected_domain="secrets")
            self.assertEqual(loaded["domain"], "secrets")

    def test_load_matrix_domain_mismatch(self):
        matrix = rm.build_matrix(domain="cve", generated_by="test", window={}, rows=_sample_rows())
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            path = rm.write_matrix(matrix, out_dir=out_dir)
            with self.assertRaises(rm.ResolutionMatrixError):
                rm.load_matrix(path, expected_domain="secrets")

    def test_find_latest_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            matrix = rm.build_matrix(domain="cve", generated_by="test", window={}, rows=_sample_rows())
            rm.write_matrix(matrix, out_dir=out_dir)
            latest = rm.find_latest_matrix("cve", artifacts_dir=out_dir)
            self.assertIsNotNone(latest)
            self.assertIsNone(rm.find_latest_matrix("secrets", artifacts_dir=out_dir))


class TestStalenessCheck(unittest.TestCase):
    def test_fresh_matrix_is_not_stale(self):
        matrix = rm.build_matrix(domain="cve", generated_by="test", window={}, rows=_sample_rows())
        result = rm.check_staleness(matrix, max_age_hours=4)
        self.assertFalse(result["is_stale"])

    def test_old_matrix_is_stale(self):
        matrix = rm.build_matrix(domain="cve", generated_by="test", window={}, rows=_sample_rows())
        old_time = datetime.now(timezone.utc) - timedelta(hours=100)
        matrix["generated_at"] = old_time.isoformat()
        result = rm.check_staleness(matrix, max_age_hours=4)
        self.assertTrue(result["is_stale"])
        self.assertTrue(any("exceeds max_age_hours" in reason for reason in result["reasons"]))

    def test_tampered_rows_detected_via_fingerprint(self):
        matrix = rm.build_matrix(domain="cve", generated_by="test", window={}, rows=_sample_rows())
        matrix["rows"][0]["existing"]["ddl_key"] = "DDL-999"
        result = rm.check_staleness(matrix, max_age_hours=100)
        self.assertTrue(result["is_stale"])
        self.assertTrue(any("fingerprint" in reason for reason in result["reasons"]))


class TestFingerprintRows(unittest.TestCase):
    def test_fingerprint_stable_for_same_content(self):
        rows_a = _sample_rows()
        rows_b = _sample_rows()
        self.assertEqual(rm.fingerprint_rows(rows_a), rm.fingerprint_rows(rows_b))

    def test_fingerprint_changes_with_existing_fields(self):
        rows_a = _sample_rows()
        rows_b = _sample_rows()
        rows_b[0]["existing"]["ddl_key"] = "DDL-2"
        self.assertNotEqual(rm.fingerprint_rows(rows_a), rm.fingerprint_rows(rows_b))


if __name__ == "__main__":
    unittest.main()
