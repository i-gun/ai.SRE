# Emailer Mail Operations

This skill package provides Outlook desktop COM mail helpers backed by non-secret `.env` configuration (no auth credentials required — it rides the signed-in Outlook session).

## Required Variables

- `EMAILER_MAILBOX_ADDRESS` (optional validation)
- `EMAILER_WATCHED_FOLDERS`
- `EMAILER_ALLOWED_RECIPIENT_DOMAINS`
- `EMAILER_SEND_MODE`
- `EMAILER_REDACTION_RULESET_PATH`

## Included Files

- `SKILL.md` - behavior contract for compose/read/mark-read operations
- `outlook_client.py` - implementation for Outlook COM operations

## Supported Workflows

- Compose a redaction-aware email and open it for review (default) or auto-send (explicit opt-in)
- Recursively read Inbox and configured folder trees with unread/since/subject filters
- Mark a message read/unread by `entry_id`

## Usage Example

```python
from outlook_client import OutlookClient

client = OutlookClient.from_env()

client.compose_email(
    to=["oncall-team@example.com"],
    subject="RCA Summary: INC0084281",
    body="Draft summary body...",
)

messages = client.read_messages(unread_only=True, limit=10)

client.mark_read(messages[0]["entry_id"])
```

## Notes

- Requires `pywin32` and a running, signed-in Outlook desktop client on the local machine — this is not portable to servers/CI
- Recipient allowlist is fail-closed: sending is blocked entirely while `EMAILER_ALLOWED_RECIPIENT_DOMAINS` is empty
- Redaction always runs before any body is displayed, sent, or returned
- Default send mode is `draft_review`; `auto_send` must be explicitly opted into
