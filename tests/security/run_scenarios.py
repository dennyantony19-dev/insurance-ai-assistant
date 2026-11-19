"""Run the security scenarios and write evidence/scenario_results.md (+ .json).

  python tests/security/run_scenarios.py          offline: local layer, generated rules, scanners
  python tests/security/run_scenarios.py --live   also calls Bedrock ApplyGuardrail (needs AWS + .env)

Manual scenarios are listed with their steps; record outcomes in evidence/manual_results.yaml
as `S01: {result: pass, note: "..."}` and they are merged into the report.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from guardrails_core.permissions import evaluate  # noqa: E402
from guardrails_core.pii import scan  # noqa: E402
from guardrails_core.topics import check_text  # noqa: E402

EVIDENCE = ROOT / "evidence"


def local_text_decision(text: str, role: str) -> tuple[str, str]:
    result = scan(text)
    if result.blocked:
        return "block", "local: " + ",".join(result.types())
    if role == "user":
        reason = check_text(text)
        if reason:
            return "block", "local: " + reason
    if result.masked:
        return "mask", "local: " + ",".join(result.types())
    return "allow", "local: no findings"


def bedrock_text_decision(text: str, role: str) -> tuple[str, str]:
    import boto3

    env = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines() if "=" in line)
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    resp = client.apply_guardrail(
        guardrailIdentifier=env.get("GUARDRAIL_ID", os.environ.get("GUARDRAIL_ID")),
        guardrailVersion=env.get("GUARDRAIL_VERSION", os.environ.get("GUARDRAIL_VERSION")),
        source="OUTPUT" if role == "output" else "INPUT",
        content=[{"text": {"text": text}}],
    )
    if resp["action"] != "GUARDRAIL_INTERVENED":
        return "allow", "bedrock: none"
    a = resp["assessments"][0] if resp.get("assessments") else {}
    hits = []
    blocked = False
    for t in a.get("topicPolicy", {}).get("topics", []):
        hits.append("topic:" + t["name"])
        blocked |= t["action"] == "BLOCKED"
    for f in a.get("contentPolicy", {}).get("filters", []):
        hits.append("content:" + f["type"])
        blocked |= f["action"] == "BLOCKED"
    sip = a.get("sensitiveInformationPolicy", {})
    for e in sip.get("piiEntities", []) + sip.get("regexes", []):
        hits.append("pii:" + e.get("type", e.get("name", "?")))
        blocked |= e["action"] == "BLOCKED"
    return ("block" if blocked else "mask"), "bedrock: " + ",".join(hits)


def code_decision(code: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "generated.py"
        f.write_text(code)
        notes = []
        bandit = subprocess.run([sys.executable, "-m", "bandit", "-q", "-ll", str(f)], capture_output=True, text=True)
        if bandit.returncode not in (0, 1):
            notes.append("bandit unavailable")
        elif bandit.returncode == 1:
            ids = sorted({line.split("]")[0].split("[")[-1] for line in bandit.stdout.splitlines() if "Issue: [" in line})
            notes.append("bandit " + ",".join(ids))
        pii = subprocess.run([sys.executable, str(ROOT / "tools" / "pii_scan.py"), str(f)], capture_output=True, text=True)
        if pii.returncode == 1:
            notes.append("pii_scan")
        return ("block" if notes and notes != ["bandit unavailable"] else "allow"), "; ".join(notes) or "clean"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="also call Bedrock ApplyGuardrail")
    args = parser.parse_args()
    scenarios = yaml.safe_load((Path(__file__).parent / "scenarios.yaml").read_text())["scenarios"]
    rules = json.loads((ROOT / "opencode.json").read_text())["permissions"]
    manual_file = EVIDENCE / "manual_results.yaml"
    manual = yaml.safe_load(manual_file.read_text()) if manual_file.exists() else {}
    rows = []
    for s in scenarios:
        kind, expect = s["kind"], s["expect"]
        if kind == "text":
            role = s.get("role", "user")
            got, note = local_text_decision(s["text"], role)
            if args.live:
                b_got, b_note = bedrock_text_decision(s["text"], role)
                note += f" | {b_note}"
                # Layers combine: the strictest decision wins.
                order = ["allow", "mask", "block"]
                got = max(got, b_got, key=order.index)
        elif kind == "shell":
            got, note = evaluate(rules, "shell", s["command"]), "opencode rules"
        elif kind in ("edit", "read", "external_directory"):
            got, note = evaluate(rules, kind, s["path"]), "opencode rules"
        elif kind == "code":
            got, note = code_decision(s["code"])
        else:
            m = (manual or {}).get(s["id"])
            rows.append({**s, "got": "-", "status": m["result"].upper() if m else "MANUAL",
                         "note": (m or {}).get("note", s["steps"])})
            continue
        rows.append({**s, "got": got, "status": "PASS" if got == expect else "FAIL", "note": note})

    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / "scenario_results.json").write_text(json.dumps(rows, indent=2))
    mode = "live (local + Bedrock)" if args.live else "offline (local layer and generated rules only)"
    live_file = EVIDENCE / "live_run.yaml"
    live = yaml.safe_load(live_file.read_text()) if live_file.exists() else None
    live_line = [f"Recorded live run ({live['date']}): {live['result']}", ""] if live else []
    lines = [f"# Scenario results ({mode})", "", *live_line,
             "| ID | Scenario | Expected | Got | Status | Evidence |", "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| {r['id']} | {r['title']} | {r['expect']} | {r['got']} | {r['status']} | {r['note']} |")
    counts = {k: sum(r["status"] == k for r in rows) for k in ("PASS", "FAIL", "MANUAL")}
    lines += ["", f"PASS {counts['PASS']} · FAIL {counts['FAIL']} · MANUAL (pending) {counts['MANUAL']}", ""]
    (EVIDENCE / "scenario_results.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
