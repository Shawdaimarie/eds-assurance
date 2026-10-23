"""Create a new private shell-compatible env file without displaying secrets."""

import argparse
import json
import os
import secrets
import shlex
from pathlib import Path


def generate(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {
        "EDS_DB_PATH": ".local/api/assurance.db",
        "EDS_AUDIT_KEY_HEX": secrets.token_hex(32),
        "EDS_API_TOKENS_JSON": json.dumps([{
            "token": secrets.token_urlsafe(32), "tenant": "eds-development", "scopes": ["read", "write", "evaluate"]
        }]),
    }
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write("# Private development credentials. Retain the audit key with its database.\n")
        for name, value in values.items():
            output.write(name + "=" + shlex.quote(value) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".local/development.env")
    args = parser.parse_args()
    try:
        created = generate(args.output)
    except FileExistsError:
        raise SystemExit("Refusing to overwrite existing credentials; use a new path.") from None
    print(f"Created private credential file: {created}. No provider keys are generated.")
