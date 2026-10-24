# Private provider-key setup

The public API does not need provider keys and cannot trigger model spending. Keep model credentials on your development machine for initial verification; only place them on Render if you deliberately run the operator collector there. Never put them in GitHub repository files, Actions artifacts, frontend code, chat, or logs.

## 1. Confirm a free-only API account before creating a key

Do not buy credits, start a paid subscription, add a payment method, enable automatic reload/top-up, or enable invoiced/postpaid billing for this workflow. Consumer chat allowances do not establish API credits. Check each provider's **API** billing page for a positive, unexpired **promotional** balance; purchased credits do not satisfy a free-credits-only test.

Use a dedicated API organization/workspace with no purchased balance, no payment method, no automatic recharge, and no invoicing agreement. If those conditions cannot be confirmed, leave that provider blocked. Do not remove payment methods or alter billing for unrelated existing workloads just to pass this check.

- **OpenAI:** [API billing](https://platform.openai.com/settings/organization/billing/overview), [API keys](https://platform.openai.com/api-keys), [permissions](https://developers.openai.com/api/docs/guides/rbac), and [spend controls](https://developers.openai.com/api/docs/guides/spend-limits). Alerts are not caps; even hard-limit enforcement can lag. Do not assume that a free usage tier grants a promotional balance.
- **Anthropic:** [API billing](https://platform.claude.com/settings/billing), [API keys](https://platform.claude.com/settings/keys), and [trial-credit documentation](https://platform.claude.com/docs/en/about-claude/pricing). Confirm the actual grant and its expiry in your own Console. Existing eligible subscribers may have [included API credits](https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers); do not subscribe or upgrade to obtain them for a $0 task. Included credits can fall back to purchased credits or invoicing, so review the organization funding settings.
- **xAI:** [Console](https://console.x.ai/), [API billing controls](https://docs.x.ai/console/billing), and [API security](https://docs.x.ai/console/faq/security). Confirm promotional balance, auto top-up off, and invoiced billing limit $0. A zero balance is a blocker, not an invitation to add funds.

Choose the exact model available in that account, with the lowest suitable text-inference pricing and structured-output support. Restrict a new key to the inference endpoint and chosen model when the provider supports it; do not use admin credentials. Create/reveal/copy the key yourself. First-time account terms, identity checks, and credential creation require your own participation.

## 2. Save one eligible provider through a masked local prompt

After the billing review succeeds, run from the repository root in your own interactive Terminal. For example, **only if Anthropic has verified trial credits**:

```bash
python3 scripts/configure_provider_keys.py --providers anthropic --free-credits-only --output .local/anthropic-trial.json
```

Select `openai` or `xai` instead only when that provider independently passes the same review. The helper asks for the current promotional balance and confirmation that all paid funding paths are absent **before** prompting for a key. It hides key input, asks for the exact model ID, and saves an owner-only (0600), Git-ignored file. It refuses to overwrite an existing file. No keys are printed and no provider calls are made.

The file contains plaintext credentials protected by local filesystem permissions; keep the device encrypted and do not screen-record, trace the shell, or embed the secret in a command. It is not a managed vault. Never paste keys into chat or screenshots.

## 3. Review and execute once, within 30 minutes

Use the Python environment where EDS Assurance is installed:

```bash
python scripts/verify_live_models.py --config .local/anthropic-trial.json --free-credits-only
```

This dry run makes no model calls. `free_credit_review_valid` must be true and `already_used` false. The review is bound to the configured model/key, expires after 30 minutes, rejects zero/non-finite promotional balances, and blocks any paid funding path recorded as enabled. These are checks of your **operator attestation**, not a live provider billing API response. Do not set the confirmations to YES unless you actually checked the account.

Recheck the billing page immediately before execution and ensure no other workload is drawing down the grant. Then:

```bash
python scripts/verify_live_models.py --config .local/anthropic-trial.json --free-credits-only --execute
```

Execution claims the private configuration once using an exclusive `.used` marker. It sends four curated public-documentation cases per eligible provider, at most 512 generated tokens each, with no automatic retries or tools. A provider failure stops subsequent providers. Do not delete the marker or retry an uncertain request automatically: timed-out requests can still consume credits. Inspect the private ledger and recheck billing before creating a new review/configuration with a new output filename.

The script cannot enforce a provider's invoice or guarantee credit accounting. Request limits, a recorded balance, and a manual review are not hard monetary caps. If a free-only funding path cannot be established, **do not execute**. No credit purchases, paid fallback, or account upgrades are authorized.

Afterward, inspect the provider usage/billing ledger to confirm the calls drew only from the promotional grant and no cash amount is due. Retain the report, request IDs, token counts, and credit balance checks privately in `.local/live-verification/`. Only sanitized status and paths are printed. A completed model collection is distinct from release-policy success: unknown cost still fails the cost gate, and the small public suite is not a model-quality benchmark. The separate `integration_completed` field only confirms that all responses were collected.

## 4. Render application credentials

The free hosted API uses temporary storage and cannot trigger model calls. The $0 hosting budget does not authorize paid provider requests. The hosted API needs `EDS_AUDIT_KEY_HEX` and `EDS_API_TOKENS_JSON`, independent of OpenAI/Anthropic/xAI keys. Keep the audit key stable for its database. Supply secrets through Render's secret environment settings; do not commit their values in `render.yaml`.

Model-provider keys are optional on Render. If you later configure one for an operator-run collection, add only the corresponding `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `XAI_API_KEY` in the intended service, and preserve unrelated environment settings. Never expose a paid collection endpoint to ordinary tenant credentials.
