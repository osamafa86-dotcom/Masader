"""Model access. AnthropicLLM calls the Claude API; FakeLLM serves tests and keyless demos."""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)

# USD per million tokens: (input, output, cache_read)
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
}
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5", "claude-fable-5-2", "claude-fable-5-1"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    pass


class LLMRefusal(LLMError):
    pass


@dataclass
class LLMResult:
    data: dict
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


def estimate_cost(model: str, input_tokens: int, output_tokens: int, cache_write: int = 0, cache_read: int = 0) -> float:
    p_in, p_out, p_cache = PRICES.get(model, PRICES["claude-opus-5-5"])
    return (input_tokens * p_in + cache_write * p_in * 1.25 + cache_read * p_cache + output_tokens * p_out) / 1_000_000


class LLM(Protocol):
    def json(self, *, task: str, model: str, system: str, user: str, schema: dict,
             max_tokens: int = 16000, effort: str | None = None) -> LLMResult: ...


class AnthropicLLM:
    def __init__(self, client=None):
        import anthropic

        self._anthropic = anthropic
        self.client = client or anthropic.Anthropic()

    def json(self, *, task, model, system, user, schema, max_tokens=16000, effort=None) -> LLMResult:
        output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
        if effort:
            output_config["effort"] = effort
        kwargs: dict = dict(
            model=model,
            max_tokens=max_tokens,
            # The system prompt is identical for every document of a task, so it is cached.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config=output_config,
        )
        if model in FALLBACK_MODELS:
            kwargs.update(betas=[FALLBACK_BETA], fallbacks="default")
        try:
            with self.client.beta.messages.stream(**kwargs) as stream:
                msg = stream.get_final_message()
        except self._anthropic.APIStatusError as exc:
            raise LLMError(f"{task}: API {exc.status_code}: {exc.message}") from exc
        except self._anthropic.APIConnectionError as exc:
            raise LLMError(f"{task}: connection error: {exc}") from exc

        if msg.stop_reason == "refusal":
            category = getattr(msg.stop_details, "category", None) if msg.stop_details else None
            raise LLMRefusal(f"{task}: model declined (category={category})")
        if msg.stop_reason == "max_tokens":
            raise LLMError(f"{task}: output truncated at max_tokens={max_tokens}")
        text = next((b.text for b in msg.content if b.type == "text"), None)
        if text is None:
            raise LLMError(f"{task}: no text block in response")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"{task}: invalid JSON: {exc}") from exc

        u = msg.usage
        served = msg.model or model
        cost = estimate_cost(served, u.input_tokens, u.output_tokens,
                             getattr(u, "cache_creation_input_tokens", 0) or 0,
                             getattr(u, "cache_read_input_tokens", 0) or 0)
        log.info("%s on %s: in=%s out=%s cost=$%.4f", task, served, u.input_tokens, u.output_tokens, cost)
        return LLMResult(data=data, model=served, input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                         cost_usd=cost)


class FakeLLM:
    """Deterministic stand-in. handler(task, payload) returns the response dict."""

    def __init__(self, handler: Callable[[str, dict], dict]):
        self.handler = handler
        self.calls: list[tuple[str, dict]] = []

    def json(self, *, task, model, system, user, schema, max_tokens=16000, effort=None) -> LLMResult:
        payload = json.loads(user)
        self.calls.append((task, payload))
        data = self.handler(task, payload)
        tokens_in, tokens_out = len(user) // 4, len(json.dumps(data, ensure_ascii=False)) // 4
        return LLMResult(data=data, model=f"fake:{model}", input_tokens=tokens_in, output_tokens=tokens_out,
                         cost_usd=estimate_cost(model, tokens_in, tokens_out))
