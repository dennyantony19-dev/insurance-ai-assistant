"""Load the single policy file (policies/policy.yaml)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_PATH = REPO_ROOT / "policies" / "policy.yaml"


@lru_cache(maxsize=4)
def load_policy(path: str | None = None) -> dict[str, Any]:
    """Return the parsed policy. Cached; pass a path to load a different file."""
    policy_path = Path(path) if path else DEFAULT_POLICY_PATH
    with policy_path.open(encoding="utf-8") as fh:
        policy = yaml.safe_load(fh)
    if not isinstance(policy, dict) or policy.get("version") != 1:
        raise ValueError(f"{policy_path} is not a version-1 policy file")
    return policy
