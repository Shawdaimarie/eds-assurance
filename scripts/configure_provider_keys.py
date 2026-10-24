"""Collect existing provider keys privately in the user's terminal; never echo them."""

import argparse
import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import getpass
import json
import os
import re
import sys
from pathlib import Path


PROVIDERS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "xai": "XAI_API_KEY"}


def save_configuration(path, providers, free_credit_review=None):
    if not providers or any(name not in PROVIDERS for name in providers):
        raise ValueError("Choose at least one supported provider")
    for value in providers.values():
        if set(value) != {"api_key", "model"}:
            raise ValueError("Invalid provider configuration")
        key, model = value["api_key"], value["model"]
        if not isinstance(key, str) or len(key) < 12 or any(c.isspace() for c in key):
            raise ValueError("API key must be a nonempty credential without whitespace")
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", model):
            raise ValueError("Supply an exact provider model identifier")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        data = {"schema_version": 1, "providers": providers}
        if free_credit_review is not None:
            data["free_credit_review"] = free_credit_review
        json.dump(data, output)
        output.write("\n")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", choices=list(PROVIDERS), nargs="+", default=["openai"])
    parser.add_argument("--output", default=".local/provider-keys.json")
    parser.add_argument("--free-credits-only", action="store_true",
                        help="Ask for a fresh promotional-credit/billing review before saving a single-use verification configuration")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit("Run this command yourself in an interactive terminal; keys must not be echoed or piped.")
    if Path(args.output).exists():
        raise SystemExit("Refusing to overwrite existing credentials. Choose a new --output path.")
    providers = {}
    reviewed_accounts = {}
    try:
        for name in dict.fromkeys(args.providers):
            print(f"Configure {name}; create the key in your provider console first.")
            if args.free_credits_only:
                print("Inspect this provider's API billing page, not a chat subscription. No purchases or new subscriptions are authorized.")
                amount = input("Unexpired promotional API credit balance in USD: ").strip()
                try:
                    balance = Decimal(amount)
                    if not balance.is_finite() or balance <= 0:
                        raise ValueError
                except (InvalidOperation, ValueError):
                    raise ValueError("No positive promotional balance was confirmed") from None
                answer = input("Confirm: NO purchased credits, NO payment method, NO auto-reload, and NO invoiced/postpaid billing [type YES]: ")
                if answer != "YES":
                    raise ValueError("Paid funding paths must be absent; billing review incomplete")
                reviewed_accounts[name] = {"promotional_credit_usd": str(balance), "purchased_credit_usd": "0",
                                           "payment_method_on_file": False, "auto_reload_enabled": False,
                                           "postpaid_enabled": False}
            key = getpass.getpass(f"{PROVIDERS[name]} (hidden): ").strip()
            model = input("Exact model ID available in that account: ").strip()
            providers[name] = {"api_key": key, "model": model}
            if args.free_credits_only:
                reviewed_accounts[name].update(model=model, key_sha256=hashlib.sha256(key.encode()).hexdigest())
        review = {"reviewed_at": datetime.now(timezone.utc).isoformat(), "providers": reviewed_accounts} if args.free_credits_only else None
        path = save_configuration(args.output, providers, review)
    except (ValueError, OSError, EOFError):
        raise SystemExit("Configuration was not saved. Check the terminal inputs and destination permissions.") from None
    except KeyboardInterrupt:
        raise SystemExit("Cancelled; no provider calls were made.") from None
    print(f"Saved private configuration to {path}. Keys were not displayed; no model calls were made.")


if __name__ == "__main__":
    main()
