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


@dataclass
class BatchItem:
    custom_id: str
    model: str
    system: str
    user: str
    schema: dict
    max_tokens: int = 16000
    effort: str | None = None


BATCH_DISCOUNT = 0.5


class LLM(Protocol):
    def json(self, *, task: str, model: str, system: str, user: str, schema: dict,
             max_tokens: int = 16000, effort: str | None = None) -> LLMResult: ...

    # Message Batches (optional): submit -> poll until "ended" -> results by custom_id.
    def batch_submit(self, items: list[BatchItem]) -> str: ...

    def batch_status(self, batch_id: str) -> str: ...

    def batch_results(self, batch_id: str) -> dict[str, LLMResult | str]: ...


def _params(item: BatchItem) -> dict:
    output_config: dict = {"format": {"type": "json_schema", "schema": item.schema}}
    if item.effort:
        output_config["effort"] = item.effort
    return {"model": item.model, "max_tokens": item.max_tokens,
            "system": [{"type": "text", "text": item.system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": item.user}], "output_config": output_config}


class _AnthropicBatches:
    """Mixed into AnthropicLLM. Batches cannot use server-side fallbacks; a declined request comes back as an
    error string and the caller retries it synchronously (where fallbacks apply)."""

    def batch_submit(self, items: list[BatchItem]) -> str:
        try:
            batch = self.client.messages.batches.create(
                requests=[{"custom_id": it.custom_id, "params": _params(it)} for it in items])
        except self._anthropic.APIError as exc:
            raise LLMError(f"batch submit: {exc}") from exc
        return batch.id

    def batch_status(self, batch_id: str) -> str:
        return self.client.messages.batches.retrieve(batch_id).processing_status

    def batch_results(self, batch_id: str) -> dict[str, LLMResult | str]:
        out: dict[str, LLMResult | str] = {}
        for entry in self.client.messages.batches.results(batch_id):
            r = entry.result
            if r.type != "succeeded":
                out[entry.custom_id] = r.type
                continue
            msg = r.message
            if msg.stop_reason != "end_turn":
                out[entry.custom_id] = f"stop_reason={msg.stop_reason}"
                continue
            text = next((b.text for b in msg.content if b.type == "text"), None)
            try:
                data = json.loads(text or "")
            except json.JSONDecodeError:
                out[entry.custom_id] = "invalid_json"
                continue
            u = msg.usage
            cost = BATCH_DISCOUNT * estimate_cost(msg.model, u.input_tokens, u.output_tokens,
                                                  getattr(u, "cache_creation_input_tokens", 0) or 0,
                                                  getattr(u, "cache_read_input_tokens", 0) or 0)
            out[entry.custom_id] = LLMResult(data=data, model=msg.model, input_tokens=u.input_tokens,
                                             output_tokens=u.output_tokens, cost_usd=cost)
        return out


class AnthropicLLM(_AnthropicBatches):
    def __init__(self, client=None):
        import anthropic

        self._anthropic = anthropic
        self._client = client

    @property
    def client(self):
        if self._client is None:  # created on first use, so the API can start without a key
            self._client = self._anthropic.Anthropic()
        return self._client

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

    def __init__(self, handler: Callable[[str, dict], dict], batch_rounds: int = 0):
        self.handler = handler
        self.calls: list[tuple[str, dict]] = []
        self.batches: dict[str, dict] = {}
        self.batch_rounds = batch_rounds  # how many status polls report "in_progress" before "ended"

    def batch_submit(self, items: list[BatchItem]) -> str:
        bid = f"fakebatch_{len(self.batches) + 1}"
        self.batches[bid] = {"items": items, "polls": 0}
        return bid

    def batch_status(self, batch_id: str) -> str:
        b = self.batches[batch_id]
        b["polls"] += 1
        return "ended" if b["polls"] > self.batch_rounds else "in_progress"

    def batch_results(self, batch_id: str) -> dict:
        out = {}
        for it in self.batches[batch_id]["items"]:
            try:
                res = self.json(task="translate_batch", model=it.model, system=it.system, user=it.user, schema=it.schema)
            except Exception as exc:  # noqa: BLE001 - a handler error becomes an errored request
                out[it.custom_id] = f"errored: {exc}"
                continue
            res.cost_usd *= BATCH_DISCOUNT
            out[it.custom_id] = res
        return out

    def json(self, *, task, model, system, user, schema, max_tokens=16000, effort=None) -> LLMResult:
        payload = json.loads(user)
        self.calls.append((task, payload))
        data = self.handler(task, payload)
        tokens_in, tokens_out = len(user) // 4, len(json.dumps(data, ensure_ascii=False)) // 4
        return LLMResult(data=data, model=f"fake:{model}", input_tokens=tokens_in, output_tokens=tokens_out,
                         cost_usd=estimate_cost(model, tokens_in, tokens_out))
