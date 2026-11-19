"""Create (or update) the Bedrock guardrail from guardrail/guardrail.json and publish a version.

Usage: AWS_PROFILE=<profile> python tools/create_guardrail.py
Writes GUARDRAIL_ID and GUARDRAIL_VERSION into .env (and prints them).
Requires bedrock:CreateGuardrail, UpdateGuardrail, CreateGuardrailVersion, ListGuardrails.
"""
from __future__ import annotations

import json
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
REGION = "us-east-1"


def load_aws_profile() -> None:
    """Use AWS_PROFILE from .env when it is not already set in the shell."""
    import os

    env_file = ROOT / ".env"
    if env_file.exists() and not os.environ.get("AWS_PROFILE"):
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("AWS_PROFILE=") and line.split("=", 1)[1].strip():
                os.environ["AWS_PROFILE"] = line.split("=", 1)[1].strip().strip('"')


def main() -> None:
    load_aws_profile()
    body = json.loads((ROOT / "guardrail" / "guardrail.json").read_text(encoding="utf-8"))
    client = boto3.client("bedrock", region_name=REGION)
    existing = [g for g in client.list_guardrails()["guardrails"] if g["name"] == body["name"]]
    if existing:
        guardrail_id = existing[0]["id"]
        client.update_guardrail(guardrailIdentifier=guardrail_id, **body)
        print(f"updated guardrail {guardrail_id}")
    else:
        guardrail_id = client.create_guardrail(**body)["guardrailId"]
        print(f"created guardrail {guardrail_id}")
    version = client.create_guardrail_version(
        guardrailIdentifier=guardrail_id, description="Published by tools/create_guardrail.py"
    )["version"]
    print(f"\nGUARDRAIL_ID={guardrail_id}\nGUARDRAIL_VERSION={version}")
    write_env({"GUARDRAIL_ID": guardrail_id, "GUARDRAIL_VERSION": version})


def write_env(values: dict[str, str]) -> None:
    """Store the new guardrail ID and version in .env so nobody has to paste them."""
    env_file = ROOT / ".env"
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    for key, value in values.items():
        lines = [line for line in lines if not line.startswith(f"{key}=")] + [f"{key}={value}"]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Saved GUARDRAIL_ID and GUARDRAIL_VERSION to .env")


if __name__ == "__main__":
    main()
