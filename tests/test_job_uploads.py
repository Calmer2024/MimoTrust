import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from app.jobs import api as jobs_api
from app.jobs.models import JobView
from app.jobs.uploads import (
    UploadBundleError,
    cleanup_upload_bundle,
    open_upload_bundle,
)
from app.main import app


def test_mobile_upload_job_stages_text_and_multiple_files(
    monkeypatch, tmp_path
) -> None:
    captured = {}
    monkeypatch.setattr(
        "app.jobs.uploads.settings",
        SimpleNamespace(job_upload_dir=str(tmp_path / "uploads")),
    )

    async def fake_create(request, device_id):
        captured["request"] = request
        captured["device_id"] = device_id
        return (
            JobView(
                job_id="job-upload-1",
                device_id=device_id,
                client_request_id=request.client_request_id,
                source=request.source,
                mode=request.mode,
                verification_mode=request.verification_mode,
            ),
            False,
        )

    monkeypatch.setattr(jobs_api.runtime, "create", fake_create)
    response = TestClient(app).post(
        "/v1/jobs/upload",
        headers={"X-Device-Id": "phone-1"},
        data={
            "title": "混合材料",
            "text": "请结合图片和视频核验这段说明。",
            "mode": "auto",
            "verification_mode": "quality",
            "client_request_id": "request-upload-1",
        },
        files=[
            ("files", ("first.png", b"image-one", "image/png")),
            ("files", ("clip.mp4", b"video-one", "video/mp4")),
        ],
    )

    assert response.status_code == 202
    request = captured["request"]
    assert captured["device_id"] == "phone-1"
    assert request.source.type == "upload_bundle"
    assert request.source.platform_hint == "user_upload"
    assert request.verification_mode == "quality"

    async def read_bundle():
        async with open_upload_bundle(request.source.value) as bundle:
            return (
                bundle.title,
                bundle.text,
                [upload.filename for upload in bundle.files],
                [await upload.read() for upload in bundle.files],
            )

    title, text, names, payloads = asyncio.run(read_bundle())
    assert title == "混合材料"
    assert text == "请结合图片和视频核验这段说明。"
    assert names == ["first.png", "clip.mp4"]
    assert payloads == [b"image-one", b"video-one"]
    cleanup_upload_bundle(request.source.value)
    assert not (tmp_path / "uploads" / request.source.value).exists()


def test_upload_bundle_rejects_non_uuid_identifier() -> None:
    with pytest.raises(UploadBundleError):
        cleanup_upload_bundle("../outside")


def test_upload_file_content_type_is_preserved() -> None:
    upload = UploadFile(
        file=BytesIO(b"sample"),
        filename="sample.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )
    assert upload.content_type == "image/jpeg"
