#!/usr/bin/env python3
"""Shared resolution_matrix artifact schema/helpers for CVE and Secrets analysis/execute flows.

An analysis flow (read-only) writes a resolution_matrix JSON artifact describing
reuse/repair/create classification per entity. A paired execute flow loads that
artifact, checks it for staleness, and only then performs writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0"
VALID_DOMAINS = {"cve", "secrets"}
VALID_CLASSIFICATIONS = {"report_only", "repair_needed", "needs_full_creation"}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


class ResolutionMatrixError(ValueError):
    """Raised for invalid or stale resolution_matrix artifacts."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fingerprint_rows(rows: List[Dict[str, Any]]) -> str:
    """Stable hash of row entity_key + existing.* fields, for drift detection."""
    normalized = [
        {
            "entity_key": row.get("entity_key", {}),
            "existing": row.get("existing", {}),
        }
        for row in rows
    ]
    blob = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_matrix(
    *,
    domain: str,
    generated_by: str,
    window: Dict[str, str],
    rows: List[Dict[str, Any]],
    approval_gate_flags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if domain not in VALID_DOMAINS:
        raise ResolutionMatrixError(f"domain must be one of {sorted(VALID_DOMAINS)}, got {domain!r}")

    for row in rows:
        classification = row.get("classification")
        if classification not in VALID_CLASSIFICATIONS:
            raise ResolutionMatrixError(
                f"row classification must be one of {sorted(VALID_CLASSIFICATIONS)}, got {classification!r}"
            )
        row.setdefault("checked_at", _utc_now().isoformat())
        row.setdefault("gaps", [])
        row.setdefault("row_fingerprint", fingerprint_rows([row]))

    return {
        "schema_version": SCHEMA_VERSION,
        "domain": domain,
        "generated_at": _utc_now().isoformat(),
        "generated_by": generated_by,
        "window": window,
        "source_data_fingerprint": fingerprint_rows(rows),
        "rows": rows,
        "approval_gate_flags": approval_gate_flags or [],
    }


def write_matrix(matrix: Dict[str, Any], *, out_dir: Path = DEFAULT_ARTIFACTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    domain = matrix.get("domain", "unknown")
    timestamp = _utc_now().strftime("%Y-%m-%dT%H%M%SZ")
    path = out_dir / f"resolution_matrix_{domain}_{timestamp}.json"
    path.write_text(json.dumps(matrix, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def load_matrix(path: Path, *, expected_domain: Optional[str] = None) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise ResolutionMatrixError(f"resolution_matrix artifact not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if data.get("schema_version") != SCHEMA_VERSION:
        raise ResolutionMatrixError(
            f"unsupported schema_version {data.get('schema_version')!r}, expected {SCHEMA_VERSION!r}"
        )
    domain = data.get("domain")
    if domain not in VALID_DOMAINS:
        raise ResolutionMatrixError(f"invalid domain {domain!r} in artifact")
    if expected_domain and domain != expected_domain:
        raise ResolutionMatrixError(
            f"artifact domain mismatch: expected {expected_domain!r}, found {domain!r}"
        )
    return data


def find_latest_matrix(domain: str, *, artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR) -> Optional[Path]:
    candidates = sorted(artifacts_dir.glob(f"resolution_matrix_{domain}_*.json"))
    return candidates[-1] if candidates else None


def check_staleness(matrix: Dict[str, Any], *, max_age_hours: float) -> Dict[str, Any]:
    """Return {'is_stale': bool, 'age_hours': float, 'reasons': [...]}. Does not re-query live systems."""
    generated_at = _parse_timestamp(matrix["generated_at"])
    age_hours = (_utc_now() - generated_at).total_seconds() / 3600.0
    reasons: List[str] = []
    if age_hours > max_age_hours:
        reasons.append(f"artifact age {age_hours:.2f}h exceeds max_age_hours={max_age_hours}")

    recomputed_fingerprint = fingerprint_rows(matrix.get("rows", []))
    if recomputed_fingerprint != matrix.get("source_data_fingerprint"):
        reasons.append("row content does not match stored source_data_fingerprint (artifact tampered or corrupted)")

    return {
        "is_stale": bool(reasons),
        "age_hours": round(age_hours, 2),
        "reasons": reasons,
    }


def _cmd_validate(args: argparse.Namespace) -> int:
    matrix = load_matrix(Path(args.path), expected_domain=args.domain)
    print(
        json.dumps(
            {
                "valid": True,
                "domain": matrix["domain"],
                "schema_version": matrix["schema_version"],
                "generated_at": matrix["generated_at"],
                "row_count": len(matrix.get("rows", [])),
            },
            indent=2,
        )
    )
    return 0


def _cmd_check_staleness(args: argparse.Namespace) -> int:
    matrix = load_matrix(Path(args.path), expected_domain=args.domain)
    result = check_staleness(matrix, max_age_hours=args.max_age_hours)
    print(json.dumps(result, indent=2))
    return 1 if result["is_stale"] else 0


def _cmd_find_latest(args: argparse.Namespace) -> int:
    path = find_latest_matrix(args.domain, artifacts_dir=Path(args.artifacts_dir))
    if not path:
        print(json.dumps({"found": False}))
        return 1
    print(json.dumps({"found": True, "path": str(path)}))
    return 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="resolution_matrix artifact helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate a resolution_matrix artifact")
    validate.add_argument("--path", required=True)
    validate.add_argument("--domain", choices=sorted(VALID_DOMAINS), default=None)
    validate.set_defaults(func=_cmd_validate)

    staleness = subparsers.add_parser("check-staleness", help="Check artifact age/integrity; exit 1 if stale")
    staleness.add_argument("--path", required=True)
    staleness.add_argument("--domain", choices=sorted(VALID_DOMAINS), default=None)
    staleness.add_argument("--max-age-hours", type=float, required=True)
    staleness.set_defaults(func=_cmd_check_staleness)

    find_latest = subparsers.add_parser("find-latest", help="Find newest artifact for a domain")
    find_latest.add_argument("--domain", choices=sorted(VALID_DOMAINS), required=True)
    find_latest.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR))
    find_latest.set_defaults(func=_cmd_find_latest)

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        return args.func(args)
    except ResolutionMatrixError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
