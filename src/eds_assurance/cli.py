"""Run the reproducible fixture or verify its persisted evidence."""

import argparse
import json
import os
import secrets
import sys
import uuid
from pathlib import Path

from .models import Dataset, Policy, RunRequest, Source
from .store import Conflict, IntegrityError, NotFound, Store


def load(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def local_store(state_dir, create=False):
    state_dir = Path(state_dir)
    key_path = state_dir / "audit.key"
    configured_key = os.environ.get("EDS_AUDIT_KEY_HEX")
    if create:
        state_dir.mkdir(parents=True, exist_ok=True)
        if not configured_key and not key_path.exists():
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(secrets.token_bytes(32))
    if (not configured_key and not key_path.exists()) or (not create and not (state_dir / "assurance.db").exists()):
        raise ValueError("State is missing; run demo first or supply the correct --state-dir")
    key = bytes.fromhex(configured_key) if configured_key else key_path.read_bytes()
    if len(key) != 32:
        raise ValueError("Audit key must contain exactly 32 bytes")
    return Store(state_dir / "assurance.db", key)


def run_demo(args):
    store = local_store(args.state_dir, create=True)
    fixtures = Path(args.fixtures)
    for source in load(fixtures / "sources.json"):
        store.put_source("demo", Source.model_validate(source))
    dataset = store.put_dataset("demo", Dataset.model_validate(load(fixtures / "dataset.json")))
    reports = {}
    for label in ("baseline", "candidate"):
        request = load(fixtures / f"{label}.json")
        request["dataset_id"] = dataset["dataset_id"]
        reports[label] = store.run("demo", RunRequest.model_validate(request))
    summary = {
        "notice": "SYNTHETIC FIXTURE: manually authored responses and telemetry. No live model or aerospace system was evaluated.",
        "dataset_manifest": dataset,
        "audit_checkpoint": store.verify_audit("demo"),
        **reports,
    }
    write_json(args.output, summary)
    print(json.dumps({"report": str(Path(args.output).resolve()),
                      "baseline_gate_passed": reports["baseline"]["release_gate_passed"],
                      "candidate_gate_passed": reports["candidate"]["release_gate_passed"],
                      "audit_event_count": summary["audit_checkpoint"]["event_count"]}, indent=2))
    return 0 if reports["candidate"]["release_gate_passed"] else 2


def main():
    parser = argparse.ArgumentParser(prog="eds-assurance")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Evaluate synthetic baseline and candidate fixtures")
    demo.add_argument("--state-dir", default=".local")
    demo.add_argument("--fixtures", default="examples")
    demo.add_argument("--output", default="reports/demo.json")
    verify = sub.add_parser("verify", help="Verify audit records and an optional external checkpoint")
    verify.add_argument("--state-dir", default=".local")
    verify.add_argument("--tenant", default="demo")
    verify.add_argument("--checkpoint", help="Previously exported checkpoint or demo report")
    evaluate = sub.add_parser("evaluate", help="Evaluate a recorded RunRequest against an existing dataset")
    evaluate.add_argument("--state-dir", default=".local")
    evaluate.add_argument("--tenant", default="demo")
    evaluate.add_argument("--request", required=True)
    evaluate.add_argument("--output", default="reports/evaluation.json")
    ingest = sub.add_parser("ingest", help="Ingest public/approved sources and pin an evaluation dataset")
    ingest.add_argument("--state-dir", default=".local")
    ingest.add_argument("--tenant", default="demo")
    ingest.add_argument("--sources", default="examples/sources.json")
    ingest.add_argument("--dataset", default="examples/dataset.json")
    live = sub.add_parser("collect", help="Plan or explicitly execute provider calls against pinned evidence")
    live.add_argument("--state-dir", default=".local")
    live.add_argument("--tenant", default="demo")
    live.add_argument("--dataset-id", required=True)
    live.add_argument("--provider", choices=["openai", "anthropic", "xai"], required=True)
    live.add_argument("--model", required=True, help="Exact model ID available in your provider account")
    live.add_argument("--max-requests", type=int, required=True)
    live.add_argument("--max-output-tokens", type=int, default=1024)
    live.add_argument("--max-input-chars", type=int, default=100_000)
    live.add_argument("--timeout-seconds", type=float, default=30.0)
    live.add_argument("--input-rate-usd-per-million", type=float)
    live.add_argument("--output-rate-usd-per-million", type=float)
    live.add_argument("--policy", help="JSON Policy; approved separately from model output")
    live.add_argument("--label", default="live-evaluation")
    live.add_argument("--ledger", help="New private partial-collection ledger path")
    live.add_argument("--output", help="New private report path")
    live.add_argument("--execute", action="store_true", help="Authorize egress of permitted evidence and paid model calls")
    sub.add_parser("doctor", help="Report provider-key presence and local tooling without exposing secrets")
    backup = sub.add_parser("backup", help="Create a verified SQLite snapshot without copying the signing key")
    backup.add_argument("--state-dir", default=".local")
    backup.add_argument("--output", required=True, help="New snapshot .db path")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            from .providers import ENDPOINTS
            print(json.dumps({"providers": {name: {"key_configured": bool(os.environ.get(key)), "endpoint": endpoint}
                                            for name, (endpoint, key) in ENDPOINTS.items()},
                              "audit_key_configured": bool(os.environ.get("EDS_AUDIT_KEY_HEX"))}, indent=2))
            return 0
        if args.command == "ingest":
            sources = [Source.model_validate(item) for item in load(args.sources)]
            dataset = Dataset.model_validate(load(args.dataset))
            if len({source.source_id for source in sources}) != len(sources):
                raise ValueError("source IDs in the ingestion file must be unique")
            allowed = {source for case in dataset.cases for source in case.allowed_source_ids}
            if not allowed <= {source.source_id for source in sources}:
                raise ValueError("ingestion sources must include all dataset source references")
            store = local_store(args.state_dir, create=True)
            for source in sources:
                store.put_source(args.tenant, source)
            print(json.dumps(store.put_dataset(args.tenant, dataset), indent=2))
            return 0
        if args.command == "demo":
            return run_demo(args)
        store = local_store(args.state_dir)
        if args.command == "backup":
            from .collection import write_private_json
            output = Path(args.output)
            checkpoint = output.with_suffix(output.suffix + ".checkpoints.json")
            if output.exists() or checkpoint.exists():
                raise ValueError("Choose a new backup and checkpoint path")
            result = store.backup(output)
            write_private_json(checkpoint, result)
            print(json.dumps({"snapshot": str(output.resolve()), "checkpoints": str(checkpoint.resolve())}))
            return 0
        if args.command == "collect":
            from .collection import collect, validate_limits, write_private_json
            from .providers import ProviderAdapter
            dataset, sources = store.evaluation_inputs(args.tenant, args.dataset_id)
            validate_limits(args.provider, args.model, dataset, sources, args.max_requests,
                            args.max_output_tokens, args.max_input_chars)
            policy = Policy.model_validate(load(args.policy)) if args.policy else Policy()
            plan = {"execute": args.execute, "provider": args.provider, "model": args.model,
                    "dataset_id": args.dataset_id, "case_count": len(dataset.cases),
                    "max_requests": args.max_requests, "max_output_tokens_per_request": args.max_output_tokens,
                    "notice": "Only per-case permitted evidence is sent. No retries or tools. Dollar costs require explicit rates and are estimates."}
            if not args.execute:
                print(json.dumps(plan, indent=2))
                return 0
            collection_id = str(uuid.uuid4())
            output = Path(args.output) if args.output else Path(args.state_dir) / "collections" / f"{collection_id}.report.json"
            ledger = Path(args.ledger) if args.ledger else Path(args.state_dir) / "collections" / f"{collection_id}.ledger.json"
            if output.exists() or ledger.exists() or output.resolve() == ledger.resolve():
                raise ValueError("Choose distinct new output and ledger paths")
            adapter = ProviderAdapter(args.provider, args.model, timeout_seconds=args.timeout_seconds,
                                      max_output_tokens=args.max_output_tokens)
            try:
                report = collect(store, args.tenant, args.dataset_id, adapter, max_requests=args.max_requests,
                                 max_input_chars=args.max_input_chars, input_rate=args.input_rate_usd_per_million,
                                 output_rate=args.output_rate_usd_per_million, policy=policy,
                                 ledger_path=ledger, label=args.label)
                write_private_json(output, report)
            finally:
                adapter.close()
            print(json.dumps({"run_id": report["run_id"], "report": str(output.resolve()),
                              "ledger": str(ledger.resolve()), "release_gate_passed": report["release_gate_passed"]}, indent=2))
            return 0 if report["release_gate_passed"] else 2
        if args.command == "verify":
            checkpoint = load(args.checkpoint) if args.checkpoint else None
            if checkpoint is not None:
                checkpoint = checkpoint.get("audit_checkpoint", checkpoint)
            result = store.verify_audit(args.tenant, checkpoint)
            print(json.dumps({"verified": True, "checkpoint": result}, indent=2))
            return 0
        report = store.run(args.tenant, RunRequest.model_validate(load(args.request)))
        write_json(args.output, report)
        print(json.dumps({"run_id": report["run_id"], "release_gate_passed": report["release_gate_passed"]}))
        return 0 if report["release_gate_passed"] else 2
    except (ValueError, OSError, Conflict, IntegrityError, NotFound, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
