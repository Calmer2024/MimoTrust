from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_index_prevents_stale_frontend_bundle() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "/static/app.css?v=" in response.text
    assert "/static/app.js?v=" in response.text


def test_completed_verification_is_part_of_video_response(monkeypatch) -> None:
    payload = {
        "protocol_version": "compact-claims-v2",
        "request_id": "request-one",
        "cached": True,
        "strategy": "metadata",
        "metadata": {
            "platform": "抖音",
            "title": "测试视频",
            "webpage_url": "https://www.douyin.com/video/7655319255663070499",
        },
        "summary": "测试摘要",
        "coverage_note": "测试覆盖",
        "structured_data": {
            "主题": "测试主题",
            "主张": [
                {"文本": "这是一条用于回归测试的完整中文主张", "表达": "直接"}
            ],
        },
        "verification": {
            "status": "completed",
            "overall_verdict": "属实",
            "claim_checks": [{"claim_id": "A1", "verdict": "属实"}],
        },
    }
    monkeypatch.setattr(
        "app.main.cache.list",
        lambda _limit: [
            {
                "cache_key": "a" * 64,
                "created_at": "2026-08-01T12:00:00",
                "expired": False,
                "result": payload,
            }
        ],
    )

    response = TestClient(app).get("/api/videos")

    assert response.status_code == 200
    verification = response.json()["items"][0]["result"]["verification"]
    assert verification["status"] == "completed"
    assert verification["claim_checks"][0]["verdict"] == "属实"


def test_full_pipeline_details_have_one_unified_process_view() -> None:
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")

    assert 'id="full-pipeline-summary"' in html
    assert 'id="trust-audit-body"' in html
    assert html.index('id="trust-audit-body"') > html.index('id="view-process"')
    assert 'id="llm-structured-input"' in html
    assert 'fetch("/api/analyze/stream"' in script
    assert 'verification_mode: $("verification-mode").value' in script
    assert 'id="narrative-analysis"' in html
    assert 'id="evidence-gaps"' in html
    assert 'id="report-json"' in html
    assert "data.full_source_text" in script
    assert 'id="thumbnail-placeholder"' in html
    assert "showThumbnail" in script
    assert "thumbnail.onerror" in script
    css = Path("app/static/app.css").read_text(encoding="utf-8")
    assert "object-fit: contain" in css
    assert "filter: saturate" not in css


def test_web_shell_uses_one_input_for_links_and_text() -> None:
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")

    assert 'id="url" type="text"' in html
    assert 'autocomplete="off"' in html
    assert "直接输入需要核验的文字" in html
    assert 'id="upload-fields"' not in html
    assert 'id="upload-files"' not in html
    assert 'id="upload-title"' not in html
    assert 'id="upload-text"' not in html
    assert 'fetch("/api/analyze/upload/stream"' in script
    assert '<option value="upload">' not in html
    assert "selectInputRoute" in script
    assert 'route.kind === "text"' in script
    assert '$("upload-' not in script


def test_android_consumes_and_displays_complete_report_sections() -> None:
    root = Path("android/app/src/main/java/com/mimotrust/xiaozhen")
    dto = (root / "data/remote/Dtos.kt").read_text(encoding="utf-8")
    repository = (root / "data/JobRepository.kt").read_text(encoding="utf-8")
    entity = (root / "data/local/JobEntity.kt").read_text(encoding="utf-8")
    database = (root / "data/local/MimoDatabase.kt").read_text(encoding="utf-8")
    application = (root / "MimoTrustApplication.kt").read_text(encoding="utf-8")
    ui = (root / "ui/MimoTrustApp.kt").read_text(encoding="utf-8")

    for field in (
        "sharingAdvice",
        "claimChecks",
        "narrativeAnalysis",
        "evidenceGaps",
        "evidenceUsed",
        "reportMarkdown",
    ):
        assert field in dto
    for field in (
        "claimDetails",
        "sharingAdvice",
        "narrativeAnalysis",
        "evidenceGaps",
        "uncertaintyNote",
        "keyEvidence",
    ):
        assert field in repository
        assert field in entity
        assert f"job.{field}" in ui
    assert "version = 4" in database
    assert "MIGRATION_1_2" in database
    assert "MIGRATION_2_3" in database
    assert "MIGRATION_3_4" in database
    assert "extractedMetadata" in database
    for migration in ("MIGRATION_1_2", "MIGRATION_2_3", "MIGRATION_3_4"):
        assert f"MimoDatabase.{migration}" in application
