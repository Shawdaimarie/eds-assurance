"""Complete local HTTP example; credentials are read from the environment."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def validate_base_url(value):
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Use a service origin without credentials, path, query, or fragment")
    if not parsed.hostname or parsed.scheme not in ("http", "https"):
        raise ValueError("Use an HTTP(S) service origin")
    if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Remote smoke tests require HTTPS")
    return value.rstrip("/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    fixtures = Path(__file__).parent
    configured = json.loads(os.environ["EDS_API_TOKENS_JSON"])
    credential = next(item for item in configured if {"read", "write", "evaluate"} <= set(item["scopes"]))
    base = validate_base_url(args.base_url)
    opener = build_opener(NoRedirect())

    def call(path, body=None):
        payload = json.dumps(body).encode() if body is not None else None
        request = Request(base + path, data=payload, headers={
            "Authorization": "Bearer " + credential["token"], "Content-Type": "application/json"
        })
        with opener.open(request, timeout=15) as response:
            return json.load(response)

    for source in json.loads((fixtures / "sources.json").read_text()):
        call("/v1/sources", source)
    dataset = call("/v1/datasets", json.loads((fixtures / "dataset.json").read_text()))
    run = json.loads((fixtures / "candidate.json").read_text())
    run["dataset_id"] = dataset["dataset_id"]
    report = call("/v1/runs", run)
    assert call("/v1/runs/" + report["run_id"]) == report
    checkpoint = call("/v1/audit/checkpoint")
    print(json.dumps({"notice": "Synthetic fixture only; no model was called.", "run_id": report["run_id"],
                      "release_gate_passed": report["release_gate_passed"], "audit": checkpoint}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except HTTPError as exc:
        raise SystemExit(f"HTTP workflow failed with status {exc.code}") from None
