#!/usr/bin/env python3
"""Shared Atlassian Document Format helpers for Jira payloads."""

from __future__ import annotations

from typing import Any, Dict


def text_to_adf(text: str) -> Dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }
