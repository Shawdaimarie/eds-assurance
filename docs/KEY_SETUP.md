# Private provider-key setup

The public API does not need provider keys and cannot trigger model spending. Keep model credentials on your development machine for initial verification; only place them on Render if you deliberately run the operator collector there. Never put them in GitHub repository files, Actions artifacts, frontend code, chat, or logs.

## 1. Create the provider credentials yourself

Use a dedicated project/workspace for EDS Assurance. Choose a key with only the inference permissions and exact models needed by your test, and review the provider's current billing controls before generating it. Do not use organization-admin credentials.

- **OpenAI:** [API keys](https://platform.openai.com/api-keys); [project/role permissions](https://developers.openai.com/api/docs/guides/rbac). Use a project-scoped key that can create Responses for the selected model.
- **Anthropic:** [Claude API keys](https://platform.claude.com/settings/keys); [official key guide](https://platform.claude.com/docs/en/get-api-key). Personal development and shared production workloads should use the appropriate key types described by the provider.
- **xAI:** [xAI Console](https://console.x.ai/); [API security guidance](https://docs.x.ai/console/faq/security). Select the inference endpoint and model access needed for your test.

Create/reveal/copy keys yourself in the provider console. An API key is separate from a consumer chat subscription. Model availability and billing access must be verified in the API account. No credentials or credit purchase are generated automatically by this repository.

## 2. Save keys through a masked local prompt

From the repository root, run:

```bash
python3 scripts/configure_provider_keys.py --providers openai anthropic xai
```

You can start with just `--providers openai`. The helper requires an interactive terminal, hides each key, asks for its exact model ID, and writes `.local/provider-keys.json` with mode 0600. It refuses to overwrite an existing file. The file contains plaintext secrets protected by local permissions; use your normal encrypted device/secret-storage controls. It is not a replacement for a managed secret vault.

The helper does not print keys and makes no model calls. Do not run it with shell tracing, screen recording, or a command that embeds the secret itself. Never paste a key into a chat message to finish this step.

## 3. Plan the bounded verification

Use the Python environment where EDS Assurance is installed:

```bash
python scripts/verify_live_models.py --config .local/provider-keys.json
```

This shows provider names and request limits only. It makes no model requests. To execute the plan deliberately:

```bash
python scripts/verify_live_models.py --config .local/provider-keys.json --execute
```

The check sends the curated public-documentation dataset: four requests per configured provider, up to 512 generated tokens each, with no automatic retries. It does not have a guaranteed dollar cap. Check billing controls and the exact model's prices before executing. Results and partial ledgers stay in `.local/live-verification/`; only sanitized paths/status are printed.

Because this helper does not supply current price rates, completed model integrations can still have a failed release gate for unknown cost. The separate `integration_completed` field indicates whether all provider responses were collected, not whether factual accuracy or release policy was established. A failure retains a private attempt ledger rather than printing a raw provider error.

## 4. Render application credentials

The free hosted API uses temporary storage and cannot trigger model calls. The $0 hosting budget does not authorize paid provider requests. The hosted API needs `EDS_AUDIT_KEY_HEX` and `EDS_API_TOKENS_JSON`, independent of OpenAI/Anthropic/xAI keys. Keep the audit key stable for its database. Supply secrets through Render's secret environment settings; do not commit their values in `render.yaml`.

Model-provider keys are optional on Render. If you later configure one for an operator-run collection, add only the corresponding `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `XAI_API_KEY` in the intended service, and preserve unrelated environment settings. Never expose a paid collection endpoint to ordinary tenant credentials.
