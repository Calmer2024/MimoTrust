from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SANDBOX_ACTIVITY = ROOT / "sandbox/mimotrust_controlled_content/android/app/src/main/kotlin/com/mimotrust/controlledcontent/MainActivity.kt"
GUARDIAN_CONTRACT = ROOT / "android/app/src/main/java/com/mimotrust/xiaozhen/overlay/ControlledContentContract.kt"
GUARDIAN_RECEIVER = ROOT / "android/app/src/main/java/com/mimotrust/xiaozhen/overlay/ControlledContentReceiver.kt"


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


def test_guardian_response_exchanges_and_verifies_analysis_asset() -> None:
    receiver = GUARDIAN_RECEIVER.read_text(encoding="utf-8")

    for check in (
        'asset.optString("role") == "analysis"',
        'asset.optString("mime_type").startsWith("video/")',
        'asset.optString("sha256") == grant.contentHash',
        "repository.createSharedJob",
    ):
        assert check in receiver


def test_comment_and_share_candidates_do_not_issue_grants() -> None:
    dispatcher = (
        ROOT
        / "sandbox/mimotrust_controlled_content/lib/services/context_dispatcher.dart"
    ).read_text(encoding="utf-8")
    model = (
        ROOT / "sandbox/mimotrust_controlled_content/lib/models/content_context.dart"
    ).read_text(encoding="utf-8")

    candidate_body = dispatcher.split("dispatchGuardianRequest", 1)[0]
    assert "ContentContext.deferred" in candidate_body
    assert "issueGrant" not in candidate_body
    assert "'mode': 'deferred_grant'" in model
