import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_provider_configuration_permissions_and_round_trip(tmp_path):
    writer = script("configure_provider_keys")
    reader = script("verify_live_models")
    providers = {"openai": {"api_key": "test-only-provider-credential", "model": "exact-model-id"}}
    path = writer.save_configuration(tmp_path / "private.json", providers)
    assert path.stat().st_mode & 0o777 == 0o600
    assert reader.read_configuration(path) == providers
    with pytest.raises(FileExistsError):
        writer.save_configuration(path, providers)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="private"):
        reader.read_configuration(path)


def test_secret_validation_never_echoes_input(tmp_path):
    writer = script("configure_provider_keys")
    secret = "sensitive credential with whitespace"
    with pytest.raises(ValueError) as raised:
        writer.save_configuration(tmp_path / "private.json", {"openai": {"api_key": secret, "model": "exact-model"}})
    assert secret not in str(raised.value)
    assert not (tmp_path / "private.json").exists()


def free_review(providers, reviewed_at=None):
    import hashlib
    from datetime import datetime, timezone
    return {"reviewed_at": reviewed_at or datetime.now(timezone.utc).isoformat(), "providers": {
        name: {"promotional_credit_usd": "5.00", "purchased_credit_usd": "0", "payment_method_on_file": False,
               "auto_reload_enabled": False, "postpaid_enabled": False, "model": value["model"],
               "key_sha256": hashlib.sha256(value["api_key"].encode()).hexdigest()}
        for name, value in providers.items()
    }}


@pytest.mark.parametrize("field,value", [
    ("promotional_credit_usd", "0"), ("promotional_credit_usd", "NaN"),
    ("promotional_credit_usd", "Infinity"), ("purchased_credit_usd", "0.01"),
    ("payment_method_on_file", True), ("auto_reload_enabled", True), ("postpaid_enabled", True),
    ("auto_reload_enabled", 0), ("model", "different-model"), ("key_sha256", "different-key"),
])
def test_free_credit_review_blocks_paid_funding_and_binding_changes(field, value):
    reader = script("verify_live_models")
    providers = {"anthropic": {"api_key": "test-only-provider-credential", "model": "exact-model-id"}}
    review = free_review(providers)
    review["providers"]["anthropic"][field] = value
    with pytest.raises(ValueError, match="review"):
        reader.validate_free_credit_review({"free_credit_review": review}, providers)


@pytest.mark.parametrize("age_seconds", [1801, -61])
def test_free_credit_review_expires_and_rejects_future_dates(age_seconds):
    from datetime import datetime, timedelta, timezone
    reader = script("verify_live_models")
    providers = {"anthropic": {"api_key": "test-only-provider-credential", "model": "exact-model-id"}}
    now = datetime.now(timezone.utc)
    review = free_review(providers, (now - timedelta(seconds=age_seconds)).isoformat())
    with pytest.raises(ValueError):
        reader.validate_free_credit_review({"free_credit_review": review}, providers, now)


def test_private_credentials_reject_symlinks(tmp_path):
    writer, reader = script("configure_provider_keys"), script("verify_live_models")
    original = writer.save_configuration(tmp_path / "private.json", {
        "openai": {"api_key": "test-only-provider-credential", "model": "exact-model-id"}})
    link = tmp_path / "link.json"
    link.symlink_to(original)
    with pytest.raises(ValueError, match="symbolic"):
        reader.read_configuration(link)


@pytest.mark.parametrize("reviewed", [False, True])
def test_unapproved_or_reused_execution_cannot_start_a_subprocess(tmp_path, monkeypatch, reviewed):
    writer, reader = script("configure_provider_keys"), script("verify_live_models")
    providers = {"anthropic": {"api_key": "test-only-provider-credential", "model": "exact-model-id"}}
    path = writer.save_configuration(tmp_path / "private.json", providers, free_review(providers) if reviewed else None)
    if reviewed:
        reader.claim_single_use(path)
    def forbidden(*args, **kwargs):
        pytest.fail("Unsafe execution reached a subprocess")
    monkeypatch.setattr(reader.subprocess, "run", forbidden)
    with pytest.raises(SystemExit, match="blocked"):
        reader.main(["--config", str(path), "--execute", "--free-credits-only"])
    with pytest.raises(SystemExit, match="blocked"):
        reader.main(["--config", str(path), "--execute"])


def test_free_credit_execution_stops_after_first_failure_and_never_echoes_provider_error(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    writer, reader = script("configure_provider_keys"), script("verify_live_models")
    providers = {name: {"api_key": "test-only-provider-credential", "model": "exact-model-id"}
                 for name in ("anthropic", "xai")}
    path = writer.save_configuration(tmp_path / "private.json", providers, free_review(providers))
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if "ingest" in command:
            return SimpleNamespace(returncode=0, stdout='{"dataset_id": "synthetic"}')
        assert "collect" in command and command[command.index("--provider") + 1] == "anthropic"
        assert kwargs["env"]["ANTHROPIC_API_KEY"] == providers["anthropic"]["api_key"]
        assert "XAI_API_KEY" not in kwargs["env"]
        return SimpleNamespace(returncode=1, stdout="private-provider-error-body")
    monkeypatch.setattr(reader.subprocess, "run", run)
    monkeypatch.setenv("XAI_API_KEY", "unrelated-secret")
    assert reader.main(["--config", str(path), "--execute", "--free-credits-only"]) == 1
    assert len(calls) == 2
    output = capsys.readouterr().out
    assert '"skipped_providers": [\n    "xai"' in output
    assert "private-provider-error-body" not in output
    assert "test-only-provider-credential" not in output
    with pytest.raises(SystemExit, match="blocked"):
        reader.main(["--config", str(path), "--execute", "--free-credits-only"])
    assert len(calls) == 2
