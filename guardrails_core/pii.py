"""Local PII and secret detection with typed-placeholder masking (policy P1).

This is the first, offline layer. Bedrock Guardrails is the second layer.
Neither is complete: see the residual-risk section of the design doc.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .policy import load_policy


@dataclass(frozen=True)
class Detector:
    type: str
    action: str  # "mask" or "block"
    regex: re.Pattern[str]
    luhn: bool = False
    allow: tuple[str, ...] = ()


@dataclass
class ScanResult:
    text: str
    findings: list[dict[str, str]] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f["action"] == "block" for f in self.findings)

    @property
    def masked(self) -> bool:
        return any(f["action"] == "mask" for f in self.findings)

    def types(self) -> list[str]:
        return sorted({f["type"] for f in self.findings})


def _luhn_ok(candidate: str) -> bool:
    digits = [int(c) for c in candidate if c.isdigit()]
    if not 13 <= len(digits) <= 16:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def build_detectors(policy: dict[str, Any] | None = None) -> list[Detector]:
    policy = policy or load_policy()
    detectors = []
    for d in policy["sensitive_data"]["local_detectors"]:
        detectors.append(
            Detector(
                type=d["type"],
                action=d["action"],
                regex=re.compile(d["pattern"]),
                luhn=bool(d.get("luhn", False)),
                allow=tuple(d.get("allow", ())),
            )
        )
    return detectors


def scan(text: str, detectors: list[Detector] | None = None) -> ScanResult:
    """Mask maskable entities as {TYPE}; record (but never return) blocked secrets.

    Findings never contain the matched value, so they are safe to log.
    """
    detectors = detectors if detectors is not None else build_detectors()
    result = ScanResult(text=text)
    for det in detectors:
        def _replace(match: re.Match[str], det: Detector = det) -> str:
            value = match.group(0)
            if det.luhn and not _luhn_ok(value):
                return value
            if any(a in value for a in det.allow):
                return value
            result.findings.append({"type": det.type, "action": det.action})
            return "{" + det.type + "}" if det.action == "mask" else "{REDACTED_" + det.type + "}"

        result.text = det.regex.sub(_replace, result.text)
    return result
