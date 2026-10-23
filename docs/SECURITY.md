# Security model

This is a bounded reference implementation for development and evaluation. It is not a security certification or a general-purpose agent sandbox.

## Assets and trust boundaries

Assets: tenant evidence, case prompts, submitted responses, experiment policies, reports, and the audit signing key. Raw prompts and answers are retained in reports; submit public, synthetic, or explicitly approved data during development.

The HTTP API treats callers and submitted evidence as untrusted. Credential configuration, local CLI operators, process memory, the host, and the signing key are trusted. The database is a persistence boundary, not a substitute for host security. A compromised host or signing key can forge records.

## Controls and checks

| Threat | Implemented control | Verified behavior / boundary |
|---|---|---|
| Cross-tenant reads or writes | Tenant derived from credential and included in each SQL lookup | API tests reject another tenant's datasets, runs, and source references |
| Privilege escalation | Explicit token scopes; no tenant or scope fields in public bodies | Reader cannot write; extra tenant field is rejected |
| SQL injection | Parameterized queries for request values | No client-supplied query, table name, or SQL execution endpoint |
| Changed evidence | Immutable source IDs; pinned canonical record digests | Changed metadata/content prevents evaluation against an existing manifest |
| Citation permission violation | Per-case source allowlists | A citation outside the allowlist unconditionally fails the gate |
| Misleading evaluation coverage | Complete case-ID set required | Missing, duplicate, and unexpected cases cannot create a partial successful run |
| Audit/report manipulation | HMAC-linked events and signed record digests | Event edits, wrong keys, removed records, and rehashed report edits fail verification |
| Audit suffix deletion | Previously exported checkpoint retained elsewhere | Deleting the tail is detectable when that earlier trusted checkpoint is supplied |
| Request memory exhaustion | Actual body size bounded before request parsing | Content-Length and chunked oversized bodies are rejected |
| Secrets in output | Tokens stored as digests in process; keys not returned | Example script and demo reports do not print API credentials |
| URL or tool abuse | No source URL fetcher or execution endpoint; CLI provider egress uses fixed HTTPS URLs | Documents are inert strings; redirects are rejected; no custom credential destination |

The database stores an audit-key verifier, and opening an existing store with a different key fails. This does not implement rotation, remote key custody, or a hardware security module.

## What the evaluator cannot establish

Exact citation quotes do not imply answer entailment. The test suite intentionally demonstrates that a false answer can pass the citation-format contract if it quotes valid evidence. The declared abstention flag is not verified against the answer's semantics. An attacker controlling the collector can fabricate observations or telemetry. A caller can select permissive policy thresholds; a separate release authority must approve policy and dataset hashes.

HMAC verification detects modification while the key is protected. Hash-only report retrieval detects accidental corruption; keyed audit verification is required to authenticate the report against audit events. Without an external checkpoint, a valid audit prefix is indistinguishable from a truncated audit log. Deletion of all local state cannot be detected solely from the deleted state.

Read and authentication failures are not themselves retained in the data audit chain. Structured security event logging, immutable external log delivery, and credential rotation automation are future work. Never enable request-body or Authorization-header logging at the gateway.

## Live-model collection boundary

Only the operator CLI can perform paid calls. A dry run requires no provider key. Explicit execution sends only permitted per-case evidence to the configured provider; it does not establish that the provider meets a residency or data-retention requirement. API keys are never included in generated artifacts. HTTP clients verify TLS, disable redirects, do not inherit environment proxy/netrc configuration, and do not retry automatically.

Private ledgers are atomically written with mode 0600 before/after attempts. Raw provider error bodies are not exposed. Cost is nullable and fails its gate when unknown. Pricing inputs, metadata, and provider usage are not independent billing attestations. Enforce account-side billing controls separately; output/request limits are not a hard dollar cap. Interrupted calls can still be billed. The model prompt is a policy instruction, not a proven security control against all prompt injections.

## Cloud pilot requirements

Keep a single instance and a dedicated encrypted persistent volume. Use a managed TLS gateway with authentication-aware rate limits, body and header limits, and timeouts. Inject secrets from a cloud secret manager, separate from the database's backup/write permissions. Retain signed checkpoints in a different access boundary. Establish backups and perform restore tests before relying on the service operationally.

Organization-facing deployment also needs identity federation, key lifecycle management, data retention/deletion rules, storage quotas, monitoring, vulnerability scanning, independent review, and an incident runbook. These are concrete future deployment work; the local prototype does not claim them.

## Reporting issues

For a private security discussion, use the contact route published by [Essential Digital Solution](https://essentialdigitalsolution.com/). Do not publish secrets or private evidence in a public repository issue.
