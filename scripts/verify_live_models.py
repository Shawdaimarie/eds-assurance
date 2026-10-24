"""Run a deliberately small public-data smoke check using a private key file."""

import argparse
import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
import stat
import subprocess
import sys
from pathlib import Path


PROVIDERS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "xai": "XAI_API_KEY"}


def read_private_data(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Credential file must not be a symbolic link")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "r", encoding="utf-8") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 32768:
            raise ValueError("Credential file must be a private regular file (chmod 600), under 32 KiB")
        return json.load(source)


def read_configuration(path):
    data = read_private_data(path)
    if data.get("schema_version") != 1 or not isinstance(data.get("providers"), dict) or not data["providers"]:
        raise ValueError("Invalid credential file structure")
    for name, value in data["providers"].items():
        if name not in PROVIDERS or not isinstance(value, dict) or set(value) != {"api_key", "model"}:
            raise ValueError("Invalid provider configuration")
        if any(not isinstance(value[field], str) or not value[field] for field in ("api_key", "model")):
            raise ValueError("Missing provider credential or model ID")
    return data["providers"]


def validate_free_credit_review(data, providers, now=None):
    """Validate a recent operator attestation, not a provider billing API response."""
    review = data.get("free_credit_review", {})
    try:
        reviewed = datetime.fromisoformat(review["reviewed_at"])
        age = ((now or datetime.now(timezone.utc)) - reviewed).total_seconds()
        if not -60 <= age <= 1800 or set(review["providers"]) != set(providers):
            raise ValueError
        for name, configuration in providers.items():
            account = review["providers"][name]
            amount = Decimal(account["promotional_credit_usd"])
            purchased = Decimal(account["purchased_credit_usd"])
            fingerprint = hashlib.sha256(configuration["api_key"].encode()).hexdigest()
            if (not amount.is_finite() or amount <= 0 or not purchased.is_finite() or purchased != 0
                    or account["model"] != configuration["model"] or account["key_sha256"] != fingerprint
                    or any(account[field] is not False for field in
                           ("payment_method_on_file", "auto_reload_enabled", "postpaid_enabled"))):
                raise ValueError
    except (KeyError, TypeError, ValueError, InvalidOperation, AttributeError):
        raise ValueError("Free-credit review missing, stale, or unsafe. Recheck promotional balance and billing controls; no calls allowed.") from None


def claim_single_use(path):
    marker = Path(str(path) + ".used")
    descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write("Free-credit verification claimed. Do not automatically retry. Recheck provider billing first.\n")
    return marker


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=".local/provider-keys.json")
    parser.add_argument("--state-dir", default=".local/live-verification")
    parser.add_argument("--execute", action="store_true", help="Send public evidence and incur up to four bounded requests per configured provider")
    parser.add_argument("--free-credits-only", action="store_true",
                        help="Require a recent private operator review showing promotional credit and no paid funding path")
    args = parser.parse_args(argv)
    if args.execute and not args.free_credits_only:
        raise SystemExit("Execution blocked. Use --free-credits-only after reviewing provider credits and billing; no model calls were made.")
    root = Path(__file__).resolve().parents[1]
    try:
        providers = read_configuration(args.config)
    except (ValueError, OSError, KeyError, TypeError):
        raise SystemExit("Unable to load private provider configuration. No keys were printed and no model calls were made.") from None
    review_valid = False
    if args.free_credits_only:
        try:
            validate_free_credit_review(read_private_data(args.config), providers)
            review_valid = True
        except (ValueError, OSError):
            if args.execute:
                raise SystemExit("Execution blocked: a fresh free-credit billing review is required. No model calls were made.") from None
    plan = {"providers": list(providers), "cases_per_provider": 4, "max_output_tokens_per_request": 512,
            "execute": args.execute, "free_credit_review_valid": review_valid,
            "already_used": Path(str(args.config) + ".used").exists(),
            "notice": "Public evidence only. Billing review is an operator attestation, not an API-enforced monetary cap. No credit purchases or paid fallback are authorized."}
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return 0
    try:
        claim_single_use(args.config)
    except OSError:
        raise SystemExit("Execution blocked: this private configuration was already used or cannot be locked. Recheck billing before a new review; no calls were made.") from None
    environment = dict(os.environ)
    for key in PROVIDERS.values():
        environment.pop(key, None)
    # This independent smoke store uses its own key file, not the deployment signing key.
    environment.pop("EDS_AUDIT_KEY_HEX", None)
    command = [sys.executable, "-m", "eds_assurance.cli"]
    ingested = subprocess.run(command + ["ingest", "--state-dir", args.state_dir,
                             "--sources", "examples/public-sources.json", "--dataset", "examples/public-dataset.json"],
                             cwd=root, env=environment, capture_output=True, text=True, timeout=30)
    if ingested.returncode != 0:
        raise SystemExit("Public-data ingestion failed; no model calls were made.")
    dataset_id = json.loads(ingested.stdout)["dataset_id"]
    results = []
    for name, value in providers.items():
        child_environment = dict(environment)
        child_environment[PROVIDERS[name]] = value["api_key"]
        result = subprocess.run(command + ["collect", "--state-dir", args.state_dir, "--provider", name,
                                "--model", value["model"], "--dataset-id", dataset_id, "--max-requests", "4",
                                "--max-output-tokens", "512", "--policy", "examples/live-policy.json", "--execute"],
                                cwd=root, env=child_environment, capture_output=True, text=True)
        if result.returncode in (0, 2):
            summary = json.loads(result.stdout)
            results.append({"provider": name, "integration_completed": True,
                            "report": summary["report"], "ledger": summary["ledger"],
                            "release_gate_passed": summary["release_gate_passed"]})
        else:
            results.append({"provider": name, "integration_completed": False,
                            "detail": "Collection stopped; inspect the private attempt ledger. No provider error body is printed."})
            break
    print(json.dumps({"results": results, "skipped_providers": [name for name in providers if name not in {item["provider"] for item in results}],
                      "cost_note": "No rates were supplied, so the cost gate remains false even for completed integrations. Check the provider ledger to confirm promotional-credit use; this script cannot certify a bill."}, indent=2))
    return 0 if all(item["integration_completed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
