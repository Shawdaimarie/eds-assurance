import json

import pytest
from fastapi.testclient import TestClient

from eds_assurance.api import BodyLimitMiddleware, create_app
from eds_assurance.security import Settings
from conftest import TOKEN_A, TOKEN_B, TOKEN_READ, fixture_json, request_for


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def test_end_to_end_api_and_tenant_isolation(client):
    for source in fixture_json("sources.json"):
        assert client.post("/v1/sources", json=source, headers=auth(TOKEN_A)).status_code == 201
    dataset = client.post("/v1/datasets", json=fixture_json("dataset.json"), headers=auth(TOKEN_A)).json()
    dataset_id = dataset["dataset_id"]
    assert client.get(f"/v1/datasets/{dataset_id}", headers=auth(TOKEN_B)).status_code == 404
    assert client.post("/v1/datasets", json=fixture_json("dataset.json"), headers=auth(TOKEN_B)).status_code == 404
    request = request_for(dataset_id).model_dump()
    assert client.post("/v1/runs", json=request, headers=auth(TOKEN_B)).status_code == 404
    response = client.post("/v1/runs", json=request, headers=auth(TOKEN_A))
    assert response.status_code == 201
    report = response.json()
    assert report["release_gate_passed"]
    assert client.get(f"/v1/runs/{report['run_id']}", headers=auth(TOKEN_B)).status_code == 404
    assert client.get(f"/v1/runs/{report['run_id']}", headers=auth(TOKEN_READ)).json() == report
    checkpoint = client.get("/v1/audit/checkpoint", headers=auth(TOKEN_A)).json()
    assert checkpoint["verified"] and checkpoint["checkpoint"]["event_count"] == 5
    assert client.get("/v1/audit/checkpoint", headers=auth(TOKEN_B)).json()["checkpoint"]["event_count"] == 0


def test_authentication_and_scopes(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/v1/audit/checkpoint").status_code == 401
    assert client.get("/v1/audit/checkpoint", headers=auth("invalid")).status_code == 401
    assert client.post("/v1/sources", json=fixture_json("sources.json")[0], headers=auth(TOKEN_READ)).status_code == 403
    assert client.get("/openapi.json").status_code == 404


def test_tenant_cannot_be_overridden_in_body(client):
    body = fixture_json("sources.json")[0]
    body["tenant"] = "beta"
    response = client.post("/v1/sources", json=body, headers=auth(TOKEN_A))
    assert response.status_code == 422
    assert "input" not in response.json()["detail"][0]


def test_body_limit(client):
    response = client.post("/v1/sources", content=b"x" * 524_289, headers=auth(TOKEN_A))
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_chunked_body_limit_without_content_length():
    import asyncio
    called = False
    sent = []
    messages = iter([{"type": "http.request", "body": b"1234", "more_body": True},
                     {"type": "http.request", "body": b"5678", "more_body": False}])
    async def downstream(scope, receive, send):
        nonlocal called
        called = True
    async def receive():
        return next(messages)
    async def send(message):
        sent.append(message)
    asyncio.run(BodyLimitMiddleware(downstream, 6)({"type": "http", "headers": []}, receive, send))
    assert not called
    assert sent[0]["status"] == 413


def test_incomplete_run_returns_422_without_mutation(client, seeded):
    store, dataset_id = seeded
    before = store.verify_audit("alpha")
    request = request_for(dataset_id).model_dump()
    request["observations"].pop()
    assert client.post("/v1/runs", json=request, headers=auth(TOKEN_A)).status_code == 422
    assert store.verify_audit("alpha") == before


def test_security_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("EDS_AUDIT_KEY_HEX", raising=False)
    monkeypatch.delenv("EDS_API_TOKENS_JSON", raising=False)
    with pytest.raises(ValueError, match="Invalid security configuration"):
        Settings.from_env()
    monkeypatch.setenv("EDS_AUDIT_KEY_HEX", "ab" * 32)
    monkeypatch.setenv("EDS_API_TOKENS_JSON", json.dumps([{"token": TOKEN_A, "tenant": "alpha", "scopes": ["read"]}]))
    config = Settings.from_env()
    assert config.authenticate(TOKEN_A).tenant == "alpha"
    assert config.authenticate("incorrect") is None
    monkeypatch.setenv("EDS_API_TOKENS_JSON", json.dumps([{"token": TOKEN_A, "tenant": "alpha", "scopes": ["admin"]}]))
    with pytest.raises(ValueError):
        Settings.from_env()
