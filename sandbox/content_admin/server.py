#!/usr/bin/env python3
"""Local-only developer upload service for normalized sandbox content."""

from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .drafts import DraftRepository
from .manifest_builder import ContentValidationError
from .publisher import ContentPublisher
from .storage import AliyunOssStorage


LOGGER = logging.getLogger("MiMoTrustContentAdmin")
SANDBOX_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = SANDBOX_ROOT / "content_registry" / "registry.json"
DEFAULT_DRAFTS = SANDBOX_ROOT / "content_admin_data" / "drafts"
STATIC_ROOT = Path(__file__).resolve().parent / "static"
MAX_JSON_BYTES = 256 * 1024
DEFAULT_MAX_ASSET_BYTES = 512 * 1024 * 1024
DRAFT_RE = re.compile(r"^/admin/v1/drafts/([0-9a-f-]{36})$")
ASSET_RE = re.compile(r"^/admin/v1/drafts/([0-9a-f-]{36})/assets/([a-z0-9][a-z0-9-]{0,63})$")
PUBLISH_RE = re.compile(r"^/admin/v1/drafts/([0-9a-f-]{36})/publish$")
PREVIEW_RE = re.compile(r"^/admin/v1/drafts/([0-9a-f-]{36})/preview$")


class AdminServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        publisher: ContentPublisher,
        token: str,
        canonical_base_url: str,
        max_asset_bytes: int,
    ):
        super().__init__(address, handler)
        self.publisher = publisher
        self.token = token
        self.canonical_base_url = canonical_base_url.rstrip("/")
        self.max_asset_bytes = max_asset_bytes


class AdminHandler(BaseHTTPRequestHandler):
    server: AdminServer

    def do_GET(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/health":
                self.send_json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "service": "mimotrust_content_admin",
                        "storage": self.server.publisher.storage.__class__.__name__,
                    },
                )
                return
            if path in {"/", "/admin", "/admin/"}:
                self.send_static("index.html", "text/html; charset=utf-8")
                return
            if path == "/admin/app.js":
                self.send_static("app.js", "application/javascript; charset=utf-8")
                return
            if path == "/admin/styles.css":
                self.send_static("styles.css", "text/css; charset=utf-8")
                return
            self.require_auth()
            if path == "/admin/v1/config":
                self.send_json(
                    HTTPStatus.OK,
                    {
                        "canonical_base_url": self.server.canonical_base_url,
                        "max_asset_bytes": self.server.max_asset_bytes,
                        "bucket": self.server.publisher.storage.bucket_name,
                        "endpoint": self.server.publisher.storage.endpoint_host,
                        "object_prefix": self.server.publisher.storage.object_prefix,
                    },
                )
                return
            if path == "/admin/v1/contents":
                self.send_json(
                    HTTPStatus.OK,
                    {"contents": self.server.publisher.list_contents()},
                )
                return
            match = DRAFT_RE.fullmatch(path)
            if match:
                self.send_json(
                    HTTPStatus.OK,
                    self.server.publisher.drafts.public_get(match.group(1)),
                )
                return
            self.not_found()
        except AuthenticationError:
            self.send_auth_required()
        except ContentValidationError as error:
            self.send_admin_error("INVALID_REQUEST", str(error), HTTPStatus.BAD_REQUEST)
        except Exception:
            LOGGER.exception("ADMIN_REQUEST_FAILED path=%s", urlparse(self.path).path)
            self.send_admin_error(
                "ADMIN_INTERNAL_ERROR",
                "The admin service could not complete the request.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_POST(self) -> None:
        try:
            self.require_auth()
            path = urlparse(self.path).path
            if path == "/admin/v1/drafts":
                created = self.server.publisher.drafts.create(self.read_json_body())
                self.send_json(HTTPStatus.CREATED, created)
                return
            match = PUBLISH_RE.fullmatch(path)
            if match:
                if self.content_length() not in {0, None}:
                    raise ContentValidationError("publish request must have an empty body")
                published = self.server.publisher.publish(match.group(1))
                self.send_json(HTTPStatus.CREATED, published)
                return
            match = PREVIEW_RE.fullmatch(path)
            if match:
                if self.content_length() not in {0, None}:
                    raise ContentValidationError("preview request must have an empty body")
                manifest = self.server.publisher.preview(match.group(1))
                self.send_json(HTTPStatus.OK, {"manifest": manifest})
                return
            self.not_found()
        except AuthenticationError:
            self.send_auth_required()
        except ContentValidationError as error:
            self.send_admin_error("INVALID_REQUEST", str(error), HTTPStatus.BAD_REQUEST)
        except Exception:
            LOGGER.exception("ADMIN_REQUEST_FAILED path=%s", urlparse(self.path).path)
            self.send_admin_error(
                "ADMIN_INTERNAL_ERROR",
                "The admin service could not complete the request.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_PUT(self) -> None:
        try:
            self.require_auth()
            path = urlparse(self.path).path
            match = ASSET_RE.fullmatch(path)
            if not match:
                self.not_found()
                return
            length = self.content_length()
            if length is None:
                raise ContentValidationError("Content-Length is required")
            result = self.server.publisher.drafts.receive(
                match.group(1),
                match.group(2),
                self.rfile,
                length,
            )
            self.send_json(HTTPStatus.OK, result)
        except AuthenticationError:
            self.send_auth_required()
        except ContentValidationError as error:
            self.send_admin_error("INVALID_ASSET", str(error), HTTPStatus.BAD_REQUEST)
        except Exception:
            LOGGER.exception("ASSET_UPLOAD_FAILED path=%s", urlparse(self.path).path)
            self.send_admin_error(
                "ADMIN_INTERNAL_ERROR",
                "The admin service could not store the asset.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def require_auth(self) -> None:
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.token}"
        if not hmac.compare_digest(supplied, expected):
            raise AuthenticationError()

    def read_json_body(self) -> dict[str, Any]:
        length = self.content_length()
        if length is None:
            raise ContentValidationError("Content-Length is required")
        if length < 1 or length > MAX_JSON_BYTES:
            raise ContentValidationError("JSON request size is invalid")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ContentValidationError("request body must be UTF-8 JSON") from error
        if not isinstance(value, dict):
            raise ContentValidationError("request body must be an object")
        return value

    def content_length(self) -> int | None:
        raw = self.headers.get("Content-Length")
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError as error:
            raise ContentValidationError("Content-Length is invalid") from error

    def send_static(self, name: str, content_type: str) -> None:
        path = STATIC_ROOT / name
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob: data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status: HTTPStatus, value: Any) -> None:
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_admin_error(self, code: str, message: str, status: HTTPStatus) -> None:
        self.send_json(status, {"error": {"code": code, "message": message}})

    def not_found(self) -> None:
        self.send_admin_error("NOT_FOUND", "Route not found.", HTTPStatus.NOT_FOUND)

    def send_auth_required(self) -> None:
        data = json.dumps(
            {
                "error": {
                    "code": "ADMIN_AUTH_REQUIRED",
                    "message": "A valid administrator token is required.",
                }
            },
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("WWW-Authenticate", 'Bearer realm="sandbox-content-admin"')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.debug("HTTP %s", format % args)

class AuthenticationError(Exception):
    pass


def create_server(
    host: str,
    port: int,
    registry_path: Path,
    drafts_path: Path,
    token: str,
    canonical_base_url: str,
    max_asset_bytes: int = DEFAULT_MAX_ASSET_BYTES,
    storage: Any | None = None,
) -> AdminServer:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("content admin must bind to a loopback address")
    if len(token) < 32:
        raise ValueError("MIMOTRUST_ADMIN_TOKEN must contain at least 32 characters")
    parsed = urlparse(canonical_base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("canonical base URL must use HTTPS")
    drafts = DraftRepository(drafts_path, registry_path, max_asset_bytes)
    publisher = ContentPublisher(drafts, registry_path, storage or AliyunOssStorage.from_environment())
    return AdminServer(
        (host, port),
        AdminHandler,
        publisher,
        token,
        canonical_base_url,
        max_asset_bytes,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--drafts", type=Path, default=DEFAULT_DRAFTS)
    parser.add_argument("--max-asset-bytes", type=int, default=DEFAULT_MAX_ASSET_BYTES)
    args = parser.parse_args()
    token = os.environ.get("MIMOTRUST_ADMIN_TOKEN", "")
    canonical_base_url = os.environ.get(
        "MIMOTRUST_CANONICAL_BASE_URL",
        "https://sandbox.mimotrust.local/content",
    )
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    server = create_server(
        args.host,
        args.port,
        args.registry,
        args.drafts,
        token,
        canonical_base_url,
        max_asset_bytes=args.max_asset_bytes,
    )
    LOGGER.info("LISTENING url=http://%s:%s", *server.server_address[:2])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
