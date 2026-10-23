"""Deterministic contract checks; these do not establish semantic truth or safety."""

import hashlib
import json
import math

from .models import Dataset, RunRequest


ENGINE_VERSION = "evidence-contract-v2"


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def content_digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def evaluate(dataset: Dataset, sources: dict, request: RunRequest) -> dict:
    expected = {case.case_id for case in dataset.cases}
    actual = [item.case_id for item in request.observations]
    if len(set(actual)) != len(actual) or set(actual) != expected:
        raise ValueError("observations must cover every dataset case exactly once")

    by_id = {item.case_id: item for item in request.observations}
    results = []
    disallowed = 0
    citation_count = 0
    valid_citation_count = 0
    for case in dataset.cases:
        observed = by_id[case.case_id]
        behavior_pass = observed.abstained == (case.expected_behavior == "abstain")
        citation_results = []
        for citation in observed.citations:
            citation_count += 1
            allowed = citation.source_id in case.allowed_source_ids
            source = sources.get(citation.source_id) if allowed else None
            quote_matches = source is not None and citation.quote in source["content"]
            valid = bool(allowed and quote_matches)
            valid_citation_count += int(valid)
            disallowed += int(not allowed)
            citation_results.append({"source_id": citation.source_id, "allowed": allowed,
                                     "exact_quote_found": bool(quote_matches), "valid": valid})
        if observed.abstained:
            evidence_pass = not observed.citations
        else:
            evidence_pass = bool(citation_results) and all(item["valid"] for item in citation_results)
        results.append({"case_id": case.case_id, "behavior_pass": behavior_pass,
                        "evidence_contract_pass": evidence_pass, "citations": citation_results})

    latencies = sorted(item.reported_latency_ms for item in request.observations)
    count = len(results)
    metrics = {
        "case_count": count,
        "behavior_pass_rate": sum(item["behavior_pass"] for item in results) / count,
        "evidence_contract_pass_rate": sum(item["evidence_contract_pass"] for item in results) / count,
        "citation_count": citation_count,
        "valid_citation_count": valid_citation_count,
        "disallowed_citation_count": disallowed,
        "reported_p95_latency_ms": latencies[math.ceil(count * 0.95) - 1],
        "reported_total_cost_usd": (
            round(sum(item.reported_cost_usd for item in request.observations), 8)
            if all(item.reported_cost_usd is not None for item in request.observations) else None
        ),
        "cost_observation_coverage": sum(item.reported_cost_usd is not None for item in request.observations) / count,
    }
    policy = request.policy
    gates = {
        "expected_behavior": metrics["behavior_pass_rate"] >= policy.min_behavior_pass_rate,
        "evidence_contract": metrics["evidence_contract_pass_rate"] >= policy.min_evidence_contract_pass_rate,
        "no_disallowed_citations": disallowed == 0,
        "reported_latency_budget": metrics["reported_p95_latency_ms"] <= policy.max_reported_p95_latency_ms,
        "reported_cost_budget": (metrics["reported_total_cost_usd"] is not None
                                 and metrics["reported_total_cost_usd"] <= policy.max_reported_total_cost_usd),
    }
    return {"engine_version": ENGINE_VERSION, "metrics": metrics, "gates": gates,
            "release_gate_passed": all(gates.values()), "cases": results,
            "limitations": [
                "Exact source quotes do not prove that an answer is true or entailed by its citations.",
                "Abstention is a declared field; the answer text is not semantically classified.",
                "Latency and cost are supplied observations, not independently measured by this evaluator.",
                "Live collector latency is client-observed wall time; supplied pricing produces an estimate, not a provider bill.",
                "Unknown costs fail the cost gate; cached-token pricing, tiers, taxes, and provider charges may differ.",
                "A passing gate covers this dataset and policy only; it is not a safety or compliance certification.",
            ]}
