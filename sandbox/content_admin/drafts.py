from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

from .asset_processing import receive_asset
from .manifest_builder import ContentValidationError, normalize_draft


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContentValidationError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise ContentValidationError(f"{path.name} must contain a JSON object")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


class DraftRepository:
    def __init__(self, root: Path, registry_path: Path, max_asset_bytes: int):
        self.root = root.resolve()
        self.registry_path = registry_path.resolve()
        self.max_asset_bytes = max_asset_bytes
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create(self, request: Any) -> dict[str, Any]:
        normalized = normalize_draft(request)
        with self._lock:
            version = self._next_version(normalized["content_id"])
            draft_id = str(uuid.uuid4())
            value = {
                "draft_id": draft_id,
                "state": "draft",
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "content_version": version,
                "content": normalized,
                "uploaded_assets": {},
            }
            write_json_atomic(self._metadata_path(draft_id), value)
            return public_draft(value)

    def get(self, draft_id: str) -> dict[str, Any]:
        with self._lock:
            return read_json(self._metadata_path_checked(draft_id))

    def public_get(self, draft_id: str) -> dict[str, Any]:
        return public_draft(self.get(draft_id))

    def receive(
        self,
        draft_id: str,
        asset_id: str,
        source: BinaryIO,
        length: int,
    ) -> dict[str, Any]:
        with self._lock:
            value = self.get(draft_id)
            if value["state"] != "draft":
                raise ContentValidationError("only draft content can receive assets")
            descriptor = next(
                (item for item in value["content"]["assets"] if item["asset_id"] == asset_id),
                None,
            )
            if descriptor is None:
                raise ContentValidationError("asset_id is not declared by this draft")
            target = self._asset_path(draft_id, asset_id)
            metadata = receive_asset(
                source,
                target,
                length,
                descriptor["mime_type"],
                self.max_asset_bytes,
            )
            metadata["uploaded_at"] = utc_now()
            value["uploaded_assets"][asset_id] = metadata
            value["updated_at"] = utc_now()
            write_json_atomic(self._metadata_path(draft_id), value)
            return {"asset_id": asset_id, **metadata}

    def asset_path(self, draft_id: str, asset_id: str) -> Path:
        value = self.get(draft_id)
        if asset_id not in value["uploaded_assets"]:
            raise ContentValidationError(f"asset {asset_id} has not been uploaded")
        path = self._asset_path(draft_id, asset_id)
        if not path.is_file():
            raise ContentValidationError(f"asset file {asset_id} is missing")
        return path

    def update(self, value: dict[str, Any]) -> None:
        with self._lock:
            value["updated_at"] = utc_now()
            write_json_atomic(self._metadata_path_checked(value["draft_id"]), value)

    def _next_version(self, content_id: str) -> str:
        registry = read_json(self.registry_path)
        versions: list[int] = []
        for entry in registry.get("contents", []):
            if entry.get("content_id") != content_id:
                continue
            raw = entry.get("content_version", "")
            if isinstance(raw, str) and raw.startswith("v") and raw[1:].isdigit():
                versions.append(int(raw[1:]))
        for directory in self.root.iterdir():
            metadata = directory / "draft.json"
            if not metadata.is_file():
                continue
            try:
                draft = read_json(metadata)
            except ContentValidationError:
                continue
            if draft.get("content", {}).get("content_id") != content_id:
                continue
            raw = draft.get("content_version", "")
            if draft.get("state") == "draft" and isinstance(raw, str) and raw.startswith("v") and raw[1:].isdigit():
                versions.append(int(raw[1:]))
        return f"v{max(versions, default=0) + 1}"

    def _metadata_path_checked(self, draft_id: str) -> Path:
        try:
            uuid.UUID(draft_id)
        except ValueError as error:
            raise ContentValidationError("draft_id is invalid") from error
        path = self._metadata_path(draft_id)
        if not path.is_file():
            raise ContentValidationError("draft was not found")
        return path

    def _metadata_path(self, draft_id: str) -> Path:
        return self.root / draft_id / "draft.json"

    def _asset_path(self, draft_id: str, asset_id: str) -> Path:
        return self.root / draft_id / "assets" / asset_id


def public_draft(value: dict[str, Any]) -> dict[str, Any]:
    descriptors = value["content"]["assets"]
    uploaded = value.get("uploaded_assets", {})
    return {
        "draft_id": value["draft_id"],
        "state": value["state"],
        "content_version": value["content_version"],
        "content": value["content"],
        "assets": [
            {
                **descriptor,
                "upload_status": "complete" if descriptor["asset_id"] in uploaded else "pending",
                "upload": uploaded.get(descriptor["asset_id"]),
            }
            for descriptor in descriptors
        ],
        "manifest": value.get("manifest"),
        "created_at": value["created_at"],
        "updated_at": value["updated_at"],
    }

