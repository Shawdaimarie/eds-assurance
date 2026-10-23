"""Bounded operator-side collection with a durable partial-attempt ledger."""

import math
import os
import secrets
from pathlib import Path

from .evaluation import canonical
from .models import Observation, Policy, RunRequest
from .providers import build_payload, collection_metadata
from .store import utcnow


def write_private_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(canonical(value) + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def validate_limits(provider, model, dataset, sources, max_requests, max_output_tokens, max_input_chars):
    if type(max_requests) is not int or not 1 <= max_requests <= 100:
        raise ValueError("max_requests must be between 1 and 100")
    if len(dataset.cases) > max_requests:
        raise ValueError("Dataset exceeds the explicit request limit; no provider calls made")
    if not 64 <= max_output_tokens <= 8192 or not 1000 <= max_input_chars <= 200_000:
        raise ValueError("Invalid input/output limits")
    payloads = []
    for case in dataset.cases:
        evidence = [sources[source_id] for source_id in case.allowed_source_ids]
        payload = build_payload(provider, model, case.prompt, evidence, max_output_tokens)
        if len(canonical(payload)) > max_input_chars:
            raise ValueError("A request exceeds the input-character limit; no provider calls made")
        payloads.append((case, evidence))
    return payloads


def estimate_cost(provider, usage, input_rate, output_rate):
    if input_rate is None or usage is None:
        return None
    input_tokens = usage.input_tokens
    if provider == "anthropic":
        input_tokens += usage.cached_input_tokens + usage.cache_creation_input_tokens
    return round((input_tokens * input_rate + usage.output_tokens * output_rate) / 1_000_000, 8)


def collect(store, tenant, dataset_id, adapter, *, max_requests, max_input_chars=100_000,
            input_rate=None, output_rate=None, policy=None, ledger_path, label="live-evaluation"):
    if (input_rate is None) != (output_rate is None):
        raise ValueError("Supply both input and output price rates, or neither")
    for rate in (input_rate, output_rate):
        if rate is not None and (not math.isfinite(rate) or rate < 0):
            raise ValueError("Price rates must be finite and nonnegative")
    if Path(ledger_path).exists():
        raise ValueError("Choose a new ledger path; existing collection records are preserved")
    policy = policy or Policy()
    dataset, sources = store.evaluation_inputs(tenant, dataset_id)
    tasks = validate_limits(adapter.provider, adapter.model, dataset, sources, max_requests,
                            adapter.max_output_tokens, max_input_chars)
    ledger = {"schema_version": 1, "started_at": utcnow(), "completed": False,
              "provider": adapter.provider, "model": adapter.model, "dataset_id": dataset_id,
              "max_requests": max_requests, "max_output_tokens_per_request": adapter.max_output_tokens,
              "notice": "Client-collected observations. Usage is provider-reported; pricing is an optional operator estimate, not a hard spending cap.",
              "attempts": []}
    write_private_json(ledger_path, ledger)
    observations = []
    for case, evidence in tasks:
        # Persist intent before egress; a crash after this point may still incur a charge.
        attempt = {"case_id": case.case_id, "status": "in_flight", "started_at": utcnow()}
        ledger["attempts"].append(attempt)
        write_private_json(ledger_path, ledger)
        result = adapter.generate(case.prompt, evidence)
        attempt.update({"status": result.status, "latency_ms": result.latency_ms,
                        "request_sha256": result.request_sha256, "response_sha256": result.response_sha256,
                        "provider_request_id": result.request_id, "http_status": result.http_status,
                        "usage": result.usage.model_dump() if result.usage else None,
                        "finished_at": utcnow()})
        attempt["estimated_cost_usd"] = estimate_cost(adapter.provider, result.usage, input_rate, output_rate)
        write_private_json(ledger_path, ledger)
        if result.status != "ok":
            raise ValueError(f"Collection stopped at case {case.case_id}: {result.status}; partial ledger retained")
        observed = Observation(case_id=case.case_id, **result.answer.model_dump(),
                               reported_latency_ms=result.latency_ms,
                               reported_cost_usd=attempt["estimated_cost_usd"],
                               collection=collection_metadata(adapter, result, input_rate, output_rate))
        observations.append(observed)
        attempt["observation"] = observed.model_dump()
        write_private_json(ledger_path, ledger)
    request = RunRequest(dataset_id=dataset_id, label=label, model_label=f"{adapter.provider}:{adapter.model}",
                         observation_kind="live_model_output", observations=observations, policy=policy)
    report = store.run(tenant, request)
    ledger.update(completed=True, finished_at=utcnow(), run_id=report["run_id"], report_sha256=report["report_sha256"])
    write_private_json(ledger_path, ledger)
    return report
