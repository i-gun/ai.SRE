---
name: 'emailer-mail-operations'
description: 'Outlook desktop COM mail operations skill for redaction-aware draft-for-review composition and recursive inbox/folder reading, using non-secret .env configuration only.'
keywords: ['outlook', 'email', 'send', 'read', 'redaction', 'com', 'pywin32']
---

# Emailer Mail Operations Skill

This skill provides redaction-aware compose/read operations against the local Outlook desktop session validated by `emailer-connection`.

## Reuse-First Tooling Policy
- Prefer existing promoted tooling, shared functions, and approved libraries before adding new automation.
- If a new artifact is needed, extend the smallest existing one or make it promotion-ready with configurable inputs, minimal dependencies, clear logging/error handling, and a usage example.
- Avoid duplicate tooling and propagate any reusable change to relevant agents, prompts, skills, and docs.

## Required Environment Variables

Same as `emailer-connection` (no additional variables):
- `EMAILER_MAILBOX_ADDRESS` (optional)
- `EMAILER_WATCHED_FOLDERS`
- `EMAILER_ALLOWED_RECIPIENT_DOMAINS`
- `EMAILER_SEND_MODE`
- `EMAILER_REDACTION_RULESET_PATH`

## Capability 1: Compose Email (draft-for-review by default)

Expected behavior:
1. Require `to`, `subject`, `body`
2. Validate every recipient domain against `EMAILER_ALLOWED_RECIPIENT_DOMAINS`; reject the whole send if any recipient is not allowlisted, or if the allowlist is empty (fail-closed)
3. Apply the redaction ruleset to `body` (and `attachments` text content when text-based) before composing
4. Create the `MailItem` via COM, set `To`/`Subject`/`Body`/attachments
5. If `EMAILER_SEND_MODE == "draft_review"` (default): call `Item.Display()` and return control to the user for manual review/send
6. If `EMAILER_SEND_MODE == "auto_send"` (explicit opt-in only): call `Item.Send()`
7. Return a confirmation summary (`subject`, `recipient_count`, `redaction_count`, `mode`) — never the full body

## Capability 2: Read Folder(s)

Expected behavior:
1. Default to `EMAILER_WATCHED_FOLDERS` (e.g., `Inbox`, `Project/CTC/Alerts`) when no folder is specified
2. Traverse each configured folder path recursively through subfolders
3. Support filters: `unread_only`, `since`, `subject_contains`, `limit`
4. Return normalized summaries (`entry_id`, `folder_path`, `subject`, `sender`, `received_time`, `unread`, `body_preview` truncated and redacted)
5. Never return full raw bodies without explicit redaction pass first

## Capability 3: Mark Message Read/Unread

Expected behavior:
- Require `entry_id`
- Toggle `UnRead` property via COM
- Return confirmation with `entry_id` and new state

## Validation Policy

- Recipient allowlist is fail-closed: empty allowlist blocks all sends
- Redaction always runs before any body is displayed, sent, or returned to the caller
- `entry_id` required for read/mark operations; never guess or search by heuristic without explicit `subject_contains`/`since` filters

## Security Rules

- Never log unredacted message bodies
- Never disable or bypass the Object Model Guard/security prompt programmatically
- Never widen `EMAILER_ALLOWED_RECIPIENT_DOMAINS` without explicit user instruction

## Integration

Depends on:
- `emailer-connection` for COM session validation

Implementation file:
- `outlook_client.py`
