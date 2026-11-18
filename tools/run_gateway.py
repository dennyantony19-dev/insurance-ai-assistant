"""Start the LiteLLM gateway with variables from .env (works on Windows, macOS and Linux).

Usage: python tools/run_gateway.py [--port 4000]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        sys.exit("No .env file. Copy .env.example to .env and fill it in first.")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))
    missing = [k for k in ("BEDROCK_MODEL_ID", "GUARDRAIL_ID", "GUARDRAIL_VERSION", "LITELLM_MASTER_KEY")
               if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="4000")
    args = parser.parse_args()
    load_env()
    litellm = shutil.which("litellm")
    if not litellm:
        sys.exit("litellm not found. Activate the venv and run: pip install -r requirements.txt")
    config = ROOT / "gateway" / "litellm_config.yaml"
    return subprocess.call([litellm, "--config", str(config), "--port", args.port, "--host", "127.0.0.1"])


if __name__ == "__main__":
    raise SystemExit(main())
