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
| `tools/run_gateway.py` | Starts the LiteLLM gateway with `.env` loaded (any OS) |
| `gateway/insurance_guardrail.py` | LiteLLM custom guardrail: local masking, topic checks, audit log |
| `guardrails_core/` | Shared detectors, topic checks, OpenCode rule model, audit logger |
| `sample_app/` | Synthetic insurance code used for the demo tasks (T1 to T4) |
| `tests/` | Unit tests; `tests/security/` holds the 22 security scenarios |
| `evidence/` | Generated scenario results and the audit log |

## Setup (about 30 minutes)

OpenCode is free and open source; it needs no subscription. It calls Claude through this repo's gateway,
which uses your own AWS Bedrock account, so Bedrock usage is the only cost.

Prerequisites: Git, Python 3.11+, Node.js 20+ (includes npm), and the AWS CLI v2 with a profile that can use
Bedrock in us-east-1 (`aws configure --profile capstone`).

### Windows (PowerShell)

```powershell
# 1. Get the code
git clone https://github.com/dennyantony19-dev/insurance-ai-assistant.git
cd insurance-ai-assistant

# 2. Python environment
python -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements-dev.txt
# semgrep is installed separately: its pinned dependencies conflict with litellm's
pip install pipx
pipx install semgrep==1.186.0         # then open a new terminal so semgrep is on PATH

# 3. OpenCode CLI, pinned (OpenCode v2 is the @opencode/cli package; "opencode-ai" is the old v1)
npm install -g @opencode/cli@2.2.5
opencode --version                    # expect 2.2.5

# 4. Configure: copy, then edit .env in Notepad (AWS_PROFILE, BEDROCK_MODEL_ID, LITELLM_MASTER_KEY)
Copy-Item .env.example .env
notepad .env

# 5. Generate configs and create the Bedrock guardrail
python tools\gen_configs.py
$env:AWS_PROFILE = "capstone"
python tools\create_guardrail.py     # paste the printed GUARDRAIL_ID and GUARDRAIL_VERSION into .env
python tools\gen_configs.py          # re-run so the gateway config picks up BEDROCK_MODEL_ID

# 6. Terminal 1: start the gateway (leave it running)
python tools\run_gateway.py

# 7. Terminal 2: run the agent from the repo root
cd insurance-ai-assistant
.venv\Scripts\Activate.ps1
$env:LITELLM_MASTER_KEY = "<same value as in .env>"
pre-commit install
opencode
```

Windows notes: if semgrep will not install or run natively, commit with `$env:SKIP="semgrep"; git commit ...`
and rely on the CI run, which always runs semgrep. OpenCode documents npm (or the standalone binary from opencode.ai/docs) for Windows; Scoop and
Chocolatey are not supported. On first run, check that an edit to `policies\policy.yaml` is refused (S16)
to confirm the path rules match Windows paths.

### macOS / Linux

```bash
git clone https://github.com/dennyantony19-dev/insurance-ai-assistant.git && cd insurance-ai-assistant
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
pipx install semgrep==1.186.0   # separate env: its pins conflict with litellm (brew/apt install pipx if missing)
npm install -g @opencode/cli@2.2.5
cp .env.example .env            # fill AWS_PROFILE, BEDROCK_MODEL_ID, LITELLM_MASTER_KEY
python tools/gen_configs.py
AWS_PROFILE=capstone python tools/create_guardrail.py   # paste GUARDRAIL_ID / GUARDRAIL_VERSION into .env
python tools/gen_configs.py
python tools/run_gateway.py      # terminal 1
export LITELLM_MASTER_KEY=...; pre-commit install; opencode   # terminal 2
```

Where to find `BEDROCK_MODEL_ID`: Bedrock console (us-east-1) > Cross-region inference > Claude Sonnet 4.6 >
inference profile ID.

Optional sandbox: open the repo in the dev container (`.devcontainer/`, needs Docker Desktop), and set
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
