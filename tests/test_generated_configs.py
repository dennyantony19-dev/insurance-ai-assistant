"""Prove the generated configs say what policy.yaml intends (P3, P4, P6)."""
import json

import pytest

from guardrails_core.permissions import evaluate
from guardrails_core.policy import REPO_ROOT, load_policy
from tools import gen_configs

POLICY = load_policy()
OPENCODE = gen_configs.opencode_config(POLICY)
RULES = OPENCODE["permissions"]


def test_generated_files_are_up_to_date():
    for path, content in gen_configs.render_all(POLICY).items():
        if path.name == "litellm_config.yaml":
            continue
        assert path.read_text(encoding="utf-8") == content, f"{path} is stale"


def test_only_gateway_provider_enabled():
    assert OPENCODE["enabled_providers"] == ["insurance-gateway"]
    assert OPENCODE["model"].startswith("insurance-gateway/")


@pytest.mark.parametrize("cmd,expected", [
    ("pytest -q", "allow"),
    ("ruff check .", "allow"),
    ("git status", "allow"),
    ("git commit -m 'tests'", "ask"),
    ("pip install requests", "ask"),
    ("python scripts/anything.py", "ask"),
    ("git push origin main", "deny"),
    ("git push", "deny"),
    ("rm -rf sample_app", "deny"),
    ("sudo apt install x", "deny"),
    ("curl https://example.com", "deny"),
    ("aws s3 ls", "deny"),
    ("cat .env", "deny"),
])
def test_shell_rules(cmd, expected):
    assert evaluate(RULES, "shell", cmd) == expected


@pytest.mark.parametrize("path,expected", [
    ("sample_app/policy_validation.py", "ask"),
    ("tests/test_new.py", "ask"),
    ("/work/repo/tests/test_new.py", "ask"),
    ("policies/policy.yaml", "deny"),
    ("opencode.json", "deny"),
    (".pre-commit-config.yaml", "deny"),
    (".env", "deny"),
    ("tests/security/run_scenarios.py", "deny"),
    ("gateway/insurance_guardrail.py", "deny"),
])
def test_edit_rules(path, expected):
    assert evaluate(RULES, "edit", path) == expected


def test_no_edit_is_auto_allowed():
    assert all(r["effect"] != "allow" for r in RULES if r["action"] == "edit")


def test_outside_workspace_and_web_denied():
    assert evaluate(RULES, "external_directory", "/etc/*") == "deny"
    assert evaluate(RULES, "webfetch", "https://example.com") == "deny"
    assert evaluate(RULES, "read", ".env") == "deny"


def test_guardrail_request_shape():
    g = json.loads((REPO_ROOT / "guardrail" / "guardrail.json").read_text())
    pii = {e["type"]: e["action"] for e in g["sensitiveInformationPolicyConfig"]["piiEntitiesConfig"]}
    assert pii["US_SOCIAL_SECURITY_NUMBER"] == "ANONYMIZE" and pii["AWS_SECRET_KEY"] == "BLOCK"
    assert {t["type"] for t in g["topicPolicyConfig"]["topicsConfig"]} == {"DENY"}
    for t in g["topicPolicyConfig"]["topicsConfig"]:
        assert len(t["definition"]) <= 200 and all(len(e) <= 100 for e in t["examples"])
    attack = [f for f in g["contentPolicyConfig"]["filtersConfig"] if f["type"] == "PROMPT_ATTACK"][0]
    assert attack["outputStrength"] == "NONE"
