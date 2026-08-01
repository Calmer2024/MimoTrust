from __future__ import annotations

import asyncio
from types import SimpleNamespace
from pathlib import Path

from fastapi.testclient import TestClient

from app.jobs.models import CreateJobRequest, JobSource, JobView
from app.jobs.runtime import JobRuntime
from app.jobs.store import SqlJobStore
from app.jobs.worker import build_mobile_card
from app.jobs.models import utc_now


def test_memory_runtime_is_idempotent_and_orders_events() -> None:
    async def scenario() -> None:
        runtime = JobRuntime("memory")
        request = CreateJobRequest(
            source=JobSource(value="https://example.com/video"),
            client_request_id="request-1234",
        )
        first = await runtime.store.create(
            JobView(
                job_id="job-one",
                device_id="device-one",
                client_request_id=request.client_request_id,
                source=request.source,
            )
        )
        second = await runtime.store.create(
            JobView(
                job_id="job-two",
                device_id="device-one",
                client_request_id=request.client_request_id,
                source=request.source,
            )
        )
        assert first[1] is False
        assert second[1] is True
        assert second[0].job_id == "job-one"
        await runtime.emit("job-one", "queued", "pending", "已接收", 0)
        await runtime.emit("job-one", "content_resolving", "running", "读取内容", 8)
        events = await runtime.events.read("job-one", 0, timeout=0.01)
        assert [event.sequence for event in events] == [1, 2]

    asyncio.run(scenario())


def test_mobile_card_uses_neutral_user_copy() -> None:
    result = SimpleNamespace(
        verification={
            "overall_verdict": "误导",
            "conclusion": "标题省略了关键时间范围。",
            "evidence_selected_count": 3,
            "evidence_used": [{"title": "原始公告", "url": "https://example.com"}],
            "uncertainties": [],
        },
        full_pipeline_milliseconds=12_300,
    )
    card = build_mobile_card("job-one", result, utc_now())
    assert card.headline == "内容可能造成误导"
    assert card.evidence_count == 3
    assert card.elapsed_ms == 12_300


def test_sql_job_store_persists_status(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = SqlJobStore(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
        await store.initialize()
        job = JobView(
            job_id="job-sql",
            device_id="device-sql",
            client_request_id="request-sql-1",
            source=JobSource(value="https://example.com/video"),
        )
        await store.create(job)
        updated = await store.update("job-sql", status="running", progress_hint=22)
        assert updated.status == "running"
        assert (await store.get("job-sql")).progress_hint == 22
        await store.engine.dispose()

    asyncio.run(scenario())


def test_create_job_api_returns_async_contract(monkeypatch) -> None:
    from app.jobs import api as jobs_api
    from app.main import app

    job = JobView(
        job_id="job-api",
        device_id="phone-one",
        client_request_id="request-api-1",
        source=JobSource(value="https://example.com/video"),
    )

    async def fake_create(_request, _device_id):
        return job, False

    monkeypatch.setattr(jobs_api.runtime, "create", fake_create)
    response = TestClient(app).post(
        "/v1/jobs",
        headers={"X-Device-Id": "phone-one"},
        json={
            "source": {"type": "shared_url", "value": "https://example.com/video"},
            "client_request_id": "request-api-1",
        },
    )
    assert response.status_code == 202
    assert response.json()["event_url"] == "/v1/jobs/job-api/events"
