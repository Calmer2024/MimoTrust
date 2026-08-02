from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from .manifest_builder import ContentValidationError


EXTENSIONS = {
    "video/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/vtt": ".vtt",
}


class AliyunOssStorage:
    def __init__(
        self,
        endpoint: str,
        bucket_name: str,
        public_base_url: str,
        object_prefix: str,
        access_key_id: str,
        access_key_secret: str,
        security_token: str | None = None,
    ):
        try:
            import oss2
        except ImportError as error:
            raise RuntimeError("oss2 is required for Aliyun OSS uploads") from error
        endpoint = endpoint.rstrip("/")
        public_base_url = public_base_url.rstrip("/")
        parsed_endpoint = urlparse(endpoint)
        if parsed_endpoint.scheme != "https" or not parsed_endpoint.netloc:
            raise ValueError("OSS endpoint must be an HTTPS URL")
        parsed_public = urlparse(public_base_url)
        if parsed_public.scheme != "https" or not parsed_public.netloc:
            raise ValueError("OSS public base URL must be an HTTPS URL")
        if not bucket_name or not access_key_id or not access_key_secret:
            raise ValueError("OSS bucket and access credentials are required")
        auth = (
            oss2.StsAuth(access_key_id, access_key_secret, security_token)
            if security_token
            else oss2.Auth(access_key_id, access_key_secret)
        )
        self._bucket = oss2.Bucket(auth, endpoint, bucket_name)
        self.endpoint_host = parsed_endpoint.netloc
        self.bucket_name = bucket_name
        self.public_base_url = public_base_url
        self.object_prefix = object_prefix.strip("/")

    @classmethod
    def from_environment(cls) -> "AliyunOssStorage":
        return cls(
            endpoint=os.environ.get("MIMOTRUST_OSS_ENDPOINT", "https://oss-cn-beijing.aliyuncs.com"),
            bucket_name=os.environ.get("MIMOTRUST_OSS_BUCKET", "sourcecheckcheck"),
            public_base_url=os.environ.get(
                "MIMOTRUST_OSS_PUBLIC_BASE_URL",
                "https://sourcecheckcheck.oss-cn-beijing.aliyuncs.com",
            ),
            object_prefix=os.environ.get("MIMOTRUST_OSS_OBJECT_PREFIX", "sandbox-content"),
            access_key_id=os.environ.get("MIMOTRUST_OSS_ACCESS_KEY_ID", ""),
            access_key_secret=os.environ.get("MIMOTRUST_OSS_ACCESS_KEY_SECRET", ""),
            security_token=os.environ.get("MIMOTRUST_OSS_SECURITY_TOKEN"),
        )

    def object_key(self, content_type: str, content_id: str, version: str, asset_id: str, mime_type: str) -> str:
        extension = EXTENSIONS.get(mime_type)
        if extension is None:
            raise ContentValidationError(f"no normalized extension for {mime_type}")
        components = [content_type, content_id, version, asset_id + extension]
        relative = "/".join(components)
        return f"{self.object_prefix}/{relative}" if self.object_prefix else relative

    def put_file(self, path: Path, object_key: str, mime_type: str) -> dict[str, Any]:
        headers = {"Content-Type": mime_type, "Cache-Control": "public, max-age=31536000, immutable"}
        self._bucket.put_object_from_file(object_key, str(path), headers=headers)
        return self.describe(object_key)

    def describe(self, object_key: str) -> dict[str, Any]:
        return {
            "source_url": f"{self.public_base_url}/{quote(object_key, safe='/')}",
            "storage": {
                "provider": "aliyun_oss",
                "object_key": object_key,
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_host,
            },
        }


class FakeStorage:
    """Deterministic storage used by tests without network access."""

    def __init__(self):
        self.uploads: list[tuple[str, bytes, str]] = []
        self.bucket_name = "test-bucket"
        self.endpoint_host = "oss-cn-beijing.aliyuncs.com"
        self.object_prefix = "sandbox-content"

    def object_key(self, content_type: str, content_id: str, version: str, asset_id: str, mime_type: str) -> str:
        extension = EXTENSIONS[mime_type]
        return f"{self.object_prefix}/{content_type}/{content_id}/{version}/{asset_id}{extension}"

    def put_file(self, path: Path, object_key: str, mime_type: str) -> dict[str, Any]:
        self.uploads.append((object_key, path.read_bytes(), mime_type))
        return self.describe(object_key)

    def describe(self, object_key: str) -> dict[str, Any]:
        return {
            "source_url": f"https://test-bucket.oss-cn-beijing.aliyuncs.com/{object_key}",
            "storage": {
                "provider": "aliyun_oss",
                "object_key": object_key,
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_host,
            },
        }
