# Changes

## 0.2.0 — 2026-10-23

- Added real OpenAI Responses, Anthropic Messages, and xAI Responses REST adapters, with explicit model selection and strict local output validation.
- Added operator-side collection with per-case evidence isolation, preflight limits, explicit execution, no automatic retries, client timing, provider usage, request/response hashes, and durable partial ledgers.
- Made cost nullable: missing usage or price rates fail the cost gate; estimates are explicitly distinguished from provider bills.
- Added public-documentation source/dataset examples, an approved-policy example, and a no-key collection plan.
- Added storage readiness, private environment bootstrap, verified native SQLite backup, and a restore test.
- Prepared a Render Blueprint and GitHub CI package/container verification, with deployment and provider runbooks.
- Preserved existing immutable source/dataset/report tables and access to older reports. New observations include optional collection metadata; new live-kind observations require it.

Provider contracts are mock-tested. Live provider checks, GitHub remote CI, local Docker execution, and cloud deployment remain unverified. No provider keys are configured in this development workspace.

## 0.1.0

Initial evidence-contract reference implementation: tenant-scoped records, pinned datasets, deterministic evaluation, signed audit events, synthetic fixture, API, and CLI.
