from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sandbox.content_admin.drafts import DraftRepository
from sandbox.content_admin.manifest_builder import (
    ContentValidationError,
    build_manifest,
    normalize_draft,
)
from sandbox.content_admin.publisher import ContentPublisher
from sandbox.content_admin.server import create_server
from sandbox.content_admin.storage import FakeStorage
from sandbox.tools.validate_contracts import validate_manifest


SHA_A = "a" * 64
SHA_B = "b" * 64


def base_request(content_type: str, assets: list[dict], blocks=None) -> dict:
    return {
        "content_type": content_type,
        "content_id": f"{content_type.replace('_', '-')}-test",
        "title": "Test content",
        "author": "Test author",
        "published_at": "2026-08-02T10:00:00+08:00",
        "canonical_url": f"https://sandbox.example.test/content/{content_type}",
        "assets": assets,
        "blocks": blocks or [],
        "display_metrics": {"like_count": 1, "comment_count": 2, "share_count": 3},
    }


def asset(asset_id: str, role: str, mime_type: str, order: int) -> dict:
    return {
        "asset_id": asset_id,
        "role": role,
        "file_name": f"{asset_id}.bin",
        "mime_type": mime_type,
        "order": order,
    }


def stored(descriptor: dict, digest: str) -> dict:
    return {
        "asset_id": descriptor["asset_id"],
        "mime_type": descriptor["mime_type"],
        "sha256": digest,
        "size_bytes": 123,
        "source_url": f"https://assets.example.test/{descriptor['asset_id']}",
        "storage": {
            "provider": "aliyun_oss",
            "object_key": f"sandbox-content/{descriptor['asset_id']}",
            "bucket": "test-bucket",
            "endpoint": "oss-cn-beijing.aliyuncs.com",
        },
    }


class ManifestBuilderTests(unittest.TestCase):
    def assert_manifest(self, request: dict, expected_hash: str | None = None):
        draft = normalize_draft(request)
        uploaded = [stored(item, SHA_A if index == 0 else SHA_B) for index, item in enumerate(draft["assets"])]
        manifest = build_manifest(draft, "v1", uploaded)
        validate_manifest(manifest, "test")
        self.assertEqual(request["content_type"], manifest["content"]["content_type"])
        if expected_hash:
            self.assertEqual(expected_hash, manifest["content"]["content_hash"])
        return manifest

    def test_video_manifest(self):
        request = base_request("video", [
            asset("video-main", "analysis", "video/mp4", 0),
            asset("video-cover", "cover", "image/png", 1),
        ])
        self.assert_manifest(request, SHA_A)

    def test_audio_manifest(self):
        request = base_request("audio", [asset("audio-main", "analysis", "audio/mpeg", 0)])
        self.assert_manifest(request, SHA_A)

    def test_article_manifest(self):
        request = base_request("article", [asset("article-body", "analysis", "text/plain", 0)])
        manifest = self.assert_manifest(request, SHA_A)
        self.assertEqual("article-body", manifest["content"]["body_asset_id"])

    def test_rich_article_manifest_has_deterministic_composite_hash(self):
        assets = [asset("image-001", "analysis", "image/png", 0)]
        blocks = [
            {"block_type": "text", "text": "Paragraph"},
            {"block_type": "image", "asset_id": "image-001"},
        ]
        request = base_request("rich_article", assets, blocks)
        first = self.assert_manifest(request)
        second = self.assert_manifest(request)
        self.assertEqual(first["content"]["content_hash"], second["content"]["content_hash"])
        self.assertEqual(blocks[0]["text"], first["content"]["blocks"][0]["text"])

    def test_gallery_manifest_preserves_order(self):
        assets = [
            asset("image-001", "analysis", "image/png", 0),
            asset("image-002", "analysis", "image/jpeg", 1),
        ]
        manifest = self.assert_manifest(base_request("image_gallery", assets))
        self.assertEqual(["image-001", "image-002"], manifest["content"]["asset_order"])

    def test_duplicate_rich_article_image_reference_is_rejected(self):
        assets = [asset("image-001", "analysis", "image/png", 0)]
        blocks = [
            {"block_type": "image", "asset_id": "image-001"},
            {"block_type": "image", "asset_id": "image-001"},
        ]
        with self.assertRaises(ContentValidationError):
            normalize_draft(base_request("rich_article", assets, blocks))


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.registry_path = self.root / "registry.json"
        self.registry_path.write_text(
            json.dumps({
                "registry_version": "1.0",
                "provider_id": "mimotrust_sandbox",
                "updated_at": "2026-08-02T00:00:00Z",
                "contents": [],
            }),
            encoding="utf-8",
        )
        self.storage = FakeStorage()
        self.drafts = DraftRepository(self.root / "drafts", self.registry_path, 1024 * 1024)
        self.publisher = ContentPublisher(self.drafts, self.registry_path, self.storage)

    def tearDown(self):
        self.temporary.cleanup()

    def create_article(self):
        request = base_request(
            "article",
            [asset("article-body", "analysis", "text/plain", 0)],
        )
        return self.drafts.create(request)

    def test_article_upload_preview_and_publish(self):
        draft = self.create_article()
        body = "line one\r\nline two\r\n".encode()
        uploaded = self.drafts.receive(
            draft["draft_id"], "article-body", io.BytesIO(body), len(body)
        )
        self.assertEqual("text/plain", uploaded["mime_type"])
        preview = self.publisher.preview(draft["draft_id"])
        self.assertEqual(uploaded["sha256"], preview["content"]["content_hash"])
        result = self.publisher.publish(draft["draft_id"])
        self.assertEqual("v1", result["content_version"])
        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.assertEqual(1, len(registry["contents"]))
        self.assertEqual(b"line one\nline two\n", self.storage.uploads[0][1])

    def test_incomplete_draft_is_not_published(self):
        draft = self.create_article()
        with self.assertRaises(ContentValidationError):
            self.publisher.publish(draft["draft_id"])
        self.assertEqual([], json.loads(self.registry_path.read_text())["contents"])


class AdminHttpTests(PublishingTests):
    def setUp(self):
        super().setUp()
        self.token = "t" * 32
        self.server = create_server(
            "127.0.0.1",
            0,
            self.registry_path,
            self.root / "http-drafts",
            self.token,
            "https://sandbox.example.test/content",
            max_asset_bytes=1024 * 1024,
            storage=self.storage,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def test_admin_api_requires_token(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base_url + "/admin/v1/config", timeout=2)
        self.assertEqual(401, caught.exception.code)
        request = Request(
            self.base_url + "/admin/v1/config",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urlopen(request, timeout=2) as response:
            body = json.load(response)
        self.assertEqual("test-bucket", body["bucket"])

    def test_static_admin_page_is_available(self):
        with urlopen(self.base_url + "/admin", timeout=2) as response:
            page = response.read().decode("utf-8")
        self.assertIn("sandbox", page)
        self.assertIn("Manifest 1.0", page)

    def test_article_can_be_published_through_http_api(self):
        draft_request = base_request(
            "article",
            [asset("article-body", "analysis", "text/plain", 0)],
        )
        create = Request(
            self.base_url + "/admin/v1/drafts",
            data=json.dumps(draft_request).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(create, timeout=2) as response:
            draft = json.load(response)
        body = "normalized article\r\n".encode("utf-8")
        upload = Request(
            self.base_url + f"/admin/v1/drafts/{draft['draft_id']}/assets/article-body",
            data=body,
            method="PUT",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urlopen(upload, timeout=2) as response:
            self.assertEqual("text/plain", json.load(response)["mime_type"])
        preview = Request(
            self.base_url + f"/admin/v1/drafts/{draft['draft_id']}/preview",
            data=b"",
            method="POST",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urlopen(preview, timeout=2) as response:
            self.assertEqual("article", json.load(response)["manifest"]["content"]["content_type"])
        publish = Request(
            self.base_url + f"/admin/v1/drafts/{draft['draft_id']}/publish",
            data=b"",
            method="POST",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urlopen(publish, timeout=2) as response:
            self.assertEqual("v1", json.load(response)["content_version"])


if __name__ == "__main__":
    unittest.main()
