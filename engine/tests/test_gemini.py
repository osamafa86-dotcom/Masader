"""GeminiLLM against a mocked Gemini API: request shape, model mapping, errors, retries and cost."""

import json

import httpx
import pytest

from marsad.ai.llm import GeminiLLM, LLMError, LLMRefusal, estimate_cost
from marsad.config import Settings
from marsad.worker import make_llm

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}


def ok_body(data: dict, *, prompt=1200, out=300, thoughts=50, finish="STOP", model="gemini-3.8-flash"):
    return {
        "candidates": [{"content": {"role": "model", "parts": [
            {"text": "thinking...", "thought": True},
            {"text": json.dumps(data, ensure_ascii=False)},
        ]}, "finishReason": finish}],
        "usageMetadata": {"promptTokenCount": prompt, "candidatesTokenCount": out, "thoughtsTokenCount": thoughts,
                          "totalTokenCount": prompt + out + thoughts},
        "modelVersion": model,
    }


class Recorder:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.responses.pop(0)
        return httpx.Response(status, json=body)

    def body(self, i=0) -> dict:
        return json.loads(self.requests[i].content)


def llm_with(rec: Recorder, **kw) -> GeminiLLM:
    return GeminiLLM(api_key="test-key", transport=httpx.MockTransport(rec), retry_wait_s=0, **kw)


def call(llm, model="claude-opus-5-5", effort="medium", max_tokens=8000):
    return llm.json(task="summarize", model=model, system="You summarise.", user='{"x": 1}',
                    schema=SCHEMA, max_tokens=max_tokens, effort=effort)


def test_request_shape_and_parsed_result():
    rec = Recorder((200, ok_body({"title": "الردع"})))
    res = call(llm_with(rec))
    assert res.data == {"title": "الردع"}
    req = rec.requests[0]
    # The key travels in a header, never in the URL (URLs end up in logs).
    assert req.headers["x-goog-api-key"] == "test-key"
    assert "key=" not in str(req.url)
    assert str(req.url).endswith("/v1beta/models/gemini-3.8-flash:generateContent")
    body = rec.body()
    assert body["systemInstruction"] == {"parts": [{"text": "You summarise."}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": '{"x": 1}'}]}]
    cfg = body["generationConfig"]
    assert cfg["responseMimeType"] == "application/json"
    assert cfg["responseJsonSchema"] == SCHEMA
    assert cfg["maxOutputTokens"] == 8000
    assert cfg["thinkingConfig"] == {"thinkingLevel": "MEDIUM"}


def test_claude_model_names_map_to_gemini_models():
    rec = Recorder((200, ok_body({"title": "a"})), (200, ok_body({"title": "b"})), (200, ok_body({"title": "c"})))
    llm = llm_with(rec, model="gemini-3.8-flash", model_light="gemini-3.5-flash-lite")
    call(llm, model="claude-haiku-5-5")
    call(llm, model="claude-opus-5-5")
    call(llm, model="gemini-3.1-pro-preview")  # an explicit Gemini model is used as given
    paths = [r.url.path for r in rec.requests]
    assert paths == ["/v1beta/models/gemini-3.5-flash-lite:generateContent",
                     "/v1beta/models/gemini-3.8-flash:generateContent",
                     "/v1beta/models/gemini-3.1-pro-preview:generateContent"]


def test_cost_counts_thinking_as_output_and_uses_gemini_prices():
    rec = Recorder((200, ok_body({"title": "x"}, prompt=1_000_000, out=500_000, thoughts=500_000)))
    res = call(llm_with(rec))
    assert res.model == "gemini-3.8-flash"
    assert res.input_tokens == 1_000_000 and res.output_tokens == 1_000_000
    assert res.cost_usd == pytest.approx(0.75 + 3.75)
    # An unknown Gemini model is priced as Gemini, not as the most expensive Claude model.
    assert estimate_cost("gemini-9-unknown", 1_000_000, 0) == pytest.approx(0.75)


def test_flash_price_doubles_from_2027_so_the_daily_budget_stays_honest():
    from datetime import date

    assert estimate_cost("gemini-3.8-flash", 1_000_000, 1_000_000, on=date(2026, 12, 31)) == pytest.approx(0.75 + 3.75)
    assert estimate_cost("gemini-3.8-flash", 1_000_000, 1_000_000, on=date(2027, 1, 1)) == pytest.approx(1.50 + 7.50)
    assert estimate_cost("claude-opus-5-5", 1_000_000, 0, on=date(2027, 1, 1)) == pytest.approx(4.00)


def test_truncated_output_is_an_error():
    rec = Recorder((200, ok_body({"title": "x"}, finish="MAX_TOKENS")))
    with pytest.raises(LLMError, match="truncated"):
        call(llm_with(rec))


@pytest.mark.parametrize("finish", ["SAFETY", "PROHIBITED_CONTENT", "RECITATION", "BLOCKLIST", "SPII"])
def test_blocked_output_is_a_refusal(finish):
    rec = Recorder((200, ok_body({"title": "x"}, finish=finish)))
    with pytest.raises(LLMRefusal):
        call(llm_with(rec))


def test_blocked_prompt_is_a_refusal():
    rec = Recorder((200, {"promptFeedback": {"blockReason": "SAFETY"}, "usageMetadata": {"promptTokenCount": 10}}))
    with pytest.raises(LLMRefusal, match="SAFETY"):
        call(llm_with(rec))


def test_invalid_argument_retries_once_with_a_plainer_request():
    rec = Recorder((400, {"error": {"code": 400, "message": "Unknown name \"responseJsonSchema\"", "status": "INVALID_ARGUMENT"}}),
                   (200, ok_body({"title": "ok"})))
    res = call(llm_with(rec))
    assert res.data == {"title": "ok"}
    second = rec.body(1)["generationConfig"]
    assert "responseJsonSchema" not in second and "thinkingConfig" not in second
    assert second["responseMimeType"] == "application/json"
    # Without the schema field the model is told the schema in the instruction instead.
    assert '"required": ["title"]' in rec.body(1)["systemInstruction"]["parts"][0]["text"]


def test_a_model_that_needed_the_plain_request_gets_it_directly_next_time():
    rec = Recorder((400, {"error": {"message": "bad thinking level", "status": "INVALID_ARGUMENT"}}),
                   (200, ok_body({"title": "1"})), (200, ok_body({"title": "2"})))
    llm = llm_with(rec)
    call(llm)
    assert call(llm).data == {"title": "2"}
    assert len(rec.requests) == 3 and "responseJsonSchema" not in rec.body(2)["generationConfig"]


def test_rate_limit_and_server_errors_are_retried_then_reported():
    rec = Recorder((429, {"error": {"message": "quota"}}), (503, {"error": {"message": "busy"}}),
                   (200, ok_body({"title": "ok"})))
    assert call(llm_with(rec)).data == {"title": "ok"}
    rec = Recorder(*[(503, {"error": {"message": "busy"}})] * 3)
    with pytest.raises(LLMError, match="503"):
        call(llm_with(rec))


def test_json_in_a_code_fence_is_accepted_and_garbage_is_an_error():
    fenced = ok_body({"title": "x"})
    fenced["candidates"][0]["content"]["parts"][1]["text"] = '```json\n{"title": "مسيّج"}\n```'
    assert call(llm_with(Recorder((200, fenced)))).data == {"title": "مسيّج"}
    bad = ok_body({"title": "x"})
    bad["candidates"][0]["content"]["parts"][1]["text"] = "not json"
    with pytest.raises(LLMError, match="invalid JSON"):
        call(llm_with(Recorder((200, bad))))


def test_missing_key_fails_at_call_time_with_a_clear_message():
    llm = GeminiLLM(api_key="", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(LLMError, match="MARSAD_GEMINI_API_KEY"):
        call(llm)


def test_no_batch_api_so_the_worker_translates_synchronously():
    from marsad.batches import supports_batches

    assert not supports_batches(GeminiLLM(api_key="k"))


def test_make_llm_selects_gemini_from_settings():
    llm = make_llm(Settings(llm_backend="gemini", gemini_api_key="k", gemini_model="gemini-3.6-flash"))
    assert isinstance(llm, GeminiLLM) and llm.model == "gemini-3.6-flash"
