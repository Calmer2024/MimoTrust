#!/usr/bin/env python3
"""Validate the first-round MiMoTrust contract fixtures without dependencies."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
REGISTRY_ROOT = ROOT / "sandbox" / "content_registry"
APP_ASSET_ROOT = ROOT / "sandbox" / "mimotrust_controlled_content" / "assets"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
VERSION_RE = re.compile(r"^v[1-9][0-9]*$")
CONTENT_TYPES = {"video", "audio", "article", "rich_article", "image_gallery"}


class ContractError(ValueError):
    pass


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"{path}: invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ContractError(f"{path}: root must be an object")
    return value


def exact_keys(value: dict, required: set[str], optional: set[str], path: str) -> None:
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing:
        raise ContractError(f"{path}: missing {sorted(missing)}")
    if extra:
        raise ContractError(f"{path}: unexpected {sorted(extra)}")


def nonempty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{path}: expected non-empty string")
    return value


def integer(value: object, path: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError(f"{path}: expected integer >= {minimum}")
    return value


def number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{path}: expected number")
    return float(value)


def parse_datetime(value: object, path: str) -> datetime:
    raw = nonempty_string(value, path)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError(f"{path}: invalid ISO 8601 date-time") from error
    if parsed.tzinfo is None:
        raise ContractError(f"{path}: timezone is required")
    return parsed


def require_url(value: object, path: str, https_only: bool = False) -> str:
    raw = nonempty_string(value, path)
    parsed = urlparse(raw)
    allowed = {"https"} if https_only else {"http", "https"}
    if parsed.scheme not in allowed or not parsed.netloc:
        raise ContractError(f"{path}: invalid URL")
    return raw


def validate_context(value: dict, source: str) -> None:
    encoded_size = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if encoded_size > 32 * 1024:
        raise ContractError(f"{source}: payload exceeds 32 KB")
    required = {
        "schema_version", "event_id", "trigger", "source_app", "provider",
        "content_ref", "content_access", "view_state", "observed_at",
    }
    exact_keys(value, required, set(), source)
    if value["schema_version"] != "2.2":
        raise ContractError(f"{source}.schema_version: unsupported")
    try:
        uuid.UUID(nonempty_string(value["event_id"], f"{source}.event_id"))
    except ValueError as error:
        raise ContractError(f"{source}.event_id: invalid UUID") from error
    if value["trigger"] not in {"comment", "share", "guardian_request"}:
        raise ContractError(f"{source}.trigger: unsupported")
    if value["source_app"] != "mimotrust_controlled_content":
        raise ContractError(f"{source}.source_app: mismatch")

    provider = value["provider"]
    if not isinstance(provider, dict):
        raise ContractError(f"{source}.provider: expected object")
    exact_keys(provider, {"provider_id", "application_id"}, set(), f"{source}.provider")
    if provider["provider_id"] != "mimotrust_sandbox" or provider["application_id"] != "com.mimotrust.controlledcontent":
        raise ContractError(f"{source}.provider: identity mismatch")

    content = value["content_ref"]
    if not isinstance(content, dict):
        raise ContractError(f"{source}.content_ref: expected object")
    exact_keys(
        content,
        {"content_type", "content_id", "content_version", "content_hash", "canonical_url"},
        set(),
        f"{source}.content_ref",
    )
    content_type = content["content_type"]
    if content_type not in CONTENT_TYPES:
        raise ContractError(f"{source}.content_ref.content_type: unsupported")
    if not ID_RE.fullmatch(nonempty_string(content["content_id"], f"{source}.content_ref.content_id")):
        raise ContractError(f"{source}.content_ref.content_id: invalid")
    if not VERSION_RE.fullmatch(nonempty_string(content["content_version"], f"{source}.content_ref.content_version")):
        raise ContractError(f"{source}.content_ref.content_version: invalid")
    if not SHA256_RE.fullmatch(nonempty_string(content["content_hash"], f"{source}.content_ref.content_hash")):
        raise ContractError(f"{source}.content_ref.content_hash: invalid")
    require_url(content["canonical_url"], f"{source}.content_ref.canonical_url", https_only=True)

    access = value["content_access"]
    if not isinstance(access, dict):
        raise ContractError(f"{source}.content_access: expected object")
    exact_keys(
        access,
        {"mode"},
        {"exchange_url", "grant_code", "audience", "expires_at", "scopes"},
        f"{source}.content_access",
    )
    if access["mode"] not in {"deferred_grant", "grant_exchange", "public_manifest", "content_uri"}:
        raise ContractError(f"{source}.content_access.mode: unsupported")
    if value["trigger"] in {"comment", "share"} and access != {"mode": "deferred_grant"}:
        raise ContractError(f"{source}.content_access: candidate must be deferred")
    if value["trigger"] == "guardian_request" and access["mode"] != "grant_exchange":
        raise ContractError(f"{source}.content_access: guardian request requires grant")
    observed_at = parse_datetime(value["observed_at"], f"{source}.observed_at")
    if access["mode"] == "grant_exchange":
        required_access = {"exchange_url", "grant_code", "audience", "expires_at", "scopes"}
        if not required_access.issubset(access):
            raise ContractError(f"{source}.content_access: incomplete grant_exchange")
        require_url(access["exchange_url"], f"{source}.content_access.exchange_url")
        nonempty_string(access["grant_code"], f"{source}.content_access.grant_code")
        if access["audience"] != "mimotrust_guardian_backend":
            raise ContractError(f"{source}.content_access.audience: mismatch")
        expires_at = parse_datetime(access["expires_at"], f"{source}.content_access.expires_at")
        if expires_at <= observed_at:
            raise ContractError(f"{source}.content_access.expires_at: already expired")
        scopes = access["scopes"]
        if not isinstance(scopes, list) or not scopes or len(scopes) != len(set(scopes)):
            raise ContractError(f"{source}.content_access.scopes: invalid")
        if not set(scopes).issubset({"manifest:read", "asset:read"}):
            raise ContractError(f"{source}.content_access.scopes: unsupported")

    view = value["view_state"]
    if not isinstance(view, dict):
        raise ContractError(f"{source}.view_state: expected object")
    if content_type in {"video", "audio"}:
        exact_keys(view, {"position_ms", "duration_ms", "is_playing"}, set(), f"{source}.view_state")
        position = integer(view["position_ms"], f"{source}.view_state.position_ms")
        duration = integer(view["duration_ms"], f"{source}.view_state.duration_ms", 1)
        if position > duration:
            raise ContractError(f"{source}.view_state.position_ms: exceeds duration")
        if not isinstance(view["is_playing"], bool):
            raise ContractError(f"{source}.view_state.is_playing: expected boolean")
    elif content_type in {"article", "rich_article"}:
        exact_keys(view, {"scroll_ratio", "block_index"}, set(), f"{source}.view_state")
        ratio = number(view["scroll_ratio"], f"{source}.view_state.scroll_ratio")
        if not 0 <= ratio <= 1:
            raise ContractError(f"{source}.view_state.scroll_ratio: out of range")
        integer(view["block_index"], f"{source}.view_state.block_index")
    else:
        exact_keys(view, {"active_asset_index", "asset_count"}, set(), f"{source}.view_state")
        active = integer(view["active_asset_index"], f"{source}.view_state.active_asset_index")
        count = integer(view["asset_count"], f"{source}.view_state.asset_count", 1)
        if active >= count:
            raise ContractError(f"{source}.view_state.active_asset_index: out of range")


def validate_manifest(value: dict, source: str) -> None:
    exact_keys(value, {"manifest_version", "provider", "content", "assets", "rights", "sandbox"}, set(), source)
    if value["manifest_version"] != "1.0":
        raise ContractError(f"{source}.manifest_version: unsupported")
    provider = value["provider"]
    if provider != {"provider_id": "mimotrust_sandbox"}:
        raise ContractError(f"{source}.provider: mismatch")
    content = value["content"]
    required_content = {
        "content_type", "content_id", "content_version", "content_hash",
        "canonical_url", "title", "author", "published_at",
    }
    exact_keys(content, required_content, {"body_asset_id", "asset_order", "blocks"}, f"{source}.content")
    if content["content_type"] not in CONTENT_TYPES:
        raise ContractError(f"{source}.content.content_type: unsupported")
    if not ID_RE.fullmatch(nonempty_string(content["content_id"], f"{source}.content.content_id")):
        raise ContractError(f"{source}.content.content_id: invalid")
    if not VERSION_RE.fullmatch(nonempty_string(content["content_version"], f"{source}.content.content_version")):
        raise ContractError(f"{source}.content.content_version: invalid")
    if not SHA256_RE.fullmatch(nonempty_string(content["content_hash"], f"{source}.content.content_hash")):
        raise ContractError(f"{source}.content.content_hash: invalid")
    require_url(content["canonical_url"], f"{source}.content.canonical_url", https_only=True)
    nonempty_string(content["title"], f"{source}.content.title")
    nonempty_string(content["author"], f"{source}.content.author")
    parse_datetime(content["published_at"], f"{source}.content.published_at")

    assets = value["assets"]
    if not isinstance(assets, list) or not assets:
        raise ContractError(f"{source}.assets: expected non-empty array")
    asset_ids = set()
    for index, asset in enumerate(assets):
        path = f"{source}.assets[{index}]"
        required_asset = {"asset_id", "role", "mime_type", "source_url", "sha256", "size_bytes", "derivation"}
        optional_asset = {
            "duration_ms", "width", "height", "frame_rate", "video_codec", "audio_codec",
            "source_asset_id", "order", "original_name", "storage", "http",
        }
        exact_keys(asset, required_asset, optional_asset, path)
        asset_id = nonempty_string(asset["asset_id"], f"{path}.asset_id")
        if asset_id in asset_ids:
            raise ContractError(f"{path}.asset_id: duplicate")
        asset_ids.add(asset_id)
        require_url(asset["source_url"], f"{path}.source_url")
        if not SHA256_RE.fullmatch(nonempty_string(asset["sha256"], f"{path}.sha256")):
            raise ContractError(f"{path}.sha256: invalid")
        integer(asset["size_bytes"], f"{path}.size_bytes", 1)
        storage = asset.get("storage")
        if storage and storage.get("provider") == "local":
            object_key = nonempty_string(storage.get("object_key"), f"{path}.storage.object_key")
            local_path = (REGISTRY_ROOT / object_key).resolve()
            if REGISTRY_ROOT.resolve() not in local_path.parents or not local_path.is_file():
                raise ContractError(f"{path}: local asset missing")
            if local_path.stat().st_size != asset["size_bytes"]:
                raise ContractError(f"{path}: local asset size mismatch")
            digest = hashlib.sha256(local_path.read_bytes()).hexdigest()
            if digest != asset["sha256"]:
                raise ContractError(f"{path}: local asset hash mismatch")
    order = content.get("asset_order")
    if order is not None and (not isinstance(order, list) or len(order) != len(set(order)) or set(order) != asset_ids):
        raise ContractError(f"{source}.content.asset_order: must list every asset once")
    if content["content_type"] == "video":
        analysis_assets = [item for item in assets if item["role"] == "analysis"]
        if len(analysis_assets) != 1 or analysis_assets[0]["sha256"] != content["content_hash"]:
            raise ContractError(f"{source}: video content hash must match its analysis asset")


def main() -> int:
    load_json(CONTRACTS / "content_context.schema.json")
    load_json(CONTRACTS / "content_manifest.schema.json")
    valid_paths = sorted((CONTRACTS / "examples").glob("*.json"))
    invalid_paths = sorted((CONTRACTS / "examples" / "invalid").glob("*.json"))
    for path in valid_paths:
        validate_context(load_json(path), str(path.relative_to(ROOT)))
    for path in invalid_paths:
        try:
            validate_context(load_json(path), str(path.relative_to(ROOT)))
        except ContractError:
            continue
        raise ContractError(f"{path.relative_to(ROOT)}: invalid fixture unexpectedly passed")

    registry = load_json(REGISTRY_ROOT / "registry.json")
    if registry.get("provider_id") != "mimotrust_sandbox":
        raise ContractError("registry provider mismatch")
    app_registry = load_json(APP_ASSET_ROOT / "data" / "registry.json")
    if app_registry != registry:
        raise ContractError("Flutter registry asset differs from the canonical registry")
    active_keys = set()
    for entry in registry.get("contents", []):
        if entry.get("status") != "active":
            continue
        key = (entry.get("content_id"), entry.get("content_version"))
        if key in active_keys:
            raise ContractError(f"duplicate active registry entry: {key}")
        active_keys.add(key)
        metrics = entry.get("display_metrics")
        if not isinstance(metrics, dict) or set(metrics) != {
            "like_count", "comment_count", "share_count"
        }:
            raise ContractError(f"registry display_metrics invalid: {key}")
        for metric_name, metric_value in metrics.items():
            integer(metric_value, f"registry.{key}.display_metrics.{metric_name}")
        manifest_path = (REGISTRY_ROOT / entry["manifest_path"]).resolve()
        if REGISTRY_ROOT.resolve() not in manifest_path.parents:
            raise ContractError("manifest path escapes registry")
        manifest = load_json(manifest_path)
        validate_manifest(manifest, str(manifest_path.relative_to(ROOT)))
        app_manifest = load_json(APP_ASSET_ROOT / "data" / entry["manifest_path"])
        if app_manifest != manifest:
            raise ContractError(
                f"Flutter Manifest asset differs from canonical Manifest: {key}"
            )
        content = manifest["content"]
        if key != (content["content_id"], content["content_version"]):
            raise ContractError(f"registry identity mismatch: {key}")
        for asset in manifest["assets"]:
            storage = asset.get("storage")
            if not storage or storage.get("provider") != "local":
                continue
            object_key = storage["object_key"]
            canonical_asset = (REGISTRY_ROOT / object_key).resolve()
            app_asset = (APP_ASSET_ROOT.parent / object_key).resolve()
            if not app_asset.is_file() or hashlib.sha256(app_asset.read_bytes()).digest() != hashlib.sha256(
                canonical_asset.read_bytes()
            ).digest():
                raise ContractError(
                    f"Flutter local asset differs from canonical asset: {object_key}"
                )

    print(
        f"OK: {len(valid_paths)} valid contexts, {len(invalid_paths)} rejected contexts, "
        f"{len(active_keys)} active manifest"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ContractError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
