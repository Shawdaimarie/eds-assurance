"""Run a deliberately small public-data smoke check using a private key file."""

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path


PROVIDERS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "xai": "XAI_API_KEY"}


def read_configuration(path):
    path = Path(path)
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode) or mode & 0o077:
        raise ValueError("Credential file must be a private regular file (chmod 600)")
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1 or not isinstance(data.get("providers"), dict) or not data["providers"]:
        raise ValueError("Invalid credential file structure")
    for name, value in data["providers"].items():
        if name not in PROVIDERS or not isinstance(value, dict) or set(value) != {"api_key", "model"}:
            raise ValueError("Invalid provider configuration")
        if any(not isinstance(value[field], str) or not value[field] for field in ("api_key", "model")):
            raise ValueError("Missing provider credential or model ID")
    return data["providers"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=".local/provider-keys.json")
    parser.add_argument("--state-dir", default=".local/live-verification")
    parser.add_argument("--execute", action="store_true", help="Send public evidence and incur up to four bounded requests per configured provider")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        providers = read_configuration(args.config)
    except (ValueError, OSError, KeyError, TypeError):
        raise SystemExit("Unable to load private provider configuration. No keys were printed and no model calls were made.") from None
    plan = {"providers": list(providers), "cases_per_provider": 4, "max_output_tokens_per_request": 512,
            "execute": args.execute, "notice": "Uses only the curated public documentation dataset; no hard dollar cap. Review provider billing limits."}
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return 0
    environment = dict(os.environ)
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
    print(json.dumps({"results": results, "cost_note": "No rates were supplied, so the cost gate remains false even for completed integrations."}, indent=2))
    return 0 if all(item["integration_completed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
