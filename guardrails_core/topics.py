"""Coarse local checks for denied topics and prompt attacks (policy P2).

Keyword patterns are easy to evade; they exist so that obvious abuse is stopped
even when Bedrock is unreachable, and so the behaviour can be tested offline.
Bedrock Guardrails denied topics and the PROMPT_ATTACK filter are the real check.
"""
from __future__ import annotations

import re
from typing import Any

from .policy import load_policy


def check_text(text: str, policy: dict[str, Any] | None = None) -> str | None:
    """Return the name of the violated rule, or None when the text is allowed."""
    policy = policy or load_policy()
    for topic in policy["denied_topics"]:
        for pattern in topic.get("local_patterns", []):
            if re.search(pattern, text):
                return f"denied topic: {topic['name']}"
    for pattern in policy["prompt_attack"].get("local_patterns", []):
        if re.search(pattern, text):
            return "prompt attack"
    return None
