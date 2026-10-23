import importlib.util
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from eds_assurance.api import create_app
from eds_assurance.store import Store
from conftest import request_for


ROOT = Path(__file__).parents[1]


def test_blueprint_keeps_persistence_and_secrets_explicit():
    body = yaml.safe_load((ROOT / "render.yaml").read_text())
    service, = body["services"]
    assert service["numInstances"] == 1
    assert "scaling" not in service
    assert service["disk"]["mountPath"] == "/var/data"
    variables = {item["key"]: item for item in service["envVars"]}
    assert variables["EDS_DB_PATH"]["value"].startswith("/var/data/")
    for key in ("EDS_AUDIT_KEY_HEX", "EDS_API_TOKENS_JSON"):
        assert variables[key] == {"key": key, "sync": False}
    assert not {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY"} & variables.keys()
    assert "$PORT" in service["startCommand"]
    assert service["healthCheckPath"] == "/readyz"


def test_verified_backup_can_restore_after_later_writes(seeded, settings, tmp_path):
    store, dataset_id = seeded
    report = store.run("alpha", request_for(dataset_id))
    snapshot = tmp_path / "backup" / "snapshot.db"
    exported = store.backup(snapshot)
    checkpoint, = exported["checkpoints"]
    store.run("alpha", request_for(dataset_id))
    restored = Store(snapshot, settings.audit_key)
    assert restored.verify_audit("alpha", checkpoint) == checkpoint
    assert restored.get_run("alpha", report["run_id"]) == report
    assert snapshot.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        store.backup(snapshot)


def test_bootstrap_does_not_print_or_overwrite_credentials(tmp_path):
    specification = importlib.util.spec_from_file_location("bootstrap_env", ROOT / "scripts/bootstrap_env.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    path = tmp_path / "private.env"
    module.generate(path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert "EDS_AUDIT_KEY_HEX=" in path.read_text()
    with pytest.raises(FileExistsError):
        module.generate(path)


def test_readiness_checks_storage_without_exposing_records(settings, store):
    with TestClient(create_app(settings)) as client:
        assert client.get("/readyz").json() == {"status": "ready"}
        with store.connect() as db:
            db.execute("DELETE FROM metadata")
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json() == {"detail": "Storage is not ready"}
