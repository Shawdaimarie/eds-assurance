"""Transactional tenant-scoped storage with a keyed audit chain."""

import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .evaluation import canonical, content_digest, digest, evaluate
from .models import Dataset, RunRequest, Source


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class IntegrityError(Exception):
    pass


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str | Path, audit_key: bytes):
        if len(audit_key) < 32:
            raise ValueError("audit key must contain at least 32 bytes")
        self.path = Path(path)
        self.audit_key = audit_key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources (
                    tenant TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                    content_hash TEXT NOT NULL, PRIMARY KEY (tenant, id));
                CREATE TABLE IF NOT EXISTS datasets (
                    tenant TEXT NOT NULL, id TEXT NOT NULL, manifest TEXT NOT NULL,
                    PRIMARY KEY (tenant, id));
                CREATE TABLE IF NOT EXISTS runs (
                    tenant TEXT NOT NULL, id TEXT NOT NULL, report TEXT NOT NULL,
                    PRIMARY KEY (tenant, id));
                CREATE TABLE IF NOT EXISTS audit (
                    tenant TEXT NOT NULL, seq INTEGER NOT NULL, timestamp TEXT NOT NULL,
                    event TEXT NOT NULL, previous_hash TEXT NOT NULL, chain_hash TEXT NOT NULL,
                    PRIMARY KEY (tenant, seq));
            """)
            db.execute("BEGIN IMMEDIATE")
            expected_key_check = hmac.new(audit_key, b"eds-assurance-audit-key-v1", hashlib.sha256).hexdigest()
            stored_key_check = db.execute("SELECT value FROM metadata WHERE name='audit_key_check'").fetchone()
            if stored_key_check is None:
                db.execute("INSERT INTO metadata VALUES ('audit_key_check', ?)", (expected_key_check,))
            elif not hmac.compare_digest(stored_key_check["value"], expected_key_check):
                raise IntegrityError("audit key does not match this store")
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _chain_hash(self, tenant, seq, timestamp, event, previous):
        body = canonical({"tenant": tenant, "seq": seq, "timestamp": timestamp,
                          "event": event, "previous_hash": previous})
        return hmac.new(self.audit_key, body.encode(), hashlib.sha256).hexdigest()

    def check_ready(self):
        with self.connect() as db:
            row = db.execute("SELECT value FROM metadata WHERE name='audit_key_check'").fetchone()
            expected = hmac.new(self.audit_key, b"eds-assurance-audit-key-v1", hashlib.sha256).hexdigest()
            if row is None or not hmac.compare_digest(row["value"], expected):
                raise IntegrityError("store is not ready")

    def backup(self, destination):
        """Make an application-consistent SQLite copy; never copy the signing key."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with self.connect() as source:
                target = sqlite3.connect(destination)
                try:
                    source.backup(target)
                finally:
                    target.close()
            snapshot = Store(destination, self.audit_key)
            with snapshot.connect() as db:
                tenants = [row[0] for row in db.execute("SELECT DISTINCT tenant FROM audit ORDER BY tenant")]
            return {"created_at": utcnow(), "checkpoints": [snapshot.verify_audit(tenant) for tenant in tenants]}
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def _audit(self, db, tenant, event):
        last = db.execute("SELECT seq, chain_hash FROM audit WHERE tenant=? ORDER BY seq DESC LIMIT 1",
                          (tenant,)).fetchone()
        seq = last["seq"] + 1 if last else 1
        previous = last["chain_hash"] if last else "0" * 64
        timestamp = utcnow()
        chain = self._chain_hash(tenant, seq, timestamp, event, previous)
        db.execute("INSERT INTO audit VALUES (?, ?, ?, ?, ?, ?)",
                   (tenant, seq, timestamp, canonical(event), previous, chain))

    def put_source(self, tenant: str, source: Source):
        body = source.model_dump()
        source_hash = content_digest(source.content)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT body FROM sources WHERE tenant=? AND id=?",
                                  (tenant, source.source_id)).fetchone()
            if existing:
                if existing["body"] != canonical(body):
                    raise Conflict("source IDs are immutable; create a new versioned ID")
            else:
                db.execute("INSERT INTO sources VALUES (?, ?, ?, ?)",
                           (tenant, source.source_id, canonical(body), source_hash))
                self._audit(db, tenant, {"type": "source.created", "source_id": source.source_id,
                                        "record_digest": digest(body), "content_sha256": source_hash})
        return {"source_id": source.source_id, "content_sha256": source_hash, "record_digest": digest(body)}

    def _source(self, db, tenant, source_id):
        row = db.execute("SELECT body, content_hash FROM sources WHERE tenant=? AND id=?",
                         (tenant, source_id)).fetchone()
        if row is None:
            raise NotFound("source not found")
        source = json.loads(row["body"])
        if content_digest(source["content"]) != row["content_hash"]:
            raise IntegrityError("source content digest mismatch")
        return source

    def put_dataset(self, tenant: str, dataset: Dataset):
        source_ids = sorted({source for case in dataset.cases for source in case.allowed_source_ids})
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            records = {source_id: digest(self._source(db, tenant, source_id)) for source_id in source_ids}
            manifest = {"schema_version": 1, "dataset": dataset.model_dump(), "source_record_digests": records}
            dataset_id = digest(manifest)
            existing = db.execute("SELECT 1 FROM datasets WHERE tenant=? AND id=?",
                                  (tenant, dataset_id)).fetchone()
            if not existing:
                db.execute("INSERT INTO datasets VALUES (?, ?, ?)", (tenant, dataset_id, canonical(manifest)))
                self._audit(db, tenant, {"type": "dataset.created", "dataset_id": dataset_id})
        return {"dataset_id": dataset_id, **manifest}

    def _dataset(self, db, tenant, dataset_id):
        row = db.execute("SELECT manifest FROM datasets WHERE tenant=? AND id=?",
                         (tenant, dataset_id)).fetchone()
        if row is None:
            raise NotFound("dataset not found")
        manifest = json.loads(row["manifest"])
        if digest(manifest) != dataset_id:
            raise IntegrityError("dataset manifest digest mismatch")
        return manifest

    def get_dataset(self, tenant, dataset_id):
        with self.connect() as db:
            return {"dataset_id": dataset_id, **self._dataset(db, tenant, dataset_id)}

    def evaluation_inputs(self, tenant, dataset_id):
        """Read one consistent, integrity-checked snapshot before sending evidence externally."""
        self.verify_audit(tenant)
        with self.connect() as db:
            db.execute("BEGIN")
            manifest = self._dataset(db, tenant, dataset_id)
            sources = {}
            for source_id, record_digest in manifest["source_record_digests"].items():
                source = self._source(db, tenant, source_id)
                if digest(source) != record_digest:
                    raise IntegrityError("source record does not match pinned evidence")
                sources[source_id] = source
            return Dataset.model_validate(manifest["dataset"]), sources

    def run(self, tenant: str, request: RunRequest):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            manifest = self._dataset(db, tenant, request.dataset_id)
            dataset = Dataset.model_validate(manifest["dataset"])
            sources = {}
            for source_id, record_digest in manifest["source_record_digests"].items():
                source = self._source(db, tenant, source_id)
                if digest(source) != record_digest:
                    raise IntegrityError("source record does not match the pinned dataset")
                sources[source_id] = source
            result = evaluate(dataset, sources, request)
            request_body = request.model_dump()
            report = {"run_id": str(uuid.uuid4()), "created_at": utcnow(),
                      "dataset_id": request.dataset_id, "label": request.label,
                      "model_label": request.model_label, "observation_kind": request.observation_kind,
                      "input_sha256": digest(request_body), "policy_sha256": digest(request.policy.model_dump()),
                      "policy": request.policy.model_dump(), "request": request_body, **result}
            report["report_sha256"] = digest(report)
            db.execute("INSERT INTO runs VALUES (?, ?, ?)", (tenant, report["run_id"], canonical(report)))
            self._audit(db, tenant, {"type": "run.completed", "run_id": report["run_id"],
                                    "report_sha256": report["report_sha256"]})
        return report

    def get_run(self, tenant, run_id):
        with self.connect() as db:
            row = db.execute("SELECT report FROM runs WHERE tenant=? AND id=?", (tenant, run_id)).fetchone()
            if row is None:
                raise NotFound("run not found")
            report = json.loads(row["report"])
            claimed = report.pop("report_sha256")
            if not hmac.compare_digest(claimed, digest(report)):
                raise IntegrityError("report digest mismatch")
            report["report_sha256"] = claimed
            return report

    def verify_audit(self, tenant, expected_checkpoint=None):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM audit WHERE tenant=? ORDER BY seq", (tenant,)).fetchall()
            previous = "0" * 64
            checkpoint = {"event_count": 0, "root_hash": previous}
            checkpoints = {0: previous}
            for seq, row in enumerate(rows, 1):
                event = json.loads(row["event"])
                expected = self._chain_hash(tenant, seq, row["timestamp"], event, previous)
                if row["seq"] != seq or row["previous_hash"] != previous or not hmac.compare_digest(row["chain_hash"], expected):
                    raise IntegrityError("audit chain verification failed")
                # Bind signed events to current records, not just to neighboring events.
                if event["type"] == "source.created":
                    try:
                        source = self._source(db, tenant, event["source_id"])
                    except NotFound:
                        raise IntegrityError("audited source is missing") from None
                    if digest(source) != event["record_digest"]:
                        raise IntegrityError("source record does not match audit event")
                elif event["type"] == "dataset.created":
                    try:
                        self._dataset(db, tenant, event["dataset_id"])
                    except NotFound:
                        raise IntegrityError("audited dataset is missing") from None
                elif event["type"] == "run.completed":
                    row_run = db.execute("SELECT report FROM runs WHERE tenant=? AND id=?",
                                         (tenant, event["run_id"])).fetchone()
                    if row_run is None:
                        raise IntegrityError("audited run is missing")
                    report = json.loads(row_run["report"])
                    claimed = report.pop("report_sha256")
                    if digest(report) != claimed or claimed != event["report_sha256"]:
                        raise IntegrityError("run does not match audit event")
                previous = row["chain_hash"]
                checkpoints[seq] = previous
            checkpoint = {"tenant": tenant, "event_count": len(rows), "root_hash": previous}
            if expected_checkpoint is not None:
                if expected_checkpoint.get("tenant") != tenant:
                    raise IntegrityError("external checkpoint belongs to a different tenant")
                count = expected_checkpoint["event_count"]
                if checkpoints.get(count) != expected_checkpoint["root_hash"]:
                    raise IntegrityError("external checkpoint is missing or does not match")
            return checkpoint
