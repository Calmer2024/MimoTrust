from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
SANDBOX_ACTIVITY = REPOSITORY_ROOT / "sandbox/mimotrust_controlled_content/android/app/src/main/kotlin/com/mimotrust/controlledcontent/MainActivity.kt"
GUARDIAN_CONTRACT = REPOSITORY_ROOT / "guardian/android/app/src/main/java/com/mimotrust/xiaozhen/overlay/ControlledContentContract.kt"
GUARDIAN_RECEIVER = REPOSITORY_ROOT / "guardian/android/app/src/main/java/com/mimotrust/xiaozhen/overlay/ControlledContentReceiver.kt"
GUARDIAN_WORKER = REPOSITORY_ROOT / "guardian/android/app/src/main/java/com/mimotrust/xiaozhen/overlay/ControlledContentEnqueueWorker.kt"
GUARDIAN_REPOSITORY = REPOSITORY_ROOT / "guardian/android/app/src/main/java/com/mimotrust/xiaozhen/data/JobRepository.kt"
ANDROID_BUILD = REPOSITORY_ROOT / "guardian/android/app/build.gradle.kts"


def test_context_22_identifiers_match_across_apps() -> None:
    sandbox = SANDBOX_ACTIVITY.read_text(encoding="utf-8")
    guardian = GUARDIAN_CONTRACT.read_text(encoding="utf-8")

    for value in (
        "com.mimotrust.intent.action.REQUEST_CONTENT_CONTEXT",
        "com.mimotrust.intent.action.CONTENT_CONTEXT",
        "com.mimotrust.controlledcontent",
        "com.mimotrust.guardian",
        "request_id",
        "payload",
    ):
        assert value in sandbox or value in guardian
    assert 'SCHEMA_VERSION = "2.2"' in guardian
    assert 'TRIGGER_GUARDIAN_REQUEST = "guardian_request"' in guardian


def test_guardian_response_is_reliably_enqueued_without_receiver_network_io() -> None:
    receiver = GUARDIAN_RECEIVER.read_text(encoding="utf-8")
    worker = GUARDIAN_WORKER.read_text(encoding="utf-8")
    repository = GUARDIAN_REPOSITORY.read_text(encoding="utf-8")

    assert "ControlledContentEnqueueWorker.enqueue" in receiver
    assert "goAsync" not in receiver
    assert "OkHttp" not in receiver
    assert "enqueueUniqueWork" in worker
    assert "content-context-$eventId" in worker
    assert "createControlledContentJob(payload, eventId)" in worker
    assert "submitContentContext" in repository


def test_guardian_accepts_all_frozen_content_types() -> None:
    contract = GUARDIAN_CONTRACT.read_text(encoding="utf-8")

    for content_type in ("video", "audio", "article", "rich_article", "image_gallery"):
        assert f'"{content_type}"' in contract
    assert 'contentType !in SUPPORTED_CONTENT_TYPES' in contract
    assert "validViewState(contentType" in contract
    assert 'access.length() == 1' in contract


def test_comment_and_share_candidates_do_not_issue_grants() -> None:
    dispatcher = (
        REPOSITORY_ROOT
        / "sandbox/mimotrust_controlled_content/lib/services/context_dispatcher.dart"
    ).read_text(encoding="utf-8")
    model = (
        REPOSITORY_ROOT / "sandbox/mimotrust_controlled_content/lib/models/content_context.dart"
    ).read_text(encoding="utf-8")

    candidate_body = dispatcher.split(
        "Future<ContentContext> dispatchGuardianRequest", 1
    )[0]
    assert "ContentContext.deferred" in candidate_body
    assert "issueGrant" not in candidate_body
    assert "'mode': 'deferred_grant'" in model


def test_android_default_backend_uses_adb_reverse_loopback() -> None:
    build = ANDROID_BUILD.read_text(encoding="utf-8")

    assert '.orElse("http://127.0.0.1:8000/")' in build
    assert '.orElse("http://10.0.2.2:8000/")' not in build
