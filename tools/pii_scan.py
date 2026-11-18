"""Pre-commit hook: fail if staged files contain PII or secrets (policy P5).

Uses the same detectors as the gateway. Usage: python tools/pii_scan.py FILE [FILE ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails_core.pii import build_detectors, scan  # noqa: E402

SKIP_PARTS = {"policies", "evidence"}  # the policy defines the patterns; evidence holds masked logs


def main(paths: list[str]) -> int:
    detectors = build_detectors()
    failed = False
    for name in paths:
        path = Path(name)
        if not path.is_file() or SKIP_PARTS & set(path.parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, 1):
            result = scan(line, detectors)
            if result.findings:
                failed = True
                print(f"{name}:{lineno}: {', '.join(result.types())} found (use synthetic placeholders)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
