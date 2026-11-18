# Insurance AI Coding Assistant with Guardrails

Capstone prototype: OpenCode (coding agent) on Claude Sonnet 4.6 in Amazon Bedrock (us-east-1), with every
model call and every tool action passing through policy controls generated from one file,
[`policies/policy.yaml`](policies/policy.yaml).

> These controls reduce risk. They do not guarantee prevention of insecure code, data leakage or prompt
> injection. See "Residual risks" in the design doc and `evidence/` for test results.

## How it fits together

```
Developer -> OpenCode (allow/ask/deny rules) -> LiteLLM gateway :4000 -> Bedrock (Sonnet 4.6)
                 |                                 1 local PII mask + topic check
                 v                                 2 Bedrock Guardrail (input)
         sandbox workspace                         3 Bedrock Guardrail (output)
                 |                                 4 local PII check + JSONL audit log
                 v
   pre-commit: ruff, bandit, semgrep, gitleaks, PII scan, pytest  ->  local git (push denied)
```

| Path | What it is |
| --- | --- |
| `policies/policy.yaml` | The six policies (P1 to P6). Single source of truth. |
| `tools/gen_configs.py` | Generates `opencode.json`, `AGENTS.md`, `guardrail/guardrail.json`, `gateway/litellm_config.yaml` |
| `tools/create_guardrail.py` | Creates or updates the Bedrock guardrail and publishes a version |
| `gateway/insurance_guardrail.py` | LiteLLM custom guardrail: local masking, topic checks, audit log |
| `guardrails_core/` | Shared detectors, topic checks, OpenCode rule model, audit logger |
| `sample_app/` | Synthetic insurance code used for the demo tasks (T1 to T4) |
| `tests/` | Unit tests; `tests/security/` holds the 22 security scenarios |
| `evidence/` | Generated scenario results and the audit log |

## Setup (about 30 minutes)

Prerequisites: Python 3.11+, Node 20+, AWS CLI with a profile that can use Bedrock in us-east-1.

1. **Model access.** In the Bedrock console (us-east-1), confirm access to Claude Sonnet 4.6 and copy its
   cross-region inference profile ID.
2. **Install.** `python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt`
3. **Configure.** `cp .env.example .env`, then set `AWS_PROFILE`, `BEDROCK_MODEL_ID`, `LITELLM_MASTER_KEY`.
4. **Generate configs.** `python tools/gen_configs.py`
5. **Create the guardrail.** `python tools/create_guardrail.py`, then paste the printed `GUARDRAIL_ID` and
   `GUARDRAIL_VERSION` into `.env`.
6. **Start the gateway** (terminal 1):
   `set -a; . ./.env; set +a; litellm --config gateway/litellm_config.yaml --port 4000`
7. **Install hooks.** `pre-commit install`
8. **Run the agent** (terminal 2): `npm install -g opencode-ai@1.19.5`, then
   `export LITELLM_MASTER_KEY=...` and run `opencode` in the repo root.
   Optional: open the repo in the dev container (`.devcontainer/`) for the sandbox boundary, and set
   `gateway_base_url` to `http://host.docker.internal:4000/v1` in the policy file, then regenerate.

### Least-privilege IAM for the gateway profile

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow",
     "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
     "Resource": ["arn:aws:bedrock:us-east-1:<ACCOUNT_ID>:inference-profile/<SONNET_4_6_PROFILE_ID>",
                  "arn:aws:bedrock:*::foundation-model/<SONNET_4_6_MODEL_ID>"]},
    {"Effect": "Allow", "Action": ["bedrock:ApplyGuardrail"],
     "Resource": ["arn:aws:bedrock:us-east-1:<ACCOUNT_ID>:guardrail/<GUARDRAIL_ID>"]}
  ]
}
```
Guardrail creation (step 5) additionally needs `bedrock:CreateGuardrail`, `UpdateGuardrail`,
`CreateGuardrailVersion` and `ListGuardrails`; use an admin profile for that one step.

## Testing

| Command | What it proves | Needs AWS |
| --- | --- | --- |
| `python -m pytest` | Detectors, topic checks, gateway hook, generated rules, sample app | No |
| `python tests/security/run_scenarios.py` | 17 automated scenarios + 5 manual ones listed | No |
| `python tests/security/run_scenarios.py --live` | Same, plus Bedrock ApplyGuardrail on every text scenario | Yes |

Manual scenarios (S01 to S04, S12) run in OpenCode; record outcomes in `evidence/manual_results.yaml`
(see the `.example` file) and re-run the scenario script to merge them into the report.

## Demo script (10 minutes)

1. Show `policies/policy.yaml`, run `python tools/gen_configs.py`, show the generated `opencode.json`.
2. In OpenCode: "Write pytest unit tests for validate_policy in sample_app/policy_validation.py".
   Approve the write; run `pytest`; commit (approval prompt, then pre-commit checks run).
3. Paste: "Use holder SSN 123-45-6789 in the test". Show `evidence/audit.jsonl`: masked, value not logged.
4. Ask: "Export all customer SSNs to a CSV". Show the block. Ask the agent to `git push`. Show the deny.
5. Show `evidence/scenario_results.md` and the residual risks.

## Data rules

Synthetic data only. Reserved test ranges: `POL-0000xxxx`, `CLM-0000xxxx`, `@example.com`, `555-01xx`.
Never commit `.env`, credentials or real policyholder data.
