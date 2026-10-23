import json

import httpx
import pytest

from eds_assurance.providers import ENDPOINTS, ProviderAdapter, strict_json


ANSWER = {"answer": "30 seconds.", "abstained": False,
          "citations": [{"source_id": "recovery-v1", "quote": "30 seconds"}]}


def envelope(provider, answer=ANSWER):
    if provider == "anthropic":
        return {"id": "msg_test", "model": "exact-returned-model", "stop_reason": "end_turn",
                "content": [{"type": "text", "text": json.dumps(answer)}],
                "usage": {"input_tokens": 20, "output_tokens": 10, "cache_read_input_tokens": 3}}
    return {"id": "resp_test", "model": "exact-returned-model", "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer)}]}],
            "usage": {"input_tokens": 20, "output_tokens": 10, "input_tokens_details": {"cached_tokens": 3}}}


def adapter_for(monkeypatch, provider, handler):
    monkeypatch.setenv(ENDPOINTS[provider][1], "test-only-provider-key")
    ticks = iter([10.0, 10.25])
    return ProviderAdapter(provider, "requested-model", transport=httpx.MockTransport(handler), clock=lambda: next(ticks))


@pytest.mark.parametrize("provider", list(ENDPOINTS))
def test_provider_wire_contract_and_measured_metadata(monkeypatch, provider):
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url) == ENDPOINTS[provider][0]
        body = json.loads(request.content)
        assert body["model"] == "requested-model"
        assert "tools" not in body
        if provider == "anthropic":
            assert request.headers["x-api-key"] == "test-only-provider-key"
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert body["output_config"]["format"]["type"] == "json_schema"
            assert body["max_tokens"] == 1024
        else:
            assert request.headers["authorization"] == "Bearer test-only-provider-key"
            assert body["store"] is False
            assert body["text"]["format"]["strict"] is True
            assert body["max_output_tokens"] == 1024
        return httpx.Response(200, json=envelope(provider), headers={"x-request-id": "request-test"})
    adapter = adapter_for(monkeypatch, provider, handler)
    try:
        result = adapter.generate("Recovery target?", [{"source_id": "recovery-v1", "content": "30 seconds"}])
    finally:
        adapter.close()
    assert result.status == "ok"
    assert result.answer.answer == "30 seconds."
    assert result.latency_ms == 250.0
    assert result.request_id == "request-test"
    assert result.returned_model == "exact-returned-model"
    assert result.usage.input_tokens == 20
    assert len(result.request_sha256) == len(result.response_sha256) == 64
    assert len(calls) == 1


@pytest.mark.parametrize("provider", list(ENDPOINTS))
@pytest.mark.parametrize("kind", ["refused", "truncated", "invalid_output"])
def test_refusal_truncation_and_schema_failures_are_not_success(monkeypatch, provider, kind):
    body = envelope(provider, {"unexpected": "output"} if kind == "invalid_output" else ANSWER)
    if provider == "anthropic":
        if kind != "invalid_output":
            body["stop_reason"] = "refusal" if kind == "refused" else "max_tokens"
    elif kind == "refused":
        body["output"][0]["content"] = [{"type": "refusal", "refusal": "declined"}]
    elif kind == "truncated":
        body["status"] = "incomplete"
    adapter = adapter_for(monkeypatch, provider, lambda request: httpx.Response(200, json=body))
    try:
        result = adapter.generate("test", [])
    finally:
        adapter.close()
    assert result.status == kind
    assert result.answer is None
    assert result.usage is not None  # Failed generations can still be billable.


@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_http_failures_are_not_retried_or_echoed(monkeypatch, status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="sensitive-provider-body", headers={"location": "https://untrusted.example/"})
    adapter = adapter_for(monkeypatch, "openai", handler)
    try:
        result = adapter.generate("test", [])
    finally:
        adapter.close()
    assert result.status == "api_error"
    assert len(calls) == 1
    assert "sensitive-provider-body" not in str(result)


@pytest.mark.parametrize("error,status", [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "transport_error")])
def test_network_failures_are_sanitized(monkeypatch, error, status):
    def handler(request):
        raise error("sensitive transport details", request=request)
    adapter = adapter_for(monkeypatch, "openai", handler)
    try:
        result = adapter.generate("test", [])
    finally:
        adapter.close()
    assert result.status == status
    assert "sensitive" not in str(result)


@pytest.mark.parametrize("body", [[], {"status": "completed", "usage": {"input_tokens": True, "output_tokens": 2}},
                                 {"status": "completed", "output": None}])
def test_malformed_response_envelopes_fail_closed(monkeypatch, body):
    adapter = adapter_for(monkeypatch, "openai", lambda request: httpx.Response(200, json=body))
    try:
        assert adapter.generate("test", []).status == "invalid_response"
    finally:
        adapter.close()


def test_response_size_bound(monkeypatch):
    adapter = adapter_for(monkeypatch, "openai", lambda request: httpx.Response(200, content=b"x" * (2*1024*1024+1)))
    try:
        assert adapter.generate("test", []).status == "invalid_response"
    finally:
        adapter.close()


def test_missing_keys_fail_before_network(monkeypatch):
    for _, key in ENDPOINTS.values():
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="Configure OPENAI_API_KEY"):
        ProviderAdapter("openai", "explicit-model")


@pytest.mark.parametrize("text", ['{"answer":1,"answer":2}', '{"value":NaN}'])
def test_ambiguous_json_is_rejected(text):
    with pytest.raises(ValueError):
        strict_json(text)
