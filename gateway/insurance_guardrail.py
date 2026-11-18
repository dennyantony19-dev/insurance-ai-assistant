"""LiteLLM custom guardrail: local insurance PII masking, topic checks and audit log.

Loaded by gateway/litellm_config.yaml as `insurance_guardrail.InsuranceGuardrail`.
It runs BEFORE the Bedrock guardrail on input and AFTER it on output, so masking
does not depend on a single vendor control.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails_core.audit import log_event  # noqa: E402
from guardrails_core.pii import build_detectors, scan  # noqa: E402
from guardrails_core.policy import load_policy  # noqa: E402
from guardrails_core.topics import check_text  # noqa: E402

try:  # LiteLLM is only needed at runtime; tests import this module without it.
    from litellm.integrations.custom_guardrail import CustomGuardrail
    from litellm.types.guardrails import GuardrailEventHooks
except ImportError:  # pragma: no cover - exercised only without litellm installed
    CustomGuardrail = object  # type: ignore[assignment,misc]
    GuardrailEventHooks = None  # type: ignore[assignment]

try:
    from fastapi import HTTPException
except ImportError:  # pragma: no cover
    HTTPException = None  # type: ignore[assignment,misc]


class GuardrailBlocked(ValueError):
    """Raised to refuse a request; LiteLLM turns it into an HTTP 400 for the client."""


def _iter_text_slots(messages: list[dict[str, Any]]):
    """Yield (container, key) pairs for every text field the model will see."""
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            yield msg, "content"
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    yield part, "text"
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") or {}
            if isinstance(fn.get("arguments"), str):
                yield fn, "arguments"


def sanitize_messages(messages: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mask PII in place and check topics. Returns a summary; raises GuardrailBlocked."""
    policy = policy or load_policy()
    detectors = build_detectors(policy)
    entity_types: set[str] = set()
    for holder, key in _iter_text_slots(messages):
        result = scan(holder[key], detectors)
        if result.blocked:
            raise GuardrailBlocked(
                policy["blocked_message"].format(reason="credential or secret detected: " + ", ".join(result.types()))
            )
        holder[key] = result.text
        entity_types.update(result.types())
    # Topic and prompt-attack checks apply to what the human typed (latest user turn).
    user_turns = [m for m in messages if m.get("role") == "user"]
    if user_turns:
        latest = user_turns[-1]
        texts = [latest["content"]] if isinstance(latest.get("content"), str) else [
            p.get("text", "") for p in latest.get("content") or [] if isinstance(p, dict)
        ]
        for text in texts:
            reason = check_text(text, policy)
            if reason:
                raise GuardrailBlocked(policy["blocked_message"].format(reason=reason))
    return {"masked_types": sorted(entity_types)}


class InsuranceGuardrail(CustomGuardrail):  # type: ignore[misc,valid-type]
    def __init__(self, **kwargs: Any) -> None:
        self.policy = load_policy()
        if CustomGuardrail is not object:
            super().__init__(**kwargs)

    def _should_run(self, data: dict[str, Any], hook: str) -> bool:
        if GuardrailEventHooks is None or not hasattr(self, "should_run_guardrail"):
            return True
        return self.should_run_guardrail(data=data, event_type=GuardrailEventHooks(hook))

    async def async_pre_call_hook(self, user_api_key_dict: Any, cache: Any, data: dict, call_type: Any) -> dict:
        if not self._should_run(data, "pre_call"):
            return data
        messages = data.get("messages") or []
        try:
            summary = sanitize_messages(messages, self.policy)
        except GuardrailBlocked as exc:
            log_event({"stage": "input", "decision": "blocked", "reason": str(exc), "model": data.get("model")})
            if HTTPException is not None and CustomGuardrail is not object:
                # 400 tells the client this is a policy refusal, not a server fault.
                raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
            raise
        decision = "masked" if summary["masked_types"] else "allowed"
        log_event({"stage": "input", "decision": decision, "entity_types": summary["masked_types"],
                   "model": data.get("model"), "messages": len(messages)})
        return data

    async def async_post_call_success_hook(self, data: dict, user_api_key_dict: Any, response: Any) -> Any:
        if not self._should_run(data, "post_call"):
            return response
        found: set[str] = set()
        for choice in getattr(response, "choices", []) or []:
            message = getattr(choice, "message", None)
            if message is None:
                continue
            if isinstance(getattr(message, "content", None), str):
                result = scan(message.content)
                message.content = result.text
                found.update(result.types())
            for call in getattr(message, "tool_calls", None) or []:
                fn = getattr(call, "function", None)
                if fn is not None and isinstance(getattr(fn, "arguments", None), str):
                    result = scan(fn.arguments)
                    fn.arguments = result.text
                    found.update(result.types())
        log_event({"stage": "output", "decision": "masked" if found else "allowed",
                   "entity_types": sorted(found), "model": data.get("model")})
        return response

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict: Any, response: Any, request_data: dict):
        """Streamed output: pass chunks through and DETECT (not mask) PII in the assembled text.

        Masking a stream chunk by chunk misses values split across chunks, so streamed
        output relies on the Bedrock output guardrail for masking; this hook records
        any local detection in the audit log so it shows up in evidence.
        """
        buffer: list[str] = []
        async for chunk in response:
            for choice in getattr(chunk, "choices", []) or []:
                delta = getattr(choice, "delta", None)
                text = getattr(delta, "content", None) if delta is not None else None
                if isinstance(text, str):
                    buffer.append(text)
            yield chunk
        result = scan("".join(buffer))
        log_event({"stage": "output_stream", "decision": "detected" if result.findings else "allowed",
                   "entity_types": result.types(), "model": request_data.get("model")})
