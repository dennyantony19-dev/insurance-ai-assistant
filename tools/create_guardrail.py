"""Create (or update) the Bedrock guardrail from guardrail/guardrail.json and publish a version.

Usage: AWS_PROFILE=<profile> python tools/create_guardrail.py
Prints GUARDRAIL_ID and GUARDRAIL_VERSION lines to paste into .env.
Requires bedrock:CreateGuardrail, UpdateGuardrail, CreateGuardrailVersion, ListGuardrails.
"""
from __future__ import annotations

import json
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
REGION = "us-east-1"


def main() -> None:
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


if __name__ == "__main__":
    main()
