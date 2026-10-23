import math
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from eds_assurance.models import Dataset, RunRequest, Source
from eds_assurance.store import Conflict, IntegrityError, NotFound
from conftest import fixture_json, request_for


def test_fixture_gates_distinguish_contract_failures(seeded):
    store, dataset_id = seeded
    baseline = store.run("alpha", request_for(dataset_id, "baseline.json"))
    candidate = store.run("alpha", request_for(dataset_id))
    assert not baseline["release_gate_passed"]
    assert baseline["metrics"]["disallowed_citation_count"] == 1
    assert not baseline["gates"]["reported_latency_budget"]
    assert candidate["release_gate_passed"]
    assert candidate["metrics"]["case_count"] == 6
    assert candidate["metrics"]["reported_p95_latency_ms"] == 210.0
    assert candidate["metrics"]["reported_total_cost_usd"] == 0.009
    assert store.get_run("alpha", candidate["run_id"]) == candidate


def test_source_ids_are_immutable_and_retries_idempotent(store):
    source = Source.model_validate(fixture_json("sources.json")[0])
    assert store.put_source("alpha", source) == store.put_source("alpha", source)
    assert store.verify_audit("alpha")["event_count"] == 1
    with pytest.raises(Conflict):
        store.put_source("alpha", source.model_copy(update={"content": "Changed evidence."}))


def test_dataset_hash_binds_source_content_and_tenant_visibility(store):
    source = Source.model_validate(fixture_json("sources.json")[0])
    dataset = Dataset(name="one", cases=[{"case_id": "one", "prompt": "Recovery target?",
                       "expected_behavior": "answer", "allowed_source_ids": [source.source_id]}])
    store.put_source("alpha", source)
    first = store.put_dataset("alpha", dataset)
    assert store.put_dataset("alpha", dataset)["dataset_id"] == first["dataset_id"]
    with pytest.raises(NotFound):
        store.put_dataset("beta", dataset)
    store.put_source("beta", source.model_copy(update={"content": "Different evidence."}))
    second = store.put_dataset("beta", dataset)
    assert second["dataset_id"] != first["dataset_id"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra"])
def test_partial_or_manipulated_coverage_is_rejected_atomically(seeded, mutation):
    store, dataset_id = seeded
    before = store.verify_audit("alpha")
    body = request_for(dataset_id).model_dump()
    if mutation == "missing":
        body["observations"].pop()
    elif mutation == "duplicate":
        body["observations"][-1] = body["observations"][0]
    else:
        body["observations"][-1]["case_id"] = "unknown"
    with pytest.raises(ValueError, match="exactly once"):
        store.run("alpha", RunRequest.model_validate(body))
    assert store.verify_audit("alpha") == before


@pytest.mark.parametrize("value", [math.nan, math.inf, -1.0])
def test_invalid_telemetry_is_rejected(seeded, value):
    _, dataset_id = seeded
    body = request_for(dataset_id).model_dump()
    body["observations"][0]["reported_latency_ms"] = value
    with pytest.raises(ValidationError):
        RunRequest.model_validate(body)


def test_empty_and_duplicate_datasets_rejected():
    body = fixture_json("dataset.json")
    body["cases"].append(body["cases"][0])
    with pytest.raises(ValidationError):
        Dataset.model_validate(body)
    with pytest.raises(ValidationError):
        Dataset(name="empty", cases=[])


def test_existing_quote_is_not_a_semantic_truth_check(seeded):
    store, dataset_id = seeded
    body = request_for(dataset_id).model_dump()
    body["observations"][0]["answer"] = "Workers never need to recover."
    report = store.run("alpha", RunRequest.model_validate(body))
    assert report["cases"][0]["evidence_contract_pass"]
    assert "do not prove" in report["limitations"][0]


def test_concurrent_writes_preserve_audit_order(store):
    def write(i):
        return store.put_source("alpha", Source(source_id=f"source-{i}", title="sample", content=f"Record {i}"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert len(list(pool.map(write, range(24)))) == 24
    assert store.verify_audit("alpha")["event_count"] == 24


def test_dataset_pins_metadata_and_content(seeded):
    store, dataset_id = seeded
    with store.connect() as db:
        db.execute("UPDATE sources SET body=replace(body, 'Synthetic recovery procedure', 'Changed title') WHERE tenant='alpha' AND id='recovery-v1'")
    with pytest.raises(IntegrityError):
        store.run("alpha", request_for(dataset_id))


def test_audit_detects_modified_event_and_wrong_key(seeded, settings):
    store, _ = seeded
    from eds_assurance.store import Store
    with pytest.raises(IntegrityError):
        Store(settings.db_path, b"z" * 32).verify_audit("alpha")
    with store.connect() as db:
        db.execute("UPDATE audit SET event='{}' WHERE tenant='alpha' AND seq=1")
    with pytest.raises(IntegrityError):
        store.verify_audit("alpha")


def test_truncated_tail_requires_external_checkpoint(seeded):
    store, _ = seeded
    checkpoint = store.verify_audit("alpha")
    with store.connect() as db:
        db.execute("DELETE FROM audit WHERE tenant='alpha' AND seq=?", (checkpoint["event_count"],))
    assert store.verify_audit("alpha")["event_count"] < checkpoint["event_count"]
    with pytest.raises(IntegrityError, match="external checkpoint"):
        store.verify_audit("alpha", checkpoint)


def test_old_checkpoint_remains_valid_after_new_events(seeded):
    store, dataset_id = seeded
    checkpoint = store.verify_audit("alpha")
    store.run("alpha", request_for(dataset_id))
    assert store.verify_audit("alpha", checkpoint)["event_count"] == checkpoint["event_count"] + 1


def test_audit_binds_recomputed_report_digest(seeded):
    from eds_assurance.evaluation import canonical, digest
    store, dataset_id = seeded
    report = store.run("alpha", request_for(dataset_id))
    report.pop("report_sha256")
    report["label"] = "altered"
    report["report_sha256"] = digest(report)
    with store.connect() as db:
        db.execute("UPDATE runs SET report=? WHERE tenant='alpha' AND id=?", (canonical(report), report["run_id"]))
    with pytest.raises(IntegrityError, match="audit event"):
        store.verify_audit("alpha")


@pytest.mark.parametrize("table", ["sources", "datasets", "runs"])
def test_deleted_audited_record_is_detected(seeded, table):
    store, dataset_id = seeded
    store.run("alpha", request_for(dataset_id))
    with store.connect() as db:
        # Table names are fixed test parameters, not request input.
        db.execute(f"DELETE FROM {table} WHERE tenant='alpha'")
    with pytest.raises(IntegrityError):
        store.verify_audit("alpha")
