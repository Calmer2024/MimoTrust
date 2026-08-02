from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace
from pathlib import Path

from fastapi.testclient import TestClient

from app.jobs.models import CreateJobRequest, JobSource, JobView
from app.jobs.runtime import JobRuntime
from app.jobs.store import SqlJobStore
from app.jobs.worker import build_mobile_card, should_retry_with_visual, stream_event_kind
from app.jobs.models import utc_now
from app.jobs import artifacts as artifacts_module


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
        await runtime.emit(
            "job-one",
            "report_generating",
            "running",
            "正在思考",
            90,
            event_kind="thinking_delta",
            payload={"text": "核对来源"},
        )
        events = await runtime.events.read("job-one", 0, timeout=0.01)
        assert [event.sequence for event in events] == [1, 2, 3]
        assert events[-1].event_kind == "thinking_delta"
        assert events[-1].payload == {"text": "核对来源"}

    asyncio.run(scenario())


def test_job_event_carries_extracted_content_metadata() -> None:
    async def scenario() -> None:
        runtime = JobRuntime("memory")
        await runtime.store.create(JobView(
            job_id="job-metadata",
            device_id="device-one",
            client_request_id="request-meta-1",
            source=JobSource(value="https://example.com/video"),
        ))
        metadata = {
            "title": "示例视频",
            "platform": "哔哩哔哩",
            "duration_seconds": 92.4,
            "topic": "公共事件",
            "claim_count": 3,
        }

        await runtime.emit(
            "job-metadata",
            "claim_structuring",
            "running",
            "已识别 3 条待核验主张",
            42,
            content_metadata=metadata,
        )

        event = (await runtime.events.read("job-metadata", 0, timeout=0.01))[0]
        assert event.content_metadata == metadata

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


def test_mobile_card_explains_when_content_has_no_verifiable_claims() -> None:
    result = SimpleNamespace(
        verification={
            "status": "skipped",
            "message": "当前内容没有需要外部事实核验的现实世界主张。",
        },
        structured_data=SimpleNamespace(claims=[]),
        full_pipeline_milliseconds=11_080,
    )

    card = build_mobile_card("job-empty", result, utc_now())

    assert card.verdict == "无需核验"
    assert card.headline == "未识别到可核验主张"
    assert card.conclusion == "当前内容没有需要外部事实核验的现实世界主张。"


def test_empty_claims_without_visual_analysis_trigger_visual_retry() -> None:
    result = SimpleNamespace(
        structured_data=SimpleNamespace(claims=[]),
        coverage=SimpleNamespace(visual_analyzed=False),
    )
    assert should_retry_with_visual(result) is True

    result.coverage.visual_analyzed = True
    assert should_retry_with_visual(result) is False

    result.structured_data.claims = [SimpleNamespace(text="一项可核验主张")]
    assert should_retry_with_visual(result) is False


def test_android_routes_plain_text_to_agent_context() -> None:
    repository = Path(
        "android/app/src/main/java/com/mimotrust/xiaozhen/data/JobRepository.kt"
    ).read_text(encoding="utf-8")
    worker = Path("app/jobs/worker.py").read_text(encoding="utf-8")

    assert '"shared_url" else "agent_context"' in repository
    assert 'job.source.type == "agent_context"' in worker
    assert "analyze_upload_bundle" in worker


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


def test_sql_job_store_upgrades_existing_table_with_verification_mode(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy-jobs.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE verification_jobs (job_id VARCHAR(36) PRIMARY KEY)"
        )

    async def scenario() -> None:
        store = SqlJobStore(f"sqlite+aiosqlite:///{database_path}")
        await store.initialize()
        await store.engine.dispose()

    asyncio.run(scenario())

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(verification_jobs)")
        }
    assert "verification_mode" in columns


def test_create_job_api_returns_async_contract(monkeypatch) -> None:
    from app.jobs import api as jobs_api
    from app.main import app

    job = JobView(
        job_id="job-api",
        device_id="phone-one",
        client_request_id="request-api-1",
        source=JobSource(value="https://example.com/video"),
    )

    captured = {}

    async def fake_create(_request, _device_id):
        captured["verification_mode"] = _request.verification_mode
        return job, False

    monkeypatch.setattr(jobs_api.runtime, "create", fake_create)
    response = TestClient(app).post(
        "/v1/jobs",
        headers={"X-Device-Id": "phone-one"},
        json={
            "source": {"type": "shared_url", "value": "https://example.com/video"},
            "verification_mode": "quality",
            "client_request_id": "request-api-1",
        },
    )
    assert response.status_code == 202
    assert response.json()["event_url"] == "/v1/jobs/job-api/events"
    assert captured["verification_mode"] == "quality"

def test_all_thinking_stages_use_the_standard_sse_event_kind() -> None:
    assert stream_event_kind("m2_thinking") == "thinking_delta"
    assert stream_event_kind("thinking") == "thinking_delta"
    assert stream_event_kind("report") == "report_delta"


def test_artifact_upload_timeout_does_not_block_job_completion(monkeypatch) -> None:
    async def never_finishes(*_args, **_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(artifacts_module.asyncio, "to_thread", never_finishes)
    monkeypatch.setattr(
        artifacts_module,
        "settings",
        SimpleNamespace(
            s3_endpoint_url="http://unreachable.invalid",
            s3_access_key="test",
            s3_secret_key="test",
            s3_region="us-east-1",
            s3_bucket="test",
            s3_upload_timeout_seconds=0.01,
        ),
    )

    result = asyncio.run(artifacts_module.store_job_artifacts("job-timeout", {}, "report"))

    assert result is None
