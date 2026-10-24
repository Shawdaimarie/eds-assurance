# EDS Assurance

**Secure evidence contracts and reproducible evaluation for AI applications.** An independent engineering project supporting [Essential Digital Solution](https://essentialdigitalsolution.com/).

Version **0.2.0** adds real REST adapters for **OpenAI, Anthropic, and xAI/Grok**, client-measured latency, provider-reported token usage, partial-attempt ledgers, verified SQLite backups, and a Render deployment configuration.

The adapters are implemented and tested with mocked HTTP responses. **Live model calls have not been verified in this workspace because provider keys are not configured.** The included demonstration remains a labeled synthetic fixture. The standalone [GitHub repository](https://github.com/Shawdaimarie/eds-assurance) has been created; deployment status is documented separately.

## What works

| Component | Behavior |
|---|---|
| Evidence and data | Immutable versioned source IDs; datasets pin canonical source record digests |
| Evaluation | Complete case coverage, declared answer/abstain behavior, citation permissions, and exact quotes |
| Provider collection | Fixed HTTPS destinations, strict output contracts, one request per case, no automatic retries or tools |
| Observability | Client wall time, provider request/model identifiers, token usage, request and response hashes |
| Cost handling | Optional estimates from explicit operator rates; unknown cost fails its release gate |
| Security | Credential-derived tenant, scoped access, bounded request bodies, inert source documents |
| Integrity | Transactional reports and HMAC audit chain; external checkpoints detect audit-tail deletion |
| Operations | Liveness/readiness endpoints, verified native SQLite backups, non-root container configuration |
| GitHub and hosting | CI tests, static checks, package/container build checks, Render Blueprint and deployment runbook |

The service is a **single-instance pilot**. Exact quote matching does not prove answer truth or entailment, and a passing report is not a safety/compliance certification. The design deliberately keeps paid model execution out of the public HTTP API.

## Install and verify

Python 3.11+ is required. Run commands from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest
python -m ruff check src tests scripts examples
eds-assurance doctor
```

The offline tests make no paid model calls. See [the verification record](docs/VERIFICATION.md) for locally executed checks and outstanding cloud/runtime verification.

## Run the synthetic demonstration

```bash
eds-assurance demo --state-dir .local --output reports/demo.json
eds-assurance verify --state-dir .local --checkpoint reports/demo.json
```

The baseline intentionally fails, and the candidate satisfies a six-case smoke suite. Responses, cost, and latency in this demonstration are manually authored. Re-running it reproduces metrics and decisions; run IDs, timestamps, report hashes, and audit checkpoints change.

## Integrate a real model

First pin the curated public documentation dataset:

```bash
eds-assurance ingest --state-dir .local --tenant demo \
  --sources examples/public-sources.json --dataset examples/public-dataset.json
```

Copy the returned `dataset_id`. Choose an exact model ID available in your provider account and set the corresponding API key in your local environment or secret manager. **Do not paste keys into chat, source files, or GitHub issues.** Model access and structured-output support vary by account/model.

Plan the run first; this requires no provider key and makes no network calls:

```bash
eds-assurance collect --state-dir .local --tenant demo \
  --provider openai --model "$OPENAI_MODEL" --dataset-id "$DATASET_ID" \
  --max-requests 4 --policy examples/live-policy.json
```

Add `--execute` to send each case's permitted evidence to the selected provider and perform the paid requests:

```bash
eds-assurance collect --state-dir .local --tenant demo \
  --provider openai --model "$OPENAI_MODEL" --dataset-id "$DATASET_ID" \
  --max-requests 4 --max-output-tokens 1024 --timeout-seconds 30 \
  --policy examples/live-policy.json --execute
```

Select `--provider anthropic` with `ANTHROPIC_API_KEY`, or `--provider xai` with `XAI_API_KEY`, to use the other adapters. OpenAI uses `OPENAI_API_KEY`. The model argument is always explicit; no model or current pricing is guessed.

Reports and partial ledgers default to unique private files under `.local/collections/`. The final report is created only when every case returns a complete valid response. Timeouts, refusals, truncated output, malformed JSON, and HTTP errors halt collection and retain the attempt ledger. There are no automatic retries. An interrupted in-flight request may still be billable.

To estimate cost, supply both `--input-rate-usd-per-million` and `--output-rate-usd-per-million` using rates you have checked for that exact model. Without rates or usage, cost remains `null` and the cost gate fails. Estimates do not account fully for cache premiums, discounts, tiers, or taxes. Request/output limits bound the experiment; **there is no guaranteed dollar spending cap**. Apply provider-side spend controls as appropriate.

The curated public source pack contains original summaries of linked documentation, reviewed 2026-10-23. It is a small contract exercise, not an independent benchmark of model intelligence or security.

## Run the authenticated API

For a **new** development environment:

```bash
python scripts/bootstrap_env.py --output .local/development.env
set -a
source .local/development.env
set +a
uvicorn eds_assurance.api:create_app --factory --host 127.0.0.1 --port 8000
```

The script refuses to overwrite existing credentials and selects `.local/api/assurance.db`, separate from the demo's key-file store. Retain the signing key with its database; creating a new key is not rotation. When using the CLI against this API store, load the same environment and pass `--state-dir .local/api`. API and CLI must use the same audit key for a shared database.

In another terminal, load the same private environment and run:

```bash
python examples/api_workflow.py
```

`/healthz` returns liveness/version; `/readyz` checks storage availability. Both disclose no project data. Every `/v1/` route requires a scoped bearer credential. The public API accepts and evaluates recorded observations; it cannot trigger paid model calls. See [API.md](docs/API.md).

## Back up and restore

Use SQLite's native backup mechanism rather than copying a live `.db` file:

```bash
eds-assurance backup --state-dir .local/api --output .local/backups/snapshot.db
```

This creates a consistent snapshot and per-tenant audit checkpoints without copying the signing key. Retain the snapshot, checkpoint, and protected key through separate backup controls. Backup verification and a restore exercise are covered by tests; cloud backup retention is an operator responsibility. See [deployment operations](docs/DEPLOYMENT.md).

## Live demo and deployment

**Hosted API:** [eds-assurance.onrender.com](https://eds-assurance.onrender.com/) · [health](https://eds-assurance.onrender.com/healthz) · [readiness](https://eds-assurance.onrender.com/readyz). This free portfolio demo exposes service information publicly; `/v1/` operations require private credentials. Live provider inference has not been verified.

A standalone repository is the project boundary: [Shawdaimarie/eds-assurance](https://github.com/Shawdaimarie/eds-assurance). Its own CI and releases can be linked from Essential Digital Solution. See the deployment runbook for publication, CI, and hosting verification status.

```bash
python scripts/validate_render.py
```

The default `render.yaml` uses Render’s **free** plan in Ohio, without a disk. This is a portfolio demo: its SQLite records are lost on idle shutdown, restart, or deploy. Use public test data only. The root endpoint and `X-EDS-Storage` response header disclose this mode. Free services sleep after inactivity and share workspace usage limits. A separate `deploy/render.persistent.yaml` retains the optional paid disk configuration; it requires a separate budget approval. Both configurations pass Render’s current public JSON schema. See the deployment runbook for the verified live status.

The free service uses `/tmp/eds-assurance/assurance.db`, an externally supplied audit key, scoped API credentials, and the platform's `PORT`. No provider keys are required by the hosted API. Local SQLite storage is scoped to one instance; only the optional paid disk configuration provides persistence across restarts. See [the deployment runbook](docs/DEPLOYMENT.md) for secret setup, backups, smoke tests, and rollback.

For local containers, load the application environment and run `docker compose up --build`. The root filesystem is read-only and the container runs as a non-root user. Local container execution remains unverified because Docker's daemon is unavailable; GitHub CI includes a container health/authenticated-workflow check.

## Documentation

- [Provider contracts and collection](docs/PROVIDERS.md)
- [Secure provider-key setup](docs/KEY_SETUP.md)
- [Architecture and decisions](docs/ARCHITECTURE.md)
- [Security and trust boundaries](docs/SECURITY.md)
- [Deployment and GitHub runbook](docs/DEPLOYMENT.md)
- [Public research register](docs/RESEARCH.md)
- [Professional development roadmap](docs/ROADMAP.md)
- [Verification and limitations](docs/VERIFICATION.md)
- [Synthetic demonstration report](reports/demo.json)

CLI exit codes: `0` for successful commands or passed evaluation gates; `2` for a completed evaluation with failed gates; `1` for invalid input, collection failure, or integrity/setup failure. Reports contain evidence and responses; treat real observations as sensitive and review them before publication.
