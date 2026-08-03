from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path

from sandbox.content_gateway.server import (
    AUDIENCE,
    DEFAULT_REGISTRY,
    ContentStore,
    GatewayError,
    GrantService,
    create_server,
)


class MutableClock:
    def __init__(self):
        self.value = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


def grant_request(**overrides):
    value = {
        "content_id": "video-001",
        "content_version": "v1",
        "audience": AUDIENCE,
        "scopes": ["manifest:read", "asset:read"],
    }
    value.update(overrides)
    return value


def exchange_request(grant_code: str, **overrides):
    value = {
        "grant_code": grant_code,
        "content_id": "video-001",
        "content_version": "v1",
        "audience": AUDIENCE,
    }
    value.update(overrides)
    return value


class GrantServiceTests(unittest.TestCase):
    def setUp(self):
        self.clock = MutableClock()
        self.service = GrantService(ContentStore(DEFAULT_REGISTRY), ttl_seconds=180, clock=self.clock)

    def issue(self):
        return self.service.issue(grant_request(), "http://127.0.0.1:8787/v1/grants/exchange")

    def test_grant_exchanges_once(self):
        issued = self.issue()
        response = self.service.exchange(exchange_request(issued["grant_code"]))
        self.assertEqual("video-001", response["manifest"]["content"]["content_id"])
        with self.assertRaises(GatewayError) as caught:
            self.service.exchange(exchange_request(issued["grant_code"]))
        self.assertEqual("GRANT_REPLAYED", caught.exception.code)

    def test_expired_grant_is_rejected(self):
        issued = self.issue()
        self.clock.value += timedelta(seconds=180)
        with self.assertRaises(GatewayError) as caught:
            self.service.exchange(exchange_request(issued["grant_code"]))
        self.assertEqual("GRANT_EXPIRED", caught.exception.code)

    def test_wrong_audience_does_not_consume_grant(self):
        issued = self.issue()
        with self.assertRaises(GatewayError) as caught:
            self.service.exchange(exchange_request(issued["grant_code"], audience="wrong"))
        self.assertEqual("AUDIENCE_MISMATCH", caught.exception.code)
        self.service.exchange(exchange_request(issued["grant_code"]))

    def test_content_mismatch_does_not_consume_grant(self):
        issued = self.issue()
        with self.assertRaises(GatewayError) as caught:
            self.service.exchange(exchange_request(issued["grant_code"], content_id="video-999"))
        self.assertEqual("CONTENT_MISMATCH", caught.exception.code)
        self.service.exchange(exchange_request(issued["grant_code"]))

    def test_wrong_issue_audience_is_rejected(self):
        with self.assertRaises(GatewayError) as caught:
            self.service.issue(grant_request(audience="wrong"), "http://example.test/exchange")
        self.assertEqual("AUDIENCE_MISMATCH", caught.exception.code)

    def test_unknown_request_field_is_rejected(self):
        with self.assertRaises(GatewayError) as caught:
            self.service.issue(
                grant_request(unexpected=True),
                "http://example.test/exchange",
            )
        self.assertEqual("INVALID_REQUEST", caught.exception.code)

    def test_partial_scopes_are_rejected(self):
        with self.assertRaises(GatewayError) as caught:
            self.service.issue(
                grant_request(scopes=["manifest:read"]),
                "http://example.test/exchange",
            )
        self.assertEqual("INVALID_REQUEST", caught.exception.code)

    def test_all_three_registered_videos_can_issue_grants(self):
        for content_id in ("video-001", "video-002", "video-003"):
            issued = self.service.issue(
                grant_request(content_id=content_id),
                "http://127.0.0.1:8787/v1/grants/exchange",
            )
            self.assertEqual(content_id, issued["content_ref"]["content_id"])


class ContentStoreReloadTests(unittest.TestCase):
    def test_registry_changes_are_loaded_without_restarting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifests = root / "manifests"
            manifests.mkdir()
            source_manifest = DEFAULT_REGISTRY.parent / "manifests" / "video-001.v1.json"
            (manifests / "video-001.v1.json").write_bytes(source_manifest.read_bytes())
            registry = {
                "registry_version": "1.0",
                "provider_id": "mimotrust_sandbox",
                "updated_at": "2026-08-02T00:00:00Z",
                "contents": [],
            }
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            store = ContentStore(registry_path)
            self.assertEqual(0, store.content_count)

            registry["contents"].append(
                {
                    "content_id": "video-001",
                    "content_version": "v1",
                    "content_type": "video",
                    "status": "active",
                    "display_order": 0,
                    "manifest_path": "manifests/video-001.v1.json",
                    "display_metrics": {"like_count": 0, "comment_count": 0, "share_count": 0},
                }
            )
            registry["updated_at"] = "2026-08-02T00:00:01Z"
            registry_path.write_text(json.dumps(registry) + "\n", encoding="utf-8")
            self.assertEqual(1, store.content_count)
            self.assertEqual("video-001", store.get_manifest("video-001", "v1")["content"]["content_id"])


class HttpGatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(host="127.0.0.1", port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = cls.server.public_base_url

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request_json(self, path, method="GET", body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=3) as response:
            return response.status, json.load(response)

    def test_health_issue_exchange_and_replay(self):
        status, health = self.request_json("/health")
        self.assertEqual(HTTPStatus.OK, status)
        self.assertEqual(3, health["content_count"])
        status, issued = self.request_json("/v1/context-grants", "POST", grant_request())
        self.assertEqual(HTTPStatus.CREATED, status)
        status, exchanged = self.request_json(
            "/v1/grants/exchange", "POST", exchange_request(issued["grant_code"])
        )
        self.assertEqual(HTTPStatus.OK, status)
        self.assertEqual("1.0", exchanged["manifest"]["manifest_version"])
        with self.assertRaises(HTTPError) as caught:
            self.request_json(
                "/v1/grants/exchange", "POST", exchange_request(issued["grant_code"])
            )
        self.assertEqual(HTTPStatus.GONE, caught.exception.code)
        error = json.load(caught.exception)
        self.assertEqual("GRANT_REPLAYED", error["error"]["code"])

    def test_feed_is_ordered_and_materializes_local_asset_urls(self):
        status, feed = self.request_json("/v1/feed")

        self.assertEqual(HTTPStatus.OK, status)
        self.assertEqual("1.0", feed["registry_version"])
        self.assertEqual("mimotrust_sandbox", feed["provider_id"])
        self.assertEqual(
            ["video-001", "video-002", "video-003"],
            [item["content_id"] for item in feed["contents"]],
        )
        first_assets = feed["contents"][0]["manifest"]["assets"]
        cover = next(asset for asset in first_assets if asset["role"] == "cover")
        self.assertEqual(
            f"{self.base_url}/assets/images/video-001-cover.png",
            cover["source_url"],
        )

    def test_exchange_materializes_local_asset_urls(self):
        _, issued = self.request_json("/v1/context-grants", "POST", grant_request())
        _, exchanged = self.request_json(
            "/v1/grants/exchange", "POST", exchange_request(issued["grant_code"])
        )
        cover = next(
            asset
            for asset in exchanged["manifest"]["assets"]
            if asset["role"] == "cover"
        )
        self.assertEqual(
            f"{self.base_url}/assets/images/video-001-cover.png",
            cover["source_url"],
        )

    def test_local_cover_asset_is_served(self):
        with urlopen(self.base_url + "/assets/images/video-001-cover.png", timeout=3) as response:
            self.assertEqual(HTTPStatus.OK, response.status)
            self.assertEqual(634670, int(response.headers["Content-Length"]))


if __name__ == "__main__":
    unittest.main()
