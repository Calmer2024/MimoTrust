from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

import app.controlled_content as controlled_content
from app.main import app
from app.jobs.worker import _download_controlled_asset


REQUEST = {
    "exchange_url": "http://47.94.58.72/v1/grants/exchange",
    "grant_code": "one-time-code",
    "audience": "mimotrust_guardian_backend",
    "content_id": "article-001",
    "content_version": "1",
}


def _submission(content_type: str = "article") -> dict[str, object]:
    request_id = str(uuid4())
    view_state: dict[str, object]
    if content_type in {"video", "audio"}:
        view_state = {"position_ms": 0, "duration_ms": 1000, "is_playing": False}
    elif content_type == "image_gallery":
        view_state = {"active_asset_index": 0, "asset_count": 1}
    else:
        view_state = {"scroll_ratio": 0.25, "block_index": 0}
    return {
        "request_id": request_id,
        "guardian_app_version": "0.1.0",
        "context": {
            "schema_version": "2.2",
            "event_id": request_id,
            "trigger": "guardian_request",
            "source_app": "mimotrust_controlled_content",
            "provider": {
                "provider_id": "mimotrust_sandbox",
                "application_id": "com.mimotrust.controlledcontent",
            },
            "content_ref": {
                "content_type": content_type,
                "content_id": f"{content_type.replace('_', '-')}-001",
                "content_version": "v1",
                "content_hash": "a" * 64,
                "canonical_url": f"https://sandbox.mimotrust.local/content/{content_type}-001",
            },
            "content_access": {
                "mode": "grant_exchange",
                "exchange_url": "http://47.94.58.72/v1/grants/exchange",
                "grant_code": "one-time-code",
                "audience": "mimotrust_guardian_backend",
                "expires_at": "2099-08-03T00:00:00Z",
                "scopes": ["manifest:read", "asset:read"],
            },
            "view_state": view_state,
            "observed_at": "2026-08-03T00:00:00Z",
        },
    }


def _manifest(submission: dict[str, object]) -> dict[str, object]:
    context = submission["context"]
    assert isinstance(context, dict)
    content_ref = context["content_ref"]
    assert isinstance(content_ref, dict)
    content_type = str(content_ref["content_type"])
    mime_type = {
        "video": "video/mp4",
        "audio": "audio/mpeg",
        "article": "text/plain",
        "rich_article": "image/png",
        "image_gallery": "image/png",
    }[content_type]
    return {
        "manifest_version": "1.0",
        "provider": {"provider_id": "mimotrust_sandbox"},
        "content": {
            **content_ref,
            "title": "测试内容",
            "author": "测试作者",
            "published_at": "2026-08-03T00:00:00Z",
        },
        "assets": [{
            "asset_id": "analysis-main",
            "role": "analysis",
            "mime_type": mime_type,
            "source_url": "https://8.8.8.8/asset",
            "sha256": "b" * 64,
            "size_bytes": 16,
            "derivation": "original",
        }],
        "rights": {
            "purpose": ["fact_check"],
            "retention_seconds": 3600,
            "redistribution_allowed": False,
        },
        "sandbox": {
            "access_enforcement": "mock_gateway_only",
            "development_asset": True,
        },
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


def test_content_context_exchanges_manifest_and_creates_job(monkeypatch) -> None:
    submission = _submission("audio")
    captured: dict[str, object] = {}

    async def fake_exchange(request):
        captured["exchange"] = request
        return {"manifest": _manifest(submission)}

    async def fake_create(request, device_id):
        captured["job_request"] = request
        captured["device_id"] = device_id
        return SimpleNamespace(
            job_id="job-001",
            status="queued",
            created_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
        ), False

    monkeypatch.setattr(controlled_content, "_exchange_with_gateway", fake_exchange)
    monkeypatch.setattr(controlled_content.runtime, "create", fake_create)

    response = TestClient(app).post(
        "/v1/content-contexts",
        json=submission,
        headers={"X-Device-Id": "test-device"},
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-001"
    assert response.json()["request_id"] == submission["request_id"]
    assert captured["device_id"] == "test-device"
    job_request = captured["job_request"]
    assert job_request.source.type == "controlled_manifest"
    assert job_request.client_request_id == submission["request_id"]
    assert '"content_type":"audio"' in job_request.source.value


def test_content_context_retry_reuses_job_without_redeeming_grant(monkeypatch) -> None:
    submission = _submission("video")
    existing = SimpleNamespace(
        job_id="job-existing",
        status="running",
        created_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    async def fake_existing(device_id, request_id):
        assert device_id == "retry-device"
        assert request_id == submission["request_id"]
        return existing

    async def unexpected_exchange(_request):
        raise AssertionError("an idempotent retry must not redeem the one-time grant")

    monkeypatch.setattr(controlled_content.runtime, "get_by_identity", fake_existing)
    monkeypatch.setattr(controlled_content, "_exchange_with_gateway", unexpected_exchange)

    response = TestClient(app).post(
        "/v1/content-contexts",
        json=submission,
        headers={"X-Device-Id": "retry-device"},
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-existing"
    assert response.json()["reused"] is True
    assert response.json()["cache_status"] == "in_progress"


def test_content_context_rejects_request_id_mismatch() -> None:
    submission = _submission()
    submission["request_id"] = str(uuid4())

    response = TestClient(app).post("/v1/content-contexts", json=submission)

    assert response.status_code == 422


def test_content_context_rejects_manifest_identity_mismatch(monkeypatch) -> None:
    submission = _submission("rich_article")
    manifest = _manifest(submission)
    manifest["content"]["content_hash"] = "c" * 64

    async def fake_exchange(_request):
        return {"manifest": manifest}

    monkeypatch.setattr(controlled_content, "_exchange_with_gateway", fake_exchange)

    response = TestClient(app).post("/v1/content-contexts", json=submission)

    assert response.status_code == 502
    assert "content_hash" in response.json()["detail"]


def test_content_context_rejects_wrong_analysis_asset_type(monkeypatch) -> None:
    submission = _submission("video")
    manifest = _manifest(submission)
    manifest["assets"][0]["mime_type"] = "image/png"

    async def fake_exchange(_request):
        return {"manifest": manifest}

    monkeypatch.setattr(controlled_content, "_exchange_with_gateway", fake_exchange)

    response = TestClient(app).post("/v1/content-contexts", json=submission)

    assert response.status_code == 502
    assert "分析素材" in response.json()["detail"]


def test_controlled_asset_download_retries_transient_connect_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("transient", request=request)
        return httpx.Response(200, content=b"verified image")

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            content, final_url = await _download_controlled_asset(
                client,
                "https://8.8.8.8/image.png",
            )
        assert content == b"verified image"
        assert final_url == "https://8.8.8.8/image.png"

    asyncio.run(scenario())
    assert attempts == 2
