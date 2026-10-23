# HTTP API contract

All `/v1/` routes require `Authorization: Bearer <token>`. The configured credential determines tenant and scopes. No body accepts a `tenant` field. There is no CORS policy permitting cross-origin browser access.

| Method | Route | Scope | Result |
|---|---|---|---|
| GET | `/healthz` | Public | Process liveness and version only |
| GET | `/readyz` | Public | Storage readiness without project information |
| POST | `/v1/sources` | `write` | Immutable evidence record, SHA-256 hashes |
| POST | `/v1/datasets` | `write` | Dataset ID and complete pinned manifest |
| GET | `/v1/datasets/{dataset_id}` | `read` | Own tenant's manifest |
| POST | `/v1/runs` | `evaluate` | Saved report, per-case results, gate decision |
| GET | `/v1/runs/{run_id}` | `read` | Own tenant's report, verified against stored digest |
| GET | `/v1/audit/checkpoint` | `read` | Verify signed audit chain and bound records; return current checkpoint |

## Source

```json
{
  "source_id": "policy-v1",
  "title": "Example retention policy",
  "content": "Example records are retained for 30 days.",
  "source_url": "https://example.com/policy"
}
```

The optional URL is attribution only and is never fetched. Source text/title are stripped of leading/trailing whitespace before hashing. Content hashes represent stored normalized text, not the bytes of an original file. Record hashes bind metadata and text together. Reusing an ID for changed content or metadata returns 409; supply a new versioned ID.

## Dataset

```json
{
  "name": "Retention checks v1",
  "cases": [{
    "case_id": "retention",
    "prompt": "How long are example records retained?",
    "expected_behavior": "answer",
    "allowed_source_ids": ["policy-v1"]
  }]
}
```

Allowed evidence must already exist in the caller's tenant. `expected_behavior` is `answer` or `abstain`. Answer cases require at least one permitted source. The service returns a 64-character hexadecimal `dataset_id` that binds the full manifest and evidence digests.

## Run

```json
{
  "dataset_id": "REPLACE_WITH_RETURNED_DATASET_ID",
  "label": "experiment-001",
  "model_label": "provider-and-exact-model-id",
  "observation_kind": "recorded_model_output",
  "observations": [{
    "case_id": "retention",
    "answer": "30 days.",
    "abstained": false,
    "citations": [{
      "source_id": "policy-v1",
      "quote": "Example records are retained for 30 days."
    }],
    "reported_latency_ms": 240.0,
    "reported_cost_usd": 0.002
  }],
  "policy": {
    "min_behavior_pass_rate": 1.0,
    "min_evidence_contract_pass_rate": 1.0,
    "max_reported_p95_latency_ms": 500.0,
    "max_reported_total_cost_usd": 1.0
  }
}
```

No provider is called by this endpoint. The caller must collect and retain the actual observations. The service rejects missing, repeated, or unexpected cases. A non-abstaining response needs nonempty answer text and passes the evidence contract only with at least one citation and all quotes matching authorized evidence. An abstention passes the evidence contract only if it has no citations. Declared behavior is compared to expected behavior separately.

The p95 uses nearest rank: sorted value at index `ceil(0.95 × N) - 1`. Known cost is summed and rounded to eight decimal places. If any observation has missing/null cost, total cost is null and its gate fails. Neither measurement is independently attested. A source allowlist violation always fails the release gate even if other supplied thresholds are permissive.

Version 0.2 accepts `observation_kind: live_model_output` only when every observation includes strict `collection` metadata: provider, requested/returned model, request/response hashes, timing source, usage, and optional price rates. The CLI collector creates this metadata. API callers remain responsible for truthful submissions; metadata is not a provider signature. See [the provider contract](PROVIDERS.md).

## Errors and operational behavior

- 401: missing or invalid credential. 403: insufficient scope.
- 404: record absent from the caller's tenant; cross-tenant records are indistinguishable from missing records.
- 409: immutable ID conflict or failed evidence-integrity check.
- 413: body exceeds 512 KiB. Chunked requests are bounded as well.
- 422: malformed schema, non-finite telemetry, unknown fields, or incomplete case coverage.
- 503: temporary SQLite operational failure.

Responses use `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`. Interactive documentation and unauthenticated OpenAPI schema routes are disabled. No HTTPS endpoint, edge rate limiter, distributed queue, or model execution sandbox is provided by this process.
