# Provider integration contract

Version 0.2 implements real REST request/response adapters. They are exercised offline through HTTPX's mock transport. No provider API key is available in the development workspace, so credentialed live verification remains outstanding.

## Supported paths

| Provider | Fixed destination | Secret | Structured-output field |
|---|---|---|---|
| OpenAI | `https://api.openai.com/v1/responses` | `OPENAI_API_KEY` | `text.format` with JSON schema and `strict: true` |
| Anthropic | `https://api.anthropic.com/v1/messages` | `ANTHROPIC_API_KEY` | `output_config.format` with JSON schema |
| xAI / Grok | `https://api.x.ai/v1/responses` | `XAI_API_KEY` | `text.format` with JSON schema and `strict: true` |

An exact model identifier is required. The operator is responsible for checking current model availability and schema support. There is no silent model substitution, fallback provider, arbitrary base URL, browser tool, or code execution. OpenAI and xAI requests set `store: false`; this setting is not a promise of zero retention, regional processing, or a particular contractual data policy.

Official contracts reviewed on 2026-10-23: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [OpenAI Responses migration and storage](https://developers.openai.com/api/docs/guides/migrate-to-responses), [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), and [xAI structured outputs](https://docs.x.ai/developers/model-capabilities/text/structured-outputs).

## Data sent to the provider

The collector verifies the local audit trail, dataset manifest, and pinned source digests before collection. Each request contains one question and only that case's permitted evidence records. Expected behaviors and evaluation labels are excluded. Input-character limits are checked for every request before the first call. Source documents are explicitly described as untrusted data; this prompt is not a proven injection defense.

Running `collect` alone prints a plan without loading a provider key or constructing an HTTP client. `--execute` authorizes transmission of the permitted evidence and paid requests. Operators must select approved/public data and an appropriate provider account. Credentials remain in environment variables and HTTP headers and are excluded from reports and ledgers.

## Request boundaries

- One request per case, at most the explicit `--max-requests` limit, with no automatic retries.
- Generation limit: 64–8192 output tokens per request. Default: 1024.
- Timeout: 1–120 seconds per HTTP phase, default 30 seconds. HTTPX's timeout is not a total wall-clock deadline.
- Input payload: default 100,000 characters; configurable from 1,000 to 200,000.
- Response: decoded body bounded to 2 MiB before JSON parsing. Redirects are not followed.
- TLS verification is enabled. Environment proxy/netrc configuration is not inherited (`trust_env=False`).

Request limits are not a guaranteed dollar spending limit. Set provider-side controls for billing exposure. A timed-out or interrupted request can incur charges even if the collector cannot retrieve usage. Before a call, the private ledger records `in_flight`; a crash can leave that status and should not trigger blind retries.

## Output and telemetry

Model-generated fields are restricted to `answer`, `abstained`, and `citations`. Local Pydantic validation enforces the original constraints even if a provider's schema subset differs. Duplicate JSON keys and non-finite numbers are rejected. Refusals, token truncation, malformed envelopes, invalid output, HTTP errors, and network errors are failure categories rather than successful abstentions.

Client `perf_counter` measures request/response processing wall time. Each observation retains provider/model identifiers, request and response SHA-256 digests, timing source, usage, and optional pricing inputs. Provider headers and returned model identifiers are untrusted metadata. These values are not provider-signed attestations; an operator able to submit observations can forge them.

Usage preserves cache fields separately. Responses API input counts already include cached input; Anthropic's cached-read and cache-creation counts are separate from `input_tokens`. The simple estimate uses uncached input/output rates and includes separate Anthropic cache counts in its input quantity. It does not model cache-specific prices, premium tiers, credits, or tax. Rates must be supplied as a pair of finite nonnegative numbers. Missing rates or usage yield `null` cost and a failed cost gate.

## Failure and persistence

The collector writes a private, atomic ledger before and after each attempt. Successful observations remain there if a later case fails. Raw provider error bodies and secret headers are not retained. The full raw response is hashed but not stored. A final evaluation run is saved only when every case produces a valid complete response.

Source/dataset/run writes retain their existing transactional and tenant boundaries. Provider collection is an operator-side CLI capability; it is not exposed through the public API, preventing ordinary tenant credentials from triggering model spend. The deployed API does not require model-provider keys.

## Validation still required before relying on a provider

Configure the selected provider key in a local terminal or secret manager, choose the exact account-accessible model, review a dry run, and execute a small public-data collection. Inspect provider response identifiers, token usage, exact citations, unsupported answers, and failure behavior. Retain results privately until reviewed. A four-case documentation exercise is a smoke test, not a statistical comparison or security benchmark.
