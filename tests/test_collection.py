import json
import sys

import httpx
import pytest

from eds_assurance.cli import main
from eds_assurance.collection import collect, estimate_cost, validate_limits
from eds_assurance.models import Policy, RunRequest, TokenUsage
from eds_assurance.providers import ProviderAdapter
from conftest import request_for
from test_providers import envelope


def test_collection_uses_only_per_case_sources_and_hides_gold_labels(seeded, tmp_path, monkeypatch):
    store, dataset_id = seeded
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    candidate = request_for(dataset_id)
    seen = []
    def handler(request):
        body = json.loads(request.content)
        message = json.loads(body["input"][1]["content"])
        case = candidate.observations[len(seen)]
        seen.append(message)
        assert "expected_behavior" not in request.content.decode()
        response = {key: case.model_dump()[key] for key in ("answer", "abstained", "citations")}
        return httpx.Response(200, json=envelope("openai", response))
    adapter = ProviderAdapter("openai", "test-model", transport=httpx.MockTransport(handler))
    ledger_path = tmp_path / "collection.json"
    try:
        report = collect(store, "alpha", dataset_id, adapter, max_requests=6,
                         input_rate=2.0, output_rate=4.0, ledger_path=ledger_path,
                         policy=Policy(max_reported_p95_latency_ms=30_000.0))
    finally:
        adapter.close()
    assert report["observation_kind"] == "live_model_output"
    assert report["release_gate_passed"]
    assert [len(item["evidence_records"]) for item in seen] == [1, 1, 1, 0, 0, 0]
    assert [item["evidence_records"][0]["source_id"] for item in seen[:3]] == ["recovery-v1", "access-v1", "region-v1"]
    metadata = report["request"]["observations"][0]["collection"]
    assert metadata["usage"]["input_tokens"] == 20
    assert metadata["cost_basis"] == "operator_rate_estimate"
    ledger = json.loads(ledger_path.read_text())
    assert ledger["completed"] and len(ledger["attempts"]) == 6
    assert ledger_path.stat().st_mode & 0o777 == 0o600
    assert "test-key" not in ledger_path.read_text()
    assert store.verify_audit("alpha")["event_count"] == 5


def test_partial_failure_preserves_usage_and_creates_no_successful_run(seeded, tmp_path, monkeypatch):
    store, dataset_id = seeded
    before = store.verify_audit("alpha")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    body = envelope("anthropic")
    body["stop_reason"] = "refusal"
    adapter = ProviderAdapter("anthropic", "test-model", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    path = tmp_path / "partial.json"
    try:
        with pytest.raises(ValueError, match="refused"):
            collect(store, "alpha", dataset_id, adapter, max_requests=6, ledger_path=path)
    finally:
        adapter.close()
    assert store.verify_audit("alpha") == before
    ledger = json.loads(path.read_text())
    assert not ledger["completed"]
    assert len(ledger["attempts"]) == 1
    assert ledger["attempts"][0]["usage"]["output_tokens"] == 10
    assert ledger["attempts"][0]["estimated_cost_usd"] is None


def test_request_and_input_limits_preflight_entire_dataset(seeded):
    store, dataset_id = seeded
    dataset, sources = store.evaluation_inputs("alpha", dataset_id)
    with pytest.raises(ValueError, match="request limit"):
        validate_limits("openai", "test", dataset, sources, 5, 1024, 100_000)
    sources["region-v1"]["content"] = "x" * 200_000
    with pytest.raises(ValueError, match="input-character limit"):
        validate_limits("openai", "test", dataset, sources, 6, 1024, 100_000)


def test_unknown_cost_never_becomes_zero_or_passes_cost_gate(seeded):
    store, dataset_id = seeded
    body = request_for(dataset_id).model_dump()
    body["observations"][0]["reported_cost_usd"] = None
    report = store.run("alpha", RunRequest.model_validate(body))
    assert report["metrics"]["reported_total_cost_usd"] is None
    assert not report["gates"]["reported_cost_budget"]
    assert not report["release_gate_passed"]


def test_cost_estimates_preserve_provider_token_conventions():
    usage = TokenUsage(input_tokens=100, output_tokens=50, cached_input_tokens=20, cache_creation_input_tokens=30)
    assert estimate_cost("openai", usage, 1.0, 2.0) == 0.0002
    assert estimate_cost("anthropic", usage, 1.0, 2.0) == 0.00025
    assert estimate_cost("openai", usage, None, None) is None


def test_live_kind_requires_collection_provenance(seeded):
    _, dataset_id = seeded
    body = request_for(dataset_id).model_dump()
    body["observation_kind"] = "live_model_output"
    with pytest.raises(ValueError, match="collector metadata"):
        RunRequest.model_validate(body)


def test_cli_dry_run_needs_no_key_and_makes_no_provider_request(seeded, settings, monkeypatch, capsys):
    _, dataset_id = seeded
    monkeypatch.setenv("EDS_AUDIT_KEY_HEX", settings.audit_key.hex())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("dry run must not construct a provider adapter")
    monkeypatch.setattr("eds_assurance.providers.ProviderAdapter", forbidden)
    monkeypatch.setattr(sys, "argv", ["eds-assurance", "collect", "--state-dir", str(settings.db_path.parent),
                                     "--tenant", "alpha", "--dataset-id", dataset_id, "--provider", "openai",
                                     "--model", "operator-selected-model", "--max-requests", "6"])
    # local_store uses assurance.db; the fixture has a different filename.
    settings.db_path.rename(settings.db_path.parent / "assurance.db")
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["execute"] is False
