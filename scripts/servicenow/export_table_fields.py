#!/usr/bin/env python3
"""Export live ServiceNow table field metadata for future reference.

Default tables reflect the ServiceNow operational surface used by this repo:
incident, problem, and problem_task.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from servicenow.common import bootstrap

bootstrap(override_env=True)

from servicenow_client import ServiceNowAPIError, ServiceNowClient


DEFAULT_TABLES = ["incident", "problem", "problem_task"]
DICTIONARY_FIELDS = [
    "sys_id",
    "name",
    "element",
    "column_label",
    "internal_type",
    "reference",
    "max_length",
    "mandatory",
    "read_only",
    "active",
    "choice",
    "default_value",
    "display",
    "primary",
    "unique",
    "calculated",
    "virtual",
    "dependent_on_field",
    "attributes",
    "comments",
    "sys_updated_on",
]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export live ServiceNow field metadata to data/ as JSON."
    )
    parser.add_argument(
        "--tables",
        default=",".join(DEFAULT_TABLES),
        help="Comma-separated table names to inspect. Default: incident,problem,problem_task.",
    )
    parser.add_argument(
        "--output",
        help="Output JSON path. Defaults to data/servicenow_table_fields_<UTC timestamp>.json.",
    )
    return parser.parse_args(argv)


def display_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("display_value") or value.get("value") or ""
    return value


def raw_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("value") or ""
    return value


def request_result_list(
    client: ServiceNowClient,
    path: str,
    *,
    params: Dict[str, Any],
) -> List[Dict[str, Any]]:
    payload = client._request("GET", path, params=params)
    result = payload.get("result", [])
    if not isinstance(result, list):
        raise ServiceNowAPIError(f"Expected list result from {path}")
    return result


def get_table_record(client: ServiceNowClient, table: str) -> Optional[Dict[str, Any]]:
    rows = request_result_list(
        client,
        "/api/now/table/sys_db_object",
        params={
            "sysparm_query": f"name={table}",
            "sysparm_fields": "name,label,super_class,sys_id,sys_updated_on",
            "sysparm_display_value": "all",
            "sysparm_exclude_reference_link": "true",
            "sysparm_limit": "1",
        },
    )
    return rows[0] if rows else None


def get_table_hierarchy(client: ServiceNowClient, table: str) -> List[str]:
    hierarchy: List[str] = []
    current: Optional[str] = table
    seen = set()

    while current and current not in seen:
        seen.add(current)
        hierarchy.append(current)
        record = get_table_record(client, current)
        if not record:
            break
        superclass = display_value(record.get("super_class"))
        current = str(superclass).strip() if superclass else None

    return hierarchy


def normalize_dictionary_row(row: Dict[str, Any], source_table: str) -> Dict[str, Any]:
    normalized = {field: display_value(row.get(field, "")) for field in DICTIONARY_FIELDS}
    normalized["source_table"] = source_table
    normalized["raw_reference_sys_id"] = raw_value(row.get("reference", ""))
    normalized["raw_internal_type"] = raw_value(row.get("internal_type", ""))
    return normalized


def get_dictionary_fields(
    client: ServiceNowClient,
    source_tables: Iterable[str],
) -> List[Dict[str, Any]]:
    rows_by_element: Dict[str, Dict[str, Any]] = {}
    for source_table in source_tables:
        rows = request_result_list(
            client,
            "/api/now/table/sys_dictionary",
            params={
                "sysparm_query": f"name={source_table}^elementISNOTEMPTY",
                "sysparm_fields": ",".join(DICTIONARY_FIELDS),
                "sysparm_display_value": "all",
                "sysparm_exclude_reference_link": "true",
                "sysparm_limit": "10000",
                "sysparm_order_by": "element",
            },
        )
        for row in rows:
            element = str(display_value(row.get("element", ""))).strip()
            if element and element not in rows_by_element:
                rows_by_element[element] = normalize_dictionary_row(row, source_table)

    return [rows_by_element[element] for element in sorted(rows_by_element)]


def get_sample_available_keys(client: ServiceNowClient, table: str) -> List[str]:
    rows = request_result_list(
        client,
        f"/api/now/table/{table}",
        params={
            "sysparm_query": "ORDERBYDESCsys_updated_on",
            "sysparm_display_value": "all",
            "sysparm_exclude_reference_link": "true",
            "sysparm_limit": "1",
        },
    )
    if not rows:
        return []
    return sorted(rows[0].keys())


def sampled_field_entry(table: str, element: str) -> Dict[str, Any]:
    entry = {field: "" for field in DICTIONARY_FIELDS}
    entry.update(
        {
            "name": table,
            "element": element,
            "source_table": table,
            "metadata_source": "sample_record_key",
            "raw_reference_sys_id": "",
            "raw_internal_type": "",
        }
    )
    return entry


def export_table(client: ServiceNowClient, table: str) -> Dict[str, Any]:
    warnings: List[str] = []
    try:
        hierarchy = get_table_hierarchy(client, table)
    except ServiceNowAPIError as exc:
        hierarchy = [table]
        warnings.append(f"Could not inspect sys_db_object hierarchy: {exc}")

    try:
        fields = get_dictionary_fields(client, hierarchy)
    except ServiceNowAPIError as exc:
        fields = []
        warnings.append(f"Could not inspect sys_dictionary fields: {exc}")

    try:
        sample_available_keys = get_sample_available_keys(client, table)
    except ServiceNowAPIError as exc:
        sample_available_keys = []
        warnings.append(f"Could not sample table record keys: {exc}")

    dictionary_elements = {field["element"] for field in fields}
    sample_only_keys = [key for key in sample_available_keys if key not in dictionary_elements]
    metadata_source = "sys_dictionary"
    if not fields and sample_available_keys:
        fields = [sampled_field_entry(table, key) for key in sample_available_keys]
        metadata_source = "sample_record_keys"
    elif sample_only_keys:
        fields.extend(sampled_field_entry(table, key) for key in sample_only_keys)
        fields = sorted(fields, key=lambda item: item["element"])
        metadata_source = "sys_dictionary_plus_sample_record_keys"

    return {
        "table": table,
        "table_hierarchy": hierarchy,
        "metadata_source": metadata_source,
        "field_count": len(fields),
        "fields": fields,
        "sample_record_key_count": len(sample_available_keys),
        "sample_record_keys": sample_available_keys,
        "sample_only_keys": sample_only_keys,
        "warnings": warnings,
    }


def default_output_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "data" / f"servicenow_table_fields_{timestamp}.json"


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    tables = [table.strip() for table in args.tables.split(",") if table.strip()]
    if not tables:
        raise SystemExit("At least one table must be provided via --tables.")

    client = ServiceNowClient.from_env()
    output_path = Path(args.output) if args.output else default_output_path()
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "generated_at": exported_at,
        "source": {
            "host": client.config.host,
            "tables": tables,
            "assignment_group_scope_count": len(client.config.assignment_groups),
        },
        "tables": [export_table(client, table) for table in tables],
    }

    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "tables": tables}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())