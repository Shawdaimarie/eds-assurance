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
