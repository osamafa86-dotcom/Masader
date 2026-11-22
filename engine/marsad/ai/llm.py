"""Model access. AnthropicLLM calls the Claude API, GeminiLLM the Gemini API; FakeLLM serves tests and keyless demos."""

import json
import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol

import httpx

log = logging.getLogger(__name__)

# USD per million tokens: (input, output, cache_read)
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
    # Gemini, paid tier, prompts up to 200k tokens; thinking tokens are billed as output.
    "gemini-3.8-flash": (0.75, 3.75, 0.075),
    "gemini-3.6-flash": (0.75, 3.75, 0.075),
    "gemini-3.5-flash-lite": (0.30, 2.50, 0.03),
    "gemini-3.1-flash-lite": (0.25, 1.50, 0.025),
    "gemini-3.1-pro-preview": (2.00, 12.00, 0.20),
    "gemini-4-hydrogen": (1.50, 7.50, 0.15),
    "gemini-4-carbon": (4.00, 20.00, 0.40),
    "gemini-4-argon": (4.00, 20.00, 0.40),
}
# Announced price changes: (first day, new prices). Without this the daily budget would undercount real spend.
PRICE_CHANGES = {
    "gemini-3.8-flash": (date(2027, 1, 1), (1.50, 7.50, 0.15)),
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


def estimate_cost(model: str, input_tokens: int, output_tokens: int, cache_write: int = 0, cache_read: int = 0,
                  on: date | None = None) -> float:
    if not model.startswith("gemini"):
        prices = PRICES.get(model, PRICES["claude-opus-5-5"])
    else:
        name = model if model in PRICES else "gemini-3.8-flash"
        prices = PRICES[name]
        change = PRICE_CHANGES.get(name)
        if change and (on or datetime.now(timezone.utc).date()) >= change[0]:
            prices = change[1]
    p_in, p_out, p_cache = prices
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


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "RECITATION", "BLOCKLIST", "SPII", "LANGUAGE"}
GEMINI_RETRY = {429, 500, 502, 503, 504}
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


class GeminiLLM:
    """The Gemini API through REST generateContent, with JSON output bound to the task's schema.

    The pipeline names Claude models in its settings; those names map to `model` (translation, summaries,
    judging) or `model_light` (classification, the Haiku slot). A setting that already names a Gemini model is
    used as given. There is no Batch API here, so the worker translates synchronously."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-3.8-flash",
                 model_light: str = "gemini-3.5-flash-lite", transport: httpx.BaseTransport | None = None,
                 timeout_s: float = 600.0, retries: int = 3, retry_wait_s: float = 2.0):
        self.api_key = api_key if api_key is not None else (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "")
        self.model, self.model_light = model, model_light
        self.retries, self.retry_wait_s = retries, retry_wait_s
        self._http = httpx.Client(transport=transport, timeout=timeout_s)
        self._plain_models: set[str] = set()  # models that rejected the schema field or thinking level once

    def resolve(self, model: str) -> str:
        if model.startswith("gemini"):
            return model
        return self.model_light if "haiku" in model else self.model

    def _body(self, system: str, user: str, schema: dict, max_tokens: int, effort: str | None, plain: bool) -> dict:
        config: dict = {"responseMimeType": "application/json", "maxOutputTokens": max_tokens}
        if plain:
            # Fallback when the API rejects the schema field or thinking level: state the schema in the instruction.
            system = f"{system}\n\nReply with JSON only, valid against this JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}"
        else:
            config["responseJsonSchema"] = schema
            if effort:
                config["thinkingConfig"] = {"thinkingLevel": effort.upper()}
        return {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": config}

    def _post(self, task: str, model: str, body: dict) -> httpx.Response:
        last = ""
        for attempt in range(self.retries):
            try:
                res = self._http.post(GEMINI_URL.format(model=model), json=body,
                                      headers={"x-goog-api-key": self.api_key, "content-type": "application/json"})
            except httpx.HTTPError as exc:
                last = f"connection error: {exc}"
            else:
                if res.status_code not in GEMINI_RETRY:
                    return res
                last = f"API {res.status_code}: {_gemini_message(res)}"
            if attempt + 1 < self.retries:
                time.sleep(self.retry_wait_s * (2 ** attempt))
        raise LLMError(f"{task}: {last}")

    def json(self, *, task, model, system, user, schema, max_tokens=16000, effort=None) -> LLMResult:
        if not self.api_key:
            raise LLMError(f"{task}: no Gemini API key (set MARSAD_GEMINI_API_KEY)")
        model = self.resolve(model)
        plain = model in self._plain_models
        res = self._post(task, model, self._body(system, user, schema, max_tokens, effort, plain=plain))
        if res.status_code == 400 and not plain:
            log.warning("%s on %s: 400 %s; retrying without schema field and thinking level", task, model, _gemini_message(res))
            res = self._post(task, model, self._body(system, user, schema, max_tokens, effort, plain=True))
            if res.status_code == 200:
                self._plain_models.add(model)
        if res.status_code != 200:
            raise LLMError(f"{task}: API {res.status_code}: {_gemini_message(res)}")
        out = res.json()

        block = (out.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise LLMRefusal(f"{task}: prompt blocked ({block})")
        candidates = out.get("candidates") or []
        if not candidates:
            raise LLMError(f"{task}: no candidates in response")
        cand = candidates[0]
        finish = cand.get("finishReason", "")
        if finish in GEMINI_BLOCKED:
            raise LLMRefusal(f"{task}: model declined (finishReason={finish})")
        if finish == "MAX_TOKENS":
            raise LLMError(f"{task}: output truncated at max_tokens={max_tokens}")
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
        fenced = _FENCE.match(text)
        try:
            data = json.loads(fenced.group(1) if fenced else text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"{task}: invalid JSON: {exc}") from exc

        u = out.get("usageMetadata") or {}
        served = out.get("modelVersion") or model
        tokens_in = u.get("promptTokenCount", 0)
        tokens_out = u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
        cached = u.get("cachedContentTokenCount", 0)
        cost = estimate_cost(served, tokens_in - cached, tokens_out, cache_read=cached)
        log.info("%s on %s: in=%s out=%s cost=$%.4f", task, served, tokens_in, tokens_out, cost)
        return LLMResult(data=data, model=served, input_tokens=tokens_in, output_tokens=tokens_out, cost_usd=cost)


def _gemini_message(res: httpx.Response) -> str:
    try:
        return str(res.json().get("error", {}).get("message", ""))[:300]
    except ValueError:
        return res.text[:300]


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
