from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

import app.controlled_content as controlled_content
from app.main import app


REQUEST = {
    "exchange_url": "http://47.94.58.72/v1/grants/exchange",
    "grant_code": "one-time-code",
    "audience": "mimotrust_guardian_backend",
    "content_id": "article-001",
    "content_version": "1",
}


def test_exchange_proxy_forwards_grant_fields_without_exchange_url(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"manifest": {"content": {}, "assets": []}})

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(controlled_content.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(controlled_content, "validate_public_url", lambda _url: None)

    response = TestClient(app).post("/v1/controlled-content/exchange", json=REQUEST)

    assert response.status_code == 200
    assert captured["url"] == REQUEST["exchange_url"]
    assert '"grant_code":"one-time-code"' in str(captured["body"])
    assert "exchange_url" not in str(captured["body"])


def test_exchange_proxy_rejects_missing_manifest(monkeypatch) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"unexpected": True})
    )
    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(controlled_content.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(controlled_content, "validate_public_url", lambda _url: None)

    response = TestClient(app).post("/v1/controlled-content/exchange", json=REQUEST)

    assert response.status_code == 502
    assert "manifest" in response.json()["detail"]


def test_guardian_uses_local_exchange_proxy() -> None:
    receiver = (
        "android/app/src/main/java/com/mimotrust/xiaozhen/overlay/"
        "ControlledContentReceiver.kt"
    )
    source = open(receiver, encoding="utf-8").read()

    assert '.put("exchange_url", grant.exchangeUrl)' in source
    assert 'BuildConfig.MIMO_API_BASE_URL + "v1/controlled-content/exchange"' in source
    assert "Request.Builder().url(grant.exchangeUrl)" not in source
