import hashlib
import json
from pathlib import Path

import pytest

from eds_assurance.models import Dataset, RunRequest, Source
from eds_assurance.security import Credential, Principal, Settings
from eds_assurance.store import Store


EXAMPLES = Path(__file__).parents[1] / "examples"
TOKEN_A = "test-project-a-" + "a" * 40
TOKEN_B = "test-project-b-" + "b" * 40
TOKEN_READ = "test-reader-" + "r" * 40


@pytest.fixture
def settings(tmp_path):
    credentials = tuple(
        Credential(hashlib.sha256(token.encode()).digest(), Principal(tenant, frozenset(scopes)))
        for token, tenant, scopes in [
            (TOKEN_A, "alpha", {"read", "write", "evaluate"}),
            (TOKEN_B, "beta", {"read", "write", "evaluate"}),
            (TOKEN_READ, "alpha", {"read"}),
        ]
    )
    return Settings(tmp_path / "evidence.db", b"k" * 32, credentials)


@pytest.fixture
def store(settings):
    return Store(settings.db_path, settings.audit_key)


def fixture_json(name):
    return json.loads((EXAMPLES / name).read_text())


@pytest.fixture
def seeded(store):
    for source in fixture_json("sources.json"):
        store.put_source("alpha", Source.model_validate(source))
    dataset = store.put_dataset("alpha", Dataset.model_validate(fixture_json("dataset.json")))
    return store, dataset["dataset_id"]


def request_for(dataset_id, name="candidate.json"):
    body = fixture_json(name)
    body["dataset_id"] = dataset_id
    return RunRequest.model_validate(body)
