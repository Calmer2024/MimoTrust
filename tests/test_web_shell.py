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
        "topic",
        "overallVerdict",
        "sharingAdvice",
        "claimChecks",
        "narrativeAnalysis",
        "evidenceGaps",
        "evidenceUsed",
        "evidenceReviewedCount",
        "evidenceSelectedCount",
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
    for field in ("claimDetails", "sharingAdvice", "narrativeAnalysis", "evidenceGaps", "keyEvidence"):
        assert f"job.{field}" in ui
    assert "version = 7" in database
    assert "MIGRATION_1_2" in database
    assert "MIGRATION_2_3" in database
    assert "MIGRATION_3_4" in database
    assert "MIGRATION_4_5" in database
    assert "MIGRATION_5_6" in database
    assert "MIGRATION_6_7" in database
    assert "extractedMetadata" in database
    for migration in (
        "MIGRATION_1_2",
        "MIGRATION_2_3",
        "MIGRATION_3_4",
        "MIGRATION_4_5",
        "MIGRATION_5_6",
        "MIGRATION_6_7",
    ):
        assert f"MimoDatabase.{migration}" in application
    for field in ("thinkingText", "reportDraft", "reportJson"):
        assert field in entity
        assert field in database
    assert "模型思考过程" in ui
    assert "DetailTabContent(job, report, selectedTab, active)" in ui
    assert "核验摘要" in ui
    assert "信息提示" in ui
    assert "证据充分度" in ui
    assert "逐项核验" in ui
    assert "ReportHero" in ui
    assert "ClaimReportCard" in ui
    assert "EvidenceLink" in ui
    assert "LocalUriHandler" in ui
    assert "processArtifacts" in entity
    assert "ProcessArtifacts" in ui
    assert "查看全部" in ui
    assert 'getSharedPreferences("mimo-ui"' in ui
    assert 'putString("verification-mode"' in ui
    assert "VerificationModeMenu" in ui
    assert "keyboardController?.hide()" in ui
    assert "focusManager.clearFocus(force = true)" in ui
    assert "streamingOverallText(job.reportDraft)" in ui
    assert 'Icon(Lucide.ChevronDown, "滑到最底"' in ui
    assert "detectHorizontalDragGestures" in ui
    assert "detectVerticalDragGestures" in ui
    assert 'Summary("结论"), Claims("逐项核验"), Evidence("依据"), Process("过程")' in ui
    assert "ExpandableClaimReportCard" in ui


def test_floating_ball_is_opaque_bouncy_and_cancellable() -> None:
    root = Path("android/app/src/main/java/com/mimotrust/xiaozhen")
    service = (root / "overlay/FloatingBallService.kt").read_text(encoding="utf-8")
    api = (root / "data/remote/MimoApi.kt").read_text(encoding="utf-8")
    repository = (root / "data/JobRepository.kt").read_text(encoding="utf-8")

    assert 'ValueAnimator.ofFloat(0f, 1f, 0f)' in service
    assert 'duration = 600L' in service
    assert 'repeatCount = 4' in service
    assert 'if (!cancelled && state == FloatingBallState.Attention)' in service
    assert 'setState(FloatingBallState.Idle, 0)' in service
    assert 'alpha = 1f' in service
    assert 'ValueAnimator.ofFloat(1f, .38f, 1f)' not in service
    assert "snapToNearestBoundary" in service
    assert "OvershootInterpolator" in service
    assert "playCollisionEffect" in service
    assert "drawFittedText" in service
    assert "vibrateAttention" in service
    assert "handleBallClick" in service
    assert "cancelVerification" in service
    assert 'FloatingBallState.Cancelling' in service
    assert '@POST("v1/jobs/{jobId}/cancel")' in api
    assert "suspend fun cancelJob(jobId: String)" in repository


def test_sandbox_articles_and_galleries_flow_into_multimodal_analysis() -> None:
    root = Path("android/app/src/main/java/com/mimotrust/xiaozhen")
    contract = (root / "overlay/ControlledContentContract.kt").read_text(encoding="utf-8")
    receiver = (root / "overlay/ControlledContentReceiver.kt").read_text(encoding="utf-8")
    worker = Path("app/jobs/worker.py").read_text(encoding="utf-8")
    ui = (root / "ui/MimoTrustApp.kt").read_text(encoding="utf-8")

    for content_type in ("article", "rich_article", "image_gallery"):
        assert f'"{content_type}"' in contract
    assert 'CONTROLLED_CONTENT_KIND = "mimotrust_controlled_content"' in receiver
    assert 'mimeType.startsWith("image/")' in receiver
    assert 'mimeType.startsWith("text/")' in receiver
    assert 'sourcePlatformHint = input.platformHint' in receiver
    assert 'job.source.platform_hint == "mimotrust_sandbox"' in worker
    assert "analyze_controlled_content(job.source.value)" in worker
    assert "hashlib.sha256(data).hexdigest()" in worker
    assert "analyze_upload_bundle(title" in worker
    assert "ResultMascot(verdict, failed = false, size = 104.dp)" in ui
    assert "Spacer(Modifier.width(10.dp))" in ui
