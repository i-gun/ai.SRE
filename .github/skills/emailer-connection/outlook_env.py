"""Outlook desktop COM connection configuration loader and validator."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

SUPPORTED_SEND_MODES = ("draft_review", "auto_send")
DEFAULT_SEND_MODE = "draft_review"
DEFAULT_WATCHED_FOLDERS = ("Inbox",)
DEFAULT_REDACTION_RULESET_PATH = "scripts/emailer/redaction_rules.json"


class EmailerConfigError(Exception):
    """Raised when Emailer configuration is invalid."""


class EmailerConnectionError(Exception):
    """Raised when Outlook COM automation is unreachable."""


@dataclass
class EmailerConfig:
    mailbox_address: Optional[str]
    watched_folders: List[str] = field(default_factory=lambda: list(DEFAULT_WATCHED_FOLDERS))
    allowed_recipient_domains: List[str] = field(default_factory=list)
    send_mode: str = DEFAULT_SEND_MODE
    redaction_ruleset_path: str = DEFAULT_REDACTION_RULESET_PATH


def _split_csv(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_emailer_config_from_env() -> EmailerConfig:
    mailbox_address = os.getenv("EMAILER_MAILBOX_ADDRESS", "").strip() or None

    watched_raw = os.getenv("EMAILER_WATCHED_FOLDERS", "").strip()
    watched_folders = _split_csv(watched_raw) if watched_raw else list(DEFAULT_WATCHED_FOLDERS)

    allowed_raw = os.getenv("EMAILER_ALLOWED_RECIPIENT_DOMAINS", "").strip()
    allowed_domains = [d.lower() for d in _split_csv(allowed_raw)]

    send_mode = os.getenv("EMAILER_SEND_MODE", DEFAULT_SEND_MODE).strip() or DEFAULT_SEND_MODE
    if send_mode not in SUPPORTED_SEND_MODES:
        raise EmailerConfigError(
            f"EMAILER_SEND_MODE must be one of {SUPPORTED_SEND_MODES}, got: {send_mode!r}"
        )

    ruleset_path = os.getenv("EMAILER_REDACTION_RULESET_PATH", "").strip() or DEFAULT_REDACTION_RULESET_PATH
    if not Path(ruleset_path).is_file():
        raise EmailerConfigError(f"Redaction ruleset file not found: {ruleset_path}")
    try:
        json.loads(Path(ruleset_path).read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise EmailerConfigError(f"Redaction ruleset file is not valid JSON: {ruleset_path}") from exc

    return EmailerConfig(
        mailbox_address=mailbox_address,
        watched_folders=watched_folders,
        allowed_recipient_domains=allowed_domains,
        send_mode=send_mode,
        redaction_ruleset_path=ruleset_path,
    )


def validate_outlook_connection(config: Optional[EmailerConfig] = None):
    """Validate pywin32 availability and an active Outlook COM session.

    Returns the signed-in mailbox SMTP address for cross-check by callers.
    Raises EmailerConnectionError on any failure.
    """
    config = config or load_emailer_config_from_env()

    try:
        import win32com.client  # noqa: WPS433 (deferred import by design)
    except ImportError as exc:
        raise EmailerConnectionError(
            "pywin32 is not installed. Install it with: pip install pywin32"
        ) from exc

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        current_user = namespace.CurrentUser
        signed_in_address = current_user.AddressEntry.GetExchangeUser().PrimarySmtpAddress
    except Exception as exc:  # COM errors surface as generic exceptions
        raise EmailerConnectionError(
            "Unable to reach Outlook via COM automation. Ensure Outlook is installed, "
            "running, and signed in, and that no security prompt is blocking automation."
        ) from exc

    if config.mailbox_address and signed_in_address.lower() != config.mailbox_address.lower():
        raise EmailerConnectionError(
            f"Configured EMAILER_MAILBOX_ADDRESS ({config.mailbox_address}) does not match "
            f"the signed-in Outlook account ({signed_in_address})."
        )

    return signed_in_address
