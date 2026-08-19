"""Export the visible Jira Cloud field catalog to a credential-free JSON snapshot."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from bootstrap_shared import bootstrap_paths

bootstrap_paths(
    skill_paths=[
        ROOT / ".github" / "skills" / "jira-authentication",
        ROOT / ".github" / "skills" / "jira-issue-operations",
    ],
    override_env=True,
)

from jira_client import JiraClient


def main() -> Path:
    fields = JiraClient.from_env().list_fields()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    output_path = ROOT / "data" / f"jira_field_catalog_{generated_at}.json"
    output_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "field_count": len(fields),
                "fields": fields,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path


if __name__ == "__main__":
    print(main())