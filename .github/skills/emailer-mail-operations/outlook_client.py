"""Outlook desktop COM mail operations: redaction-aware compose and folder reads."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "emailer-connection"))

from outlook_env import (  # noqa: E402
    EmailerConfig,
    EmailerConnectionError,
    load_emailer_config_from_env,
    validate_outlook_connection,
)

# Outlook MAPI folder-type constant for the default Inbox.
OL_FOLDER_INBOX = 6
BODY_PREVIEW_LENGTH = 300


class EmailerValidationError(Exception):
    """Raised when Emailer operation inputs fail validation checks."""


class EmailerAPIError(Exception):
    """Raised when Outlook COM operations fail."""


@dataclass
class RedactionResult:
    text: str
    redaction_count: int


def _load_redaction_patterns(ruleset_path: str) -> List[Dict[str, str]]:
    payload = json.loads(Path(ruleset_path).read_text(encoding="utf-8"))
    return payload.get("patterns", [])


def redact_text(text: str, ruleset_path: str) -> RedactionResult:
    if not text:
        return RedactionResult(text=text, redaction_count=0)

    patterns = _load_redaction_patterns(ruleset_path)
    redaction_count = 0
    redacted = text
    for pattern in patterns:
        compiled = re.compile(pattern["regex"])
        redacted, n = compiled.subn(pattern["replacement"], redacted)
        redaction_count += n

    return RedactionResult(text=redacted, redaction_count=redaction_count)


def _validate_recipients(to: List[str], allowed_domains: List[str]) -> None:
    if not to:
        raise EmailerValidationError("At least one recipient is required")
    if not allowed_domains:
        raise EmailerValidationError(
            "EMAILER_ALLOWED_RECIPIENT_DOMAINS is empty; sending is blocked (fail-closed)"
        )
    for recipient in to:
        domain = recipient.split("@")[-1].lower()
        if domain not in allowed_domains:
            raise EmailerValidationError(
                f"Recipient domain not allowlisted: {recipient} (allowed: {allowed_domains})"
            )


class OutlookClient:
    """Client wrapper for Outlook desktop COM mail operations."""

    def __init__(self, config: Optional[EmailerConfig] = None):
        self.config = config or load_emailer_config_from_env()
        self.signed_in_address = validate_outlook_connection(self.config)

        import win32com.client  # noqa: WPS433 (deferred import by design)

        self._outlook = win32com.client.Dispatch("Outlook.Application")
        self._namespace = self._outlook.GetNamespace("MAPI")

    @classmethod
    def from_env(cls) -> "OutlookClient":
        return cls(load_emailer_config_from_env())

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------
    def compose_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not subject:
            raise EmailerValidationError("Subject is required")
        if not body:
            raise EmailerValidationError("Body is required")

        _validate_recipients(to, self.config.allowed_recipient_domains)
        redaction = redact_text(body, self.config.redaction_ruleset_path)

        try:
            mail_item = self._outlook.CreateItem(0)  # 0 = olMailItem
            mail_item.To = "; ".join(to)
            mail_item.Subject = subject
            mail_item.Body = redaction.text

            for attachment_path in attachments or []:
                mail_item.Attachments.Add(str(Path(attachment_path).resolve()))

            if self.config.send_mode == "auto_send":
                mail_item.Send()
            else:
                mail_item.Display()
        except Exception as exc:
            raise EmailerAPIError(f"Outlook compose operation failed: {exc}") from exc

        return {
            "subject": subject,
            "recipient_count": len(to),
            "redaction_count": redaction.redaction_count,
            "mode": self.config.send_mode,
        }

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def _resolve_folder(self, folder_path: str):
        parts = [p for p in folder_path.split("/") if p]
        if not parts:
            raise EmailerValidationError("Folder path must not be empty")

        if parts[0].lower() == "inbox":
            folder = self._namespace.GetDefaultFolder(OL_FOLDER_INBOX)
            parts = parts[1:]
        else:
            folder = None
            for root_folder in self._namespace.Folders:
                try:
                    folder = root_folder.Folders[parts[0]]
                    break
                except Exception:
                    continue
            if folder is None:
                raise EmailerAPIError(f"Folder not found: {folder_path}")
            parts = parts[1:]

        for part in parts:
            try:
                folder = folder.Folders[part]
            except Exception as exc:
                raise EmailerAPIError(f"Subfolder not found: {part} in {folder_path}") from exc

        return folder

    def _iter_folder_recursive(self, folder, folder_path: str):
        yield folder, folder_path
        for subfolder in folder.Folders:
            sub_path = f"{folder_path}/{subfolder.Name}"
            yield from self._iter_folder_recursive(subfolder, sub_path)

    def read_messages(
        self,
        folder_paths: Optional[List[str]] = None,
        unread_only: bool = False,
        since: Optional[datetime] = None,
        subject_contains: Optional[str] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        folder_paths = folder_paths or self.config.watched_folders
        results: List[Dict[str, Any]] = []

        for path in folder_paths:
            root_folder = self._resolve_folder(path)
            for folder, resolved_path in self._iter_folder_recursive(root_folder, path):
                try:
                    items = folder.Items
                except Exception:
                    continue

                for item in items:
                    if len(results) >= limit:
                        return results
                    try:
                        if unread_only and not getattr(item, "UnRead", False):
                            continue
                        received_time = getattr(item, "ReceivedTime", None)
                        if since and received_time and received_time < since:
                            continue
                        subject = getattr(item, "Subject", "") or ""
                        if subject_contains and subject_contains.lower() not in subject.lower():
                            continue

                        body = getattr(item, "Body", "") or ""
                        redaction = redact_text(body, self.config.redaction_ruleset_path)
                        preview = redaction.text[:BODY_PREVIEW_LENGTH]

                        results.append(
                            {
                                "entry_id": getattr(item, "EntryID", None),
                                "folder_path": resolved_path,
                                "subject": subject,
                                "sender": getattr(item, "SenderEmailAddress", ""),
                                "received_time": str(received_time) if received_time else None,
                                "unread": getattr(item, "UnRead", False),
                                "body_preview": preview,
                            }
                        )
                    except Exception:
                        continue

        return results

    def mark_read(self, entry_id: str, unread: bool = False) -> Dict[str, Any]:
        if not entry_id:
            raise EmailerValidationError("entry_id is required")
        try:
            item = self._namespace.GetItemFromID(entry_id)
            item.UnRead = unread
            item.Save()
        except Exception as exc:
            raise EmailerAPIError(f"Unable to update read state for {entry_id}: {exc}") from exc

        return {"entry_id": entry_id, "unread": unread}
