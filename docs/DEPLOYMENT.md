# GitHub and deployment runbook

Published repository: [Shawdaimarie/eds-assurance](https://github.com/Shawdaimarie/eds-assurance). GitHub CI run [40041827502](https://github.com/Shawdaimarie/eds-assurance/actions/runs/40041827502) passed Python 3.11–3.13 tests and the deployment/container job. A $0 free demo deployment is being prepared in the confirmed Essential Digital Solution workspace; the paid persistent proposal will not be applied. Live model verification awaits privately configured provider credentials.

## Before publication

Run tests, static checks, package build, fixture verification, and Blueprint validation. Inspect the files being committed: `.local/`, provider credentials, databases, signing keys, real model observations, and backup snapshots must remain excluded. The checked-in report is explicitly synthetic.

```bash
python -m pytest
python -m ruff check src tests scripts examples
python -m build --no-isolation
python scripts/validate_render.py
git status --short
```

The source package is also available as a Git bundle. The bundle contains the prepared commit and no runtime state or keys. A local commit is not evidence that GitHub CI has executed.

## Published standalone repository

The public repository was created through the signed-in GitHub interface and populated through the GitHub connector. The local `main` branch tracks `origin/main` at `https://github.com/Shawdaimarie/eds-assurance.git`.

For subsequent changes, inspect `git status`, commit reviewed files, and push `main`. Check the resulting CI jobs. Unit/API/provider tests run on Python 3.11, 3.12, and 3.13. The deployment job validates the current Render schema, builds a container, and runs health plus authenticated API checks. No provider keys are used by CI. Required checks should be enabled on `main` before treating it as the deploy branch.

## Render free portfolio demo

The approved hosting budget is **$0**, in the workspace renamed **Essential Digital Solution** (formerly Shawdai's workspace). The default `render.yaml` uses `plan: free`, one Python process/instance in Ohio, no attached disk, and `EDS_DB_PATH=/tmp/eds-assurance/assurance.db`. `EDS_STORAGE_MODE=ephemeral-demo` makes the root endpoint and every response's `X-EDS-Storage` header disclose temporary storage. Authenticated tenant isolation remains enforced.

Render's free filesystem is reset on idle shutdown, restart, or deploy. Free services sleep after 15 minutes of inactivity and share 750 monthly instance hours per workspace. Existing free services also consume that allowance. Free services do not support shell access or persistent disks. This deployment is for public test data and portfolio demonstration; it is not a durable evidence repository.

No payment method is added. The workspace build-pipeline spend limit was verified at $0. Without a payment method, Render suspends services/disables builds at applicable free usage limits instead of billing overages. Do not add paid resources or upgrade automatically.

The Render connector can create this single free service directly from `main`; no Blueprint instance or disk is required. Set the pinned build/start commands and variables from `render.yaml`, plus the private application credentials. The connector creation endpoint defaults to commit-based auto-deploy; inspect and align the service's CI/deploy and readiness settings afterward. The Blueprint remains the reviewable configuration reference. Validate both Blueprint files with `python scripts/validate_render.py`.

| Variable | Required value |
|---|---|
| `EDS_AUDIT_KEY_HEX` | Exactly 32 random bytes represented as 64 hexadecimal characters |
| `EDS_API_TOKENS_JSON` | JSON list of token, tenant, and scope records; tokens must be 32–256 URL-safe characters |

Keep secret values in Render's environment settings and a protected local file, never repository files, chat, issues, screenshots, or logs. No provider key is required by the hosted API, and it cannot initiate paid model requests. Live provider verification is a separate local operator action; the $0 hosting budget does not grant a model-spending budget.

## Optional persistent configuration (not authorized for deployment)

`deploy/render.persistent.yaml` retains the paid 0.5 CPU/512 MB service and a 1 GB disk at `/var/data`. It is not applied under the approved $0 budget. A future change requires explicit budget approval and current pricing review. Use `/var/data/assurance.db` and the matching audit key for that deployment. Only this disk-backed mode supports the service-shell backup operations below.

Official references reviewed on 2026-10-23: [free service limits](https://render.com/docs/free), [Blueprint specification](https://render.com/docs/blueprint-spec), [persistent disks](https://render.com/docs/disks), and [environment variables](https://render.com/docs/configure-environment-variables).

## Verify the deployment

1. Inspect build/deploy status and logs without revealing environment values.
2. Check HTTPS `/healthz` for version `0.2.0` and `/readyz` for storage readiness.
3. Confirm unauthenticated `/v1/audit/checkpoint` returns 401.
4. Use a dedicated test tenant and credential to ingest sample sources, create a dataset, submit a fixture, retrieve its report, and export an audit checkpoint.
5. Confirm a second tenant cannot read the first tenant's dataset or run.
6. In free demo mode, verify that records reset after restart/redeploy; do not promise persistence. Only test record retention when the separately approved persistent configuration is deployed.

Run `python examples/api_workflow.py --base-url https://your-service.example` from a trusted shell with dedicated test-tenant credentials. The script requires HTTPS for remote origins and refuses redirects; do not place production tokens in it. Test the container locally first when a Docker daemon is available. Local Docker execution was unavailable during preparation; the remote container and authenticated API workflow passed in GitHub CI run 40041827502.

## Backups, recovery, and rollback

Use `eds-assurance backup --state-dir /var/data --output /var/data/backups/<unique-name>.db` from a trusted service shell. This uses SQLite's native backup API, verifies the resulting copy, and writes per-tenant checkpoints alongside it. It does not copy the signing key. Export backups/checkpoints to controlled external storage and retain the audit key through a separate secret-management path.

The local suite exercises restoring a snapshot after subsequent writes. For operational recovery, stop writes, restore a verified snapshot with its matching audit key to a separate test instance, verify every checkpoint, and confirm expected runs before replacing service data. Do not restore a filesystem disk snapshot as a substitute for an application-consistent SQLite backup.

Disk-backed services support one instance and have deploy/restart interruptions. A code rollback does not roll back data. Keep a verified application-consistent backup before a future schema migration. This release adds metadata fields to new reports and a CLI collector; it does not replace existing evidence tables or delete older reports.

Before organization-facing use, establish identity federation, edge timeouts/rate limits, backup retention, secret rotation, security-event logging, operational ownership, and incident procedures. Multi-instance availability needs an external database and a separate worker design; it is not enabled by changing `numInstances` on this SQLite configuration.
