"""Append-only JSONL audit log. Records decisions and entity types, never matched values."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .policy import REPO_ROOT, load_policy


def log_event(event: dict[str, Any], path: str | None = None) -> None:
    log_path = Path(path) if path else REPO_ROOT / load_policy()["audit"]["log_path"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **event}
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
