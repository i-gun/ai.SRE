"""Manual smoke-test CLI for the Emailer Outlook COM integration.

Usage:
    python scripts/emailer/send_test_email.py --to someone@example.com --subject "Test" --body "Hello"
    python scripts/emailer/send_test_email.py --read --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bootstrap_shared import PROJECT_ROOT, bootstrap_paths  # noqa: E402

bootstrap_paths(
    skill_paths=[
        PROJECT_ROOT / ".github" / "skills" / "emailer-mail-operations",
        PROJECT_ROOT / ".github" / "skills" / "emailer-connection",
    ]
)

from outlook_client import OutlookClient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", action="append", default=[], help="Recipient email address (repeatable)")
    parser.add_argument("--subject", default="Emailer test message")
    parser.add_argument("--body", default="This is a test message from the Emailer agent.")
    parser.add_argument("--read", action="store_true", help="Read messages instead of composing")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    client = OutlookClient.from_env()
    print(f"Connected as: {client.signed_in_address}")

    if args.read:
        messages = client.read_messages(limit=args.limit)
        print(json.dumps(messages, indent=2, default=str))
        return 0

    if not args.to:
        parser.error("--to is required unless --read is set")

    result = client.compose_email(to=args.to, subject=args.subject, body=args.body)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
