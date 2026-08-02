#!/usr/bin/env python3
"""Exercise the first-round gateway flow and verify the remote video hash."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


AUDIENCE = "mimotrust_guardian_backend"


def request_json(url: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        return response.status, json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", default="http://127.0.0.1:8787")
    args = parser.parse_args()
    base_url = args.gateway.rstrip("/")

    _, health = request_json(f"{base_url}/health")
    content_count = health.get("content_count")
    if (
        health.get("status") != "ok"
        or health.get("provider_id") != "mimotrust_sandbox"
        or health.get("manifest_version") != "1.0"
        or not isinstance(content_count, int)
        or isinstance(content_count, bool)
        or content_count < 1
    ):
        raise RuntimeError(f"unexpected health response: {health}")

    grant_request = {
        "content_id": "video-001",
        "content_version": "v1",
        "audience": AUDIENCE,
        "scopes": ["manifest:read", "asset:read"],
    }
    status, issued = request_json(f"{base_url}/v1/context-grants", "POST", grant_request)
    if status != 201:
        raise RuntimeError(f"grant issue returned HTTP {status}")

    exchange_request = {
        "grant_code": issued["grant_code"],
        "content_id": "video-001",
        "content_version": "v1",
        "audience": AUDIENCE,
    }
    _, exchanged = request_json(f"{base_url}/v1/grants/exchange", "POST", exchange_request)
    manifest = exchanged["manifest"]
    content = manifest["content"]
    asset = next(item for item in manifest["assets"] if item["role"] == "analysis")
    if content["content_hash"] != asset["sha256"]:
        raise RuntimeError("content hash does not match the analysis asset")

    digest = hashlib.sha256()
    downloaded = 0
    with urlopen(asset["source_url"], timeout=30) as response:
        if response.headers.get_content_type() != asset["mime_type"]:
            raise RuntimeError("remote MIME type does not match the manifest")
        while chunk := response.read(64 * 1024):
            downloaded += len(chunk)
            if downloaded > asset["size_bytes"]:
                raise RuntimeError("remote asset exceeds the declared byte size")
            digest.update(chunk)
    if downloaded != asset["size_bytes"]:
        raise RuntimeError(f"size mismatch: expected {asset['size_bytes']}, received {downloaded}")
    if digest.hexdigest() != asset["sha256"]:
        raise RuntimeError("remote asset SHA-256 mismatch")

    try:
        request_json(f"{base_url}/v1/grants/exchange", "POST", exchange_request)
    except HTTPError as error:
        replay = json.load(error)
        if error.code != 410 or replay.get("error", {}).get("code") != "GRANT_REPLAYED":
            raise RuntimeError(f"unexpected replay response: HTTP {error.code} {replay}") from error
    else:
        raise RuntimeError("grant replay unexpectedly succeeded")

    print("OK: health -> grant -> exchange -> download -> SHA-256 -> replay rejection")
    print(f"content_id={content['content_id']} size_bytes={downloaded} sha256={digest.hexdigest()}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
