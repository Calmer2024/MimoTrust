#!/usr/bin/env python3
"""Standard-library HTTP gateway for the first MiMoTrust sandbox flow."""

from __future__ import annotations

import argparse
import copy
import json
import logging
import mimetypes
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse


LOGGER = logging.getLogger("MiMoTrustGateway")
PROVIDER_ID = "mimotrust_sandbox"
AUDIENCE = "mimotrust_guardian_backend"
ALLOWED_SCOPES = frozenset({"manifest:read", "asset:read"})
DEFAULT_SCOPES = ("manifest:read", "asset:read")
MAX_REQUEST_BYTES = 32 * 1024
SANDBOX_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = SANDBOX_ROOT / "content_registry" / "registry.json"


class GatewayError(Exception):
    def __init__(self, code: str, message: str, status: HTTPStatus):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class ContentStore:
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path.resolve()
        self.root = self.registry_path.parent
        self._lock = threading.RLock()
        self._registry_signature = (-1, -1, -1)
        self._registry_metadata: dict[str, object] = {}
        self._contents: dict[tuple[str, str], tuple[dict, dict]] = {}
        self._reload_if_changed(force=True)

    def _reload_if_changed(self, force: bool = False) -> None:
        try:
            stat = self.registry_path.stat()
        except OSError as error:
            raise ValueError(f"cannot stat content registry: {self.registry_path}") from error
        signature = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        if not force and signature == self._registry_signature:
            return
        with self._lock:
            if not force and signature == self._registry_signature:
                return
            registry = self._read_json(self.registry_path)
            contents = self._load_contents(registry)
            self._contents = contents
            self._registry_metadata = {
                "registry_version": registry.get("registry_version"),
                "provider_id": registry.get("provider_id"),
                "updated_at": registry.get("updated_at"),
            }
            self._registry_signature = signature

    def _load_contents(self, registry: dict) -> dict[tuple[str, str], tuple[dict, dict]]:
        if registry.get("provider_id") != PROVIDER_ID:
            raise ValueError("registry provider_id does not match the fixed contract")
        contents: dict[tuple[str, str], tuple[dict, dict]] = {}
        for entry in registry.get("contents", []):
            if entry.get("status") != "active":
                continue
            key = (entry["content_id"], entry["content_version"])
            if key in contents:
                raise ValueError(f"duplicate active registry entry: {key}")
            manifest_path = (self.root / entry["manifest_path"]).resolve()
            if self.root not in manifest_path.parents:
                raise ValueError("manifest_path escapes the content registry")
            manifest = self._read_json(manifest_path)
            content = manifest.get("content", {})
            if (content.get("content_id"), content.get("content_version")) != key:
                raise ValueError(f"manifest identity mismatch for {key}")
            if manifest.get("provider", {}).get("provider_id") != PROVIDER_ID:
                raise ValueError(f"manifest provider mismatch for {key}")
            contents[key] = (entry, manifest)
        return contents

    @staticmethod
    def _read_json(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError(f"expected a JSON object: {path}")
        return value

    def get_manifest(self, content_id: str, content_version: str) -> dict:
        self._reload_if_changed()
        with self._lock:
            item = self._contents.get((content_id, content_version))
        if item is None:
            raise GatewayError(
                "CONTENT_UNAVAILABLE",
                "The requested content or version is not active.",
                HTTPStatus.NOT_FOUND,
            )
        return item[1]

    def get_feed(self) -> dict:
        self._reload_if_changed()
        with self._lock:
            items = sorted(
                self._contents.values(),
                key=lambda item: item[0].get("display_order", 1 << 30),
            )
            return {
                **self._registry_metadata,
                "contents": [
                    {
                        "content_id": entry["content_id"],
                        "content_version": entry["content_version"],
                        "content_type": entry["content_type"],
                        "display_order": entry.get("display_order", 1 << 30),
                        "display_metrics": entry.get(
                            "display_metrics",
                            {"like_count": 0, "comment_count": 0, "share_count": 0},
                        ),
                        "manifest": manifest,
                    }
                    for entry, manifest in items
                ],
            }

    @property
    def content_count(self) -> int:
        self._reload_if_changed()
        with self._lock:
            return len(self._contents)

    def resolve_asset(self, relative_path: str) -> Path:
        assets_root = (self.root / "assets").resolve()
        candidate = (assets_root / unquote(relative_path)).resolve()
        if candidate != assets_root and assets_root not in candidate.parents:
            raise GatewayError("ASSET_NOT_FOUND", "Asset not found.", HTTPStatus.NOT_FOUND)
        if not candidate.is_file():
            raise GatewayError("ASSET_NOT_FOUND", "Asset not found.", HTTPStatus.NOT_FOUND)
        return candidate


@dataclass
class GrantRecord:
    grant_id: str
    grant_code: str
    content_id: str
    content_version: str
    audience: str
    scopes: tuple[str, ...]
    expires_at: datetime
    exchanged: bool = False


class GrantService:
    def __init__(
        self,
        store: ContentStore,
        ttl_seconds: int = 180,
        clock: Callable[[], datetime] | None = None,
    ):
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")
        self.store = store
        self.ttl_seconds = ttl_seconds
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._grants: dict[str, GrantRecord] = {}
        self._lock = threading.Lock()

    def issue(self, request: dict, exchange_url: str) -> dict:
        reject_unknown_keys(
            request,
            {"content_id", "content_version", "audience", "scopes"},
        )
        content_id = required_string(request, "content_id")
        content_version = required_string(request, "content_version")
        audience = required_string(request, "audience")
        if audience != AUDIENCE:
            raise GatewayError(
                "AUDIENCE_MISMATCH",
                "The requested audience is not allowed.",
                HTTPStatus.FORBIDDEN,
            )
        requested_scopes = request.get("scopes", list(DEFAULT_SCOPES))
        scopes = validate_scopes(requested_scopes)
        manifest = self.store.get_manifest(content_id, content_version)
        content = manifest["content"]
        now = self.clock()
        record = GrantRecord(
            grant_id=str(uuid.uuid4()),
            grant_code=secrets.token_urlsafe(32),
            content_id=content_id,
            content_version=content_version,
            audience=audience,
            scopes=scopes,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )
        with self._lock:
            self._grants[record.grant_code] = record
        LOGGER.info(
            "CONTENT_GRANT_ISSUED grant_id=%s content_id=%s",
            record.grant_id,
            content_id,
        )
        return {
            "grant_code": record.grant_code,
            "expires_at": isoformat(record.expires_at),
            "audience": record.audience,
            "scopes": list(record.scopes),
            "exchange_url": exchange_url,
            "content_ref": {
                "content_type": content["content_type"],
                "content_id": content["content_id"],
                "content_version": content["content_version"],
                "content_hash": content["content_hash"],
                "canonical_url": content["canonical_url"],
            },
        }

    def exchange(self, request: dict) -> dict:
        reject_unknown_keys(
            request,
            {"grant_code", "audience", "content_id", "content_version"},
        )
        grant_code = required_string(request, "grant_code")
        audience = required_string(request, "audience")
        content_id = required_string(request, "content_id")
        content_version = required_string(request, "content_version")
        with self._lock:
            record = self._grants.get(grant_code)
            if record is None:
                raise GatewayError(
                    "GRANT_INVALID", "The grant code is unknown.", HTTPStatus.NOT_FOUND
                )
            if record.exchanged:
                raise GatewayError(
                    "GRANT_REPLAYED",
                    "The grant has already been exchanged.",
                    HTTPStatus.GONE,
                )
            if self.clock() >= record.expires_at:
                raise GatewayError(
                    "GRANT_EXPIRED", "The grant has expired.", HTTPStatus.GONE
                )
            if audience != record.audience:
                raise GatewayError(
                    "AUDIENCE_MISMATCH",
                    "The audience does not match this grant.",
                    HTTPStatus.FORBIDDEN,
                )
            if (content_id, content_version) != (
                record.content_id,
                record.content_version,
            ):
                raise GatewayError(
                    "CONTENT_MISMATCH",
                    "The content identity does not match this grant.",
                    HTTPStatus.CONFLICT,
                )
            manifest = self.store.get_manifest(content_id, content_version)
            record.exchanged = True
        LOGGER.info(
            "CONTENT_GRANT_EXCHANGED grant_id=%s content_id=%s",
            record.grant_id,
            content_id,
        )
        return {"grant_id": record.grant_id, "manifest": manifest}


def required_string(value: dict, key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise GatewayError(
            "INVALID_REQUEST", f"{key} must be a non-empty string.", HTTPStatus.BAD_REQUEST
        )
    return item


def reject_unknown_keys(value: dict, allowed: set[str]) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise GatewayError(
            "INVALID_REQUEST",
            f"Unsupported request fields: {', '.join(sorted(unknown))}.",
            HTTPStatus.BAD_REQUEST,
        )


def validate_scopes(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(x, str) for x in value):
        raise GatewayError(
            "INVALID_REQUEST", "scopes must be a non-empty string array.", HTTPStatus.BAD_REQUEST
        )
    if len(value) != len(set(value)) or set(value) != ALLOWED_SCOPES:
        raise GatewayError(
            "INVALID_REQUEST",
            "scopes must contain manifest:read and asset:read exactly once.",
            HTTPStatus.BAD_REQUEST,
        )
    return tuple(value)


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def materialize_manifest(manifest: dict, public_base_url: str) -> dict:
    result = copy.deepcopy(manifest)
    for asset in result.get("assets", []):
        source_url = asset.get("source_url")
        if not isinstance(source_url, str):
            continue
        parsed = urlparse(source_url)
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            continue
        asset["source_url"] = f"{public_base_url.rstrip('/')}{parsed.path}"
    return result


def materialize_feed(feed: dict, public_base_url: str) -> dict:
    result = copy.deepcopy(feed)
    for item in result.get("contents", []):
        item["manifest"] = materialize_manifest(item["manifest"], public_base_url)
    return result


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, service, public_base_url: str):
        super().__init__(address, handler)
        self.service: GrantService = service
        self.public_base_url = public_base_url.rstrip("/")


class GatewayHandler(BaseHTTPRequestHandler):
    server: GatewayServer

    def do_GET(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/health":
                self.send_json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "provider_id": PROVIDER_ID,
                        "manifest_version": "1.0",
                        "content_count": self.server.service.store.content_count,
                    },
                )
                return
            if path == "/v1/feed":
                feed = self.server.service.store.get_feed()
                self.send_json(
                    HTTPStatus.OK,
                    materialize_feed(feed, self.server.public_base_url),
                )
                return
            if path.startswith("/assets/"):
                self.send_asset(self.server.service.store.resolve_asset(path[len("/assets/") :]))
                return
            raise GatewayError("NOT_FOUND", "Route not found.", HTTPStatus.NOT_FOUND)
        except GatewayError as error:
            self.send_error_json(error)

    def do_POST(self) -> None:
        try:
            request = self.read_json_body()
            path = urlparse(self.path).path
            if path == "/v1/context-grants":
                response = self.server.service.issue(
                    request,
                    f"{self.server.public_base_url}/v1/grants/exchange",
                )
                self.send_json(HTTPStatus.CREATED, response)
                return
            if path == "/v1/grants/exchange":
                response = self.server.service.exchange(request)
                response["manifest"] = materialize_manifest(
                    response["manifest"], self.server.public_base_url
                )
                self.send_json(HTTPStatus.OK, response)
                return
            raise GatewayError("NOT_FOUND", "Route not found.", HTTPStatus.NOT_FOUND)
        except GatewayError as error:
            self.send_error_json(error)

    def read_json_body(self) -> dict:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise GatewayError("INVALID_REQUEST", "Content-Length is required.", HTTPStatus.LENGTH_REQUIRED)
        try:
            length = int(raw_length)
        except ValueError as error:
            raise GatewayError("INVALID_REQUEST", "Invalid Content-Length.", HTTPStatus.BAD_REQUEST) from error
        if length < 1 or length > MAX_REQUEST_BYTES:
            raise GatewayError(
                "INVALID_REQUEST", "Request body size is invalid.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE
            )
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GatewayError("INVALID_REQUEST", "Body must be UTF-8 JSON.", HTTPStatus.BAD_REQUEST) from error
        if not isinstance(value, dict):
            raise GatewayError("INVALID_REQUEST", "Body must be a JSON object.", HTTPStatus.BAD_REQUEST)
        return value

    def send_asset(self, path: Path) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            LOGGER.debug("HTTP asset client disconnected path=%s", path.name)

    def send_error_json(self, error: GatewayError) -> None:
        self.send_json(
            error.status,
            {"error": {"code": error.code, "message": error.message}},
        )

    def send_json(self, status: HTTPStatus, value: dict) -> None:
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        LOGGER.debug("HTTP %s", format % args)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8787,
    registry_path: Path = DEFAULT_REGISTRY,
    ttl_seconds: int = 180,
    public_base_url: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> GatewayServer:
    store = ContentStore(registry_path)
    service = GrantService(store, ttl_seconds=ttl_seconds, clock=clock)
    server = GatewayServer((host, port), GatewayHandler, service, "http://placeholder")
    actual_host, actual_port = server.server_address[:2]
    advertised_host = "127.0.0.1" if actual_host in {"0.0.0.0", "::"} else actual_host
    server.public_base_url = public_base_url or f"http://{advertised_host}:{actual_port}"
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--grant-ttl-seconds", type=int, default=180)
    parser.add_argument("--public-base-url")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    server = create_server(
        host=args.host,
        port=args.port,
        registry_path=args.registry,
        ttl_seconds=args.grant_ttl_seconds,
        public_base_url=args.public_base_url,
    )
    LOGGER.info("LISTENING url=%s", server.public_base_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
