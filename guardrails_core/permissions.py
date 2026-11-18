"""Offline model of OpenCode's permission matching, used to test the generated rules.

OpenCode evaluates ordered rules and the LAST matching rule wins; '*' matches any
characters including '/', '?' matches one character, and a pattern ending in '*'
also matches the bare command (https://opencode.ai/docs/permissions/).
This model lets CI prove the policy says what we intend. It does not replace
checking the real behaviour in OpenCode (scenarios S13-S17 are re-run live).
"""
from __future__ import annotations

import re
from typing import Any


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    out = []
    for ch in pattern:
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        else:
            out.append(re.escape(ch))
    regex = "".join(out)
    if pattern.endswith(" *"):
        # "git push *" also matches bare "git push"
        regex = regex[: -len(re.escape(" ") + ".*")] + "(?: .*)?"
    return re.compile(rf"^{regex}$", re.S)


def evaluate(rules: list[dict[str, Any]], action: str, resource: str, default: str = "ask") -> str:
    """Return allow / ask / deny for an action on a resource."""
    decision = default
    for rule in rules:
        if rule["action"] != action:
            continue
        if _glob_to_regex(rule["resource"]).match(resource):
            decision = rule["effect"]
    return decision
