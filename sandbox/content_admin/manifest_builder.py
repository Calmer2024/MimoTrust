from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse


PROVIDER_ID = "mimotrust_sandbox"
CONTENT_TYPES = {"video", "audio", "article", "rich_article", "image_gallery"}
ASSET_ROLES = {"original", "playback", "analysis", "cover", "subtitle"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ASSET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
VERSION_RE = re.compile(r"^v[1-9][0-9]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ALLOWED_MIME_TYPES = {
    "video": {"video/mp4"},
    "audio": {"audio/mpeg", "audio/mp4", "audio/x-m4a"},
    "article": {"text/plain", "text/markdown"},
    "rich_article": {"image/jpeg", "image/png", "image/webp"},
    "image_gallery": {"image/jpeg", "image/png", "image/webp"},
}
IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
TEXT_MIME_TYPES = {"text/plain", "text/markdown", "text/vtt"}


class ContentValidationError(ValueError):
    pass


def _nonempty_string(value: Any, field: str, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContentValidationError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if maximum is not None and len(normalized) > maximum:
        raise ContentValidationError(f"{field} exceeds {maximum} characters")
    return normalized


def _https_url(value: Any, field: str) -> str:
    raw = _nonempty_string(value, field)
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ContentValidationError(f"{field} must be an HTTPS URL")
    return raw


def _date_time(value: Any, field: str) -> str:
    raw = _nonempty_string(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContentValidationError(f"{field} must be an ISO 8601 date-time") from error
    if parsed.tzinfo is None:
        raise ContentValidationError(f"{field} must include a timezone")
    return parsed.isoformat()


def normalize_draft(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContentValidationError("request body must be an object")
    allowed = {
        "content_type",
        "content_id",
        "title",
        "author",
        "published_at",
        "canonical_url",
        "assets",
        "blocks",
        "display_metrics",
        "rights",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ContentValidationError(f"unsupported fields: {', '.join(sorted(unknown))}")

    content_type = _nonempty_string(value.get("content_type"), "content_type")
    if content_type not in CONTENT_TYPES:
        raise ContentValidationError("content_type is unsupported")
    content_id = _nonempty_string(value.get("content_id"), "content_id")
    if not ID_RE.fullmatch(content_id):
        raise ContentValidationError("content_id must match ^[a-z0-9][a-z0-9-]{0,63}$")

    assets = _normalize_assets(value.get("assets"), content_type)
    blocks = _normalize_blocks(value.get("blocks"), assets, content_type)
    metrics = _normalize_metrics(value.get("display_metrics"))
    rights = _normalize_rights(value.get("rights"))

    return {
        "content_type": content_type,
        "content_id": content_id,
        "title": _nonempty_string(value.get("title"), "title", 200),
        "author": _nonempty_string(value.get("author"), "author", 100),
        "published_at": _date_time(value.get("published_at"), "published_at"),
        "canonical_url": _https_url(value.get("canonical_url"), "canonical_url"),
        "assets": assets,
        "blocks": blocks,
        "display_metrics": metrics,
        "rights": rights,
    }


def _normalize_assets(value: Any, content_type: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ContentValidationError("assets must be a non-empty array")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ContentValidationError(f"assets[{index}] must be an object")
        allowed = {
            "asset_id",
            "role",
            "file_name",
            "mime_type",
            "order",
            "duration_ms",
            "width",
            "height",
            "frame_rate",
            "video_codec",
            "audio_codec",
        }
        unknown = set(item) - allowed
        if unknown:
            raise ContentValidationError(
                f"assets[{index}] has unsupported fields: {', '.join(sorted(unknown))}"
            )
        asset_id = _nonempty_string(item.get("asset_id"), f"assets[{index}].asset_id")
        if not ASSET_ID_RE.fullmatch(asset_id) or asset_id in seen_ids:
            raise ContentValidationError(f"assets[{index}].asset_id is invalid or duplicated")
        seen_ids.add(asset_id)
        role = _nonempty_string(item.get("role"), f"assets[{index}].role")
        if role not in ASSET_ROLES:
            raise ContentValidationError(f"assets[{index}].role is unsupported")
        mime_type = _nonempty_string(item.get("mime_type"), f"assets[{index}].mime_type").lower()
        order = item.get("order", index)
        if isinstance(order, bool) or not isinstance(order, int) or order < 0 or order in seen_orders:
            raise ContentValidationError(f"assets[{index}].order is invalid or duplicated")
        seen_orders.add(order)
        asset = {
            "asset_id": asset_id,
            "role": role,
            "file_name": _nonempty_string(item.get("file_name"), f"assets[{index}].file_name", 255),
            "mime_type": mime_type,
            "order": order,
        }
        for key in ("duration_ms", "width", "height"):
            if key in item:
                number = item[key]
                if isinstance(number, bool) or not isinstance(number, int) or number < 1:
                    raise ContentValidationError(f"assets[{index}].{key} must be a positive integer")
                asset[key] = number
        if "frame_rate" in item:
            frame_rate = item["frame_rate"]
            if isinstance(frame_rate, bool) or not isinstance(frame_rate, (int, float)) or frame_rate <= 0:
                raise ContentValidationError(f"assets[{index}].frame_rate must be positive")
            asset["frame_rate"] = float(frame_rate)
        for key in ("video_codec", "audio_codec"):
            if key in item:
                asset[key] = _nonempty_string(item[key], f"assets[{index}].{key}", 100)
        normalized.append(asset)

    normalized.sort(key=lambda item: item["order"])
    _validate_asset_set(normalized, content_type)
    return normalized


def _validate_asset_set(assets: list[dict[str, Any]], content_type: str) -> None:
    analysis = [asset for asset in assets if asset["role"] == "analysis"]
    covers = [asset for asset in assets if asset["role"] == "cover"]
    subtitles = [asset for asset in assets if asset["role"] == "subtitle"]
    if len(covers) > 1 or len(subtitles) > 1:
        raise ContentValidationError("at most one cover and one subtitle are allowed")
    for asset in covers:
        if asset["mime_type"] not in IMAGE_MIME_TYPES:
            raise ContentValidationError("cover assets must be JPEG, PNG, or WebP")
    for asset in subtitles:
        if asset["mime_type"] != "text/vtt":
            raise ContentValidationError("subtitle assets must use text/vtt")

    allowed_primary = ALLOWED_MIME_TYPES[content_type]
    if content_type in {"video", "audio", "article"}:
        if len(analysis) != 1 or analysis[0]["mime_type"] not in allowed_primary:
            raise ContentValidationError(f"{content_type} requires exactly one supported analysis asset")
    elif content_type in {"rich_article", "image_gallery"}:
        if not analysis or any(asset["mime_type"] not in allowed_primary for asset in analysis):
            raise ContentValidationError(f"{content_type} requires one or more supported image assets")
    if content_type in {"article", "rich_article", "image_gallery"} and subtitles:
        raise ContentValidationError(f"{content_type} does not support subtitles")


def _normalize_blocks(value: Any, assets: list[dict[str, Any]], content_type: str) -> list[dict[str, Any]]:
    if content_type != "rich_article":
        if value not in (None, []):
            raise ContentValidationError("blocks are only allowed for rich_article")
        return []
    if not isinstance(value, list) or not value:
        raise ContentValidationError("rich_article requires a non-empty blocks array")
    image_ids = {asset["asset_id"] for asset in assets if asset["role"] == "analysis"}
    normalized: list[dict[str, Any]] = []
    referenced_images: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ContentValidationError(f"blocks[{index}] must be an object")
        block_type = item.get("block_type")
        if block_type == "text":
            if set(item) != {"block_type", "text"}:
                raise ContentValidationError(f"blocks[{index}] text block has invalid fields")
            normalized.append({
                "block_index": index,
                "block_type": "text",
                "text": _nonempty_string(item.get("text"), f"blocks[{index}].text"),
            })
        elif block_type == "image":
            if set(item) != {"block_type", "asset_id"}:
                raise ContentValidationError(f"blocks[{index}] image block has invalid fields")
            asset_id = _nonempty_string(item.get("asset_id"), f"blocks[{index}].asset_id")
            if asset_id not in image_ids:
                raise ContentValidationError(f"blocks[{index}] references an unknown image asset")
            referenced_images.append(asset_id)
            normalized.append({"block_index": index, "block_type": "image", "asset_id": asset_id})
        else:
            raise ContentValidationError(f"blocks[{index}].block_type is unsupported")
    if set(referenced_images) != image_ids or len(referenced_images) != len(set(referenced_images)):
        raise ContentValidationError("every rich_article analysis image must appear in blocks exactly once")
    return normalized


def _normalize_metrics(value: Any) -> dict[str, int]:
    value = value if value is not None else {}
    if not isinstance(value, dict) or set(value) - {"like_count", "comment_count", "share_count"}:
        raise ContentValidationError("display_metrics has unsupported fields")
    result: dict[str, int] = {}
    for key in ("like_count", "comment_count", "share_count"):
        number = value.get(key, 0)
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise ContentValidationError(f"display_metrics.{key} must be a non-negative integer")
        result[key] = number
    return result


def _normalize_rights(value: Any) -> dict[str, Any]:
    value = value if value is not None else {}
    if not isinstance(value, dict) or set(value) - {
        "purpose", "retention_seconds", "redistribution_allowed"
    }:
        raise ContentValidationError("rights has unsupported fields")
    purpose = value.get("purpose", ["fact_check"])
    if not isinstance(purpose, list) or not purpose or not all(isinstance(item, str) and item for item in purpose):
        raise ContentValidationError("rights.purpose must be a non-empty string array")
    retention = value.get("retention_seconds", 3600)
    if isinstance(retention, bool) or not isinstance(retention, int) or retention < 0:
        raise ContentValidationError("rights.retention_seconds must be a non-negative integer")
    redistribution = value.get("redistribution_allowed", False)
    if not isinstance(redistribution, bool):
        raise ContentValidationError("rights.redistribution_allowed must be boolean")
    return {
        "purpose": purpose,
        "retention_seconds": retention,
        "redistribution_allowed": redistribution,
    }


def composite_content_hash(content_type: str, blocks: list[dict[str, Any]], assets: list[dict[str, Any]]) -> str:
    payload: dict[str, Any] = {
        "algorithm": "mimotrust-composite-v1",
        "content_type": content_type,
        "assets": [
            {"asset_id": asset["asset_id"], "sha256": asset["sha256"]}
            for asset in assets
            if asset["role"] == "analysis"
        ],
    }
    if content_type == "rich_article":
        payload["blocks"] = blocks
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_manifest(
    draft: dict[str, Any],
    version: str,
    stored_assets: list[dict[str, Any]],
) -> dict[str, Any]:
    if not VERSION_RE.fullmatch(version):
        raise ContentValidationError("content_version is invalid")
    by_id = {asset["asset_id"]: asset for asset in stored_assets}
    expected_ids = [asset["asset_id"] for asset in draft["assets"]]
    if set(by_id) != set(expected_ids):
        raise ContentValidationError("uploaded asset set does not match the draft")

    assets: list[dict[str, Any]] = []
    for descriptor in draft["assets"]:
        uploaded = by_id[descriptor["asset_id"]]
        if uploaded["mime_type"] != descriptor["mime_type"]:
            raise ContentValidationError(f"MIME mismatch for {descriptor['asset_id']}")
        asset = {
            "asset_id": descriptor["asset_id"],
            "role": descriptor["role"],
            "mime_type": uploaded["mime_type"],
            "source_url": uploaded["source_url"],
            "sha256": uploaded["sha256"],
            "size_bytes": uploaded["size_bytes"],
            "derivation": "original",
            "order": descriptor["order"],
            "original_name": descriptor["file_name"],
            "storage": uploaded["storage"],
        }
        for key in ("duration_ms", "width", "height", "frame_rate", "video_codec", "audio_codec"):
            if key in uploaded:
                asset[key] = uploaded[key]
            elif key in descriptor:
                asset[key] = descriptor[key]
        assets.append(asset)

    analysis_assets = [asset for asset in assets if asset["role"] == "analysis"]
    content_type = draft["content_type"]
    if content_type in {"video", "audio", "article"}:
        content_hash = analysis_assets[0]["sha256"]
    else:
        content_hash = composite_content_hash(content_type, draft["blocks"], assets)

    content: dict[str, Any] = {
        "content_type": content_type,
        "content_id": draft["content_id"],
        "content_version": version,
        "content_hash": content_hash,
        "canonical_url": draft["canonical_url"],
        "title": draft["title"],
        "author": draft["author"],
        "published_at": draft["published_at"],
        "asset_order": [asset["asset_id"] for asset in assets],
    }
    if content_type == "article":
        content["body_asset_id"] = analysis_assets[0]["asset_id"]
    if content_type == "rich_article":
        content["blocks"] = draft["blocks"]

    return {
        "manifest_version": "1.0",
        "provider": {"provider_id": PROVIDER_ID},
        "content": content,
        "assets": assets,
        "rights": draft["rights"],
        "sandbox": {
            "access_enforcement": "signed_url" if uploaded_uses_signed_urls(assets) else "mock_gateway_only",
            "development_asset": True,
            "notes": (
                "Uploaded by the developer content admin. Composite hashes use "
                "mimotrust-composite-v1 pending backend confirmation."
            ),
        },
    }


def uploaded_uses_signed_urls(assets: list[dict[str, Any]]) -> bool:
    return any(asset.get("storage", {}).get("signed_url") is True for asset in assets)
