# Verification record — v0.2.0

Local date: **2026-10-23**. Runtime: Python **3.12.14**, macOS arm64. Dependencies are pinned in the included lock files.

| Check | Result |
|---|---|
| Automated tests | 65 passed on Python 3.12 |
| Static checks | Ruff F-series checks pass for source, tests, scripts, and examples |
| Existing API/data controls | Complete workflow, tenant isolation, access scopes, immutable evidence, exact coverage, bounded bodies, and audit tampering tests pass |
| Actual local HTTP process | Uvicorn plus authenticated example workflow succeeds; cross-tenant reads fail; saved runs survive a process restart |
| Provider wire contracts | OpenAI, Anthropic, and xAI REST payloads, authentication headers, schema configuration, usage, model/request IDs, and timing tested through HTTPX mock transport |
| Provider failure handling | Refusals, truncation, invalid output, malformed envelopes, response-size limits, 302/401/429/500 responses, timeouts, and connection failures tested |
| Collection boundaries | Per-case evidence isolation, excluded gold labels, request/input limits, no-key/no-call dry runs, nullable cost, and partial ledger retention tested |
| Secret generation | Private file mode and refusal to overwrite existing credentials tested |
| Backup and restore | Native SQLite snapshot verifies and restores prior records after subsequent source-store writes |
| Readiness | Storage failure returns 503 without exposing project data |
| Synthetic demonstration | Baseline fails; candidate passes; audit checkpoint verifies |
| CLI/public data workflow | Doctor, public-source ingestion, and credential-free dry run succeed with no model calls |
| Distribution build | v0.2.0 source archive and wheel build successfully; installed wheel imports and completes doctor/demo workflows |
| Dependencies and Compose | `pip check` succeeds; Docker Compose configuration validates |
| Render configuration | Passes Render's current public JSON schema; single instance and external secret fields also covered by offline tests |
| Live provider calls | Not performed: no provider API keys configured; no paid model requests made |
| Docker runtime | Not executed locally: Docker daemon unavailable |
| Remote GitHub CI | [Run 40041827502](https://github.com/Shawdaimarie/eds-assurance/actions/runs/40041827502): all four jobs passed, including Python 3.11–3.13 and container/API workflow |
| Cloud deployment | Dashboard Blueprint review reached; Render requires payment information. Workspace confirmation pending. No EDS Assurance service or paid resources created |
| Other Python versions | Python 3.11 and 3.13 verified in GitHub CI |

The upstream Starlette test client emits one HTTPX deprecation warning. All tests pass with pinned dependencies. Runtime provider adapters use HTTPX directly; this warning concerns the test transport.

Mocked HTTP contract checks do not establish that a provider account/model currently accepts the request. Before relying on the integration, use a configured key and exact model to perform a bounded public-data smoke run and inspect its retained ledger and response metadata.

The checked-in `reports/demo.json` remains a synthetic demonstration. It does not contain measured live model or service performance. Test-generated live-kind observations use mock transports and are not published as real model results.

Exact quotation is a structural evidence check. One intentional test demonstrates that a false answer with an existing source quote can satisfy that contract. Semantic validation, calibrated graders, and representative held-out benchmarks remain separate work.

No uptime, distributed scale, regulatory compliance, or aerospace qualification is asserted. Public source links and references do not imply institutional affiliation or employer endorsement.
