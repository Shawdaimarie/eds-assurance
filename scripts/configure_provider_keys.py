"""Collect existing provider keys privately in the user's terminal; never echo them."""

import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path


PROVIDERS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "xai": "XAI_API_KEY"}


def save_configuration(path, providers):
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
        json.dump({"schema_version": 1, "providers": providers}, output)
        output.write("\n")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", choices=list(PROVIDERS), nargs="+", default=["openai"])
    parser.add_argument("--output", default=".local/provider-keys.json")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit("Run this command yourself in an interactive terminal; keys must not be echoed or piped.")
    if Path(args.output).exists():
        raise SystemExit("Refusing to overwrite existing credentials. Choose a new --output path.")
    providers = {}
    try:
        for name in dict.fromkeys(args.providers):
            print(f"Configure {name}; create the key in your provider console first.")
            key = getpass.getpass(f"{PROVIDERS[name]} (hidden): ").strip()
            model = input("Exact model ID available in that account: ").strip()
            providers[name] = {"api_key": key, "model": model}
        path = save_configuration(args.output, providers)
    except (ValueError, OSError, EOFError):
        raise SystemExit("Configuration was not saved. Check the terminal inputs and destination permissions.") from None
    except KeyboardInterrupt:
        raise SystemExit("Cancelled; no provider calls were made.") from None
    print(f"Saved private configuration to {path}. Keys were not displayed; no model calls were made.")


if __name__ == "__main__":
    main()
