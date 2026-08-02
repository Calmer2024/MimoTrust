from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from sandbox.tools.validate_contracts import ContractError, validate_manifest

from .drafts import DraftRepository, read_json, utc_now, write_json_atomic
from .manifest_builder import ContentValidationError, build_manifest


class ContentPublisher:
    def __init__(self, drafts: DraftRepository, registry_path: Path, storage: Any):
        self.drafts = drafts
        self.registry_path = registry_path.resolve()
        self.registry_root = self.registry_path.parent
        self.storage = storage
        self._lock = threading.RLock()

    def publish(self, draft_id: str) -> dict[str, Any]:
        with self._lock:
            draft_record = self.drafts.get(draft_id)
            if draft_record["state"] != "draft":
                raise ContentValidationError("draft has already been published")
            draft = draft_record["content"]
            version = draft_record["content_version"]
            registry = read_json(self.registry_path)
            key = (draft["content_id"], version)
            if any(
                (entry.get("content_id"), entry.get("content_version")) == key
                for entry in registry.get("contents", [])
            ):
                raise ContentValidationError("content version already exists; create a new draft")
            missing = [
                descriptor["asset_id"]
                for descriptor in draft["assets"]
                if descriptor["asset_id"] not in draft_record["uploaded_assets"]
            ]
            if missing:
                raise ContentValidationError(f"assets are not uploaded: {', '.join(missing)}")

            # Validate the exact future URLs and Manifest before writing any OSS object.
            self.preview(draft_id)

            stored_assets: list[dict[str, Any]] = []
            for descriptor in draft["assets"]:
                asset_id = descriptor["asset_id"]
                uploaded = draft_record["uploaded_assets"][asset_id]
                path = self.drafts.asset_path(draft_id, asset_id)
                object_key = self.storage.object_key(
                    draft["content_type"],
                    draft["content_id"],
                    version,
                    asset_id,
                    uploaded["mime_type"],
                )
                location = self.storage.put_file(path, object_key, uploaded["mime_type"])
                stored_assets.append({"asset_id": asset_id, **uploaded, **location})

            manifest = build_manifest(draft, version, stored_assets)
            try:
                validate_manifest(manifest, f"draft:{draft_id}")
            except ContractError as error:
                raise ContentValidationError(f"generated Manifest is invalid: {error}") from error

            manifest_relative = f"manifests/{draft['content_id']}.{version}.json"
            manifest_path = (self.registry_root / manifest_relative).resolve()
            if self.registry_root not in manifest_path.parents:
                raise ContentValidationError("generated manifest path escapes registry")
            if manifest_path.exists():
                raise ContentValidationError("manifest file already exists")

            entries = registry.setdefault("contents", [])
            display_order = max(
                (entry.get("display_order", -1) for entry in entries if isinstance(entry, dict)),
                default=-1,
            ) + 1
            entry = {
                "content_id": draft["content_id"],
                "content_version": version,
                "content_type": draft["content_type"],
                "status": "active",
                "display_order": display_order,
                "manifest_path": manifest_relative,
                "display_metrics": draft["display_metrics"],
            }
            registry["updated_at"] = utc_now()
            entries.append(entry)

            write_json_atomic(manifest_path, manifest)
            try:
                write_json_atomic(self.registry_path, registry)
            except Exception:
                manifest_path.unlink(missing_ok=True)
                raise

            draft_record["state"] = "published"
            draft_record["published_at"] = utc_now()
            draft_record["manifest"] = manifest
            self.drafts.update(draft_record)
            return {
                "content_id": draft["content_id"],
                "content_version": version,
                "manifest_path": manifest_relative,
                "manifest": manifest,
            }

    def preview(self, draft_id: str) -> dict[str, Any]:
        with self._lock:
            draft_record = self.drafts.get(draft_id)
            if draft_record["state"] != "draft":
                if draft_record.get("manifest"):
                    return draft_record["manifest"]
                raise ContentValidationError("draft has already been published")
            draft = draft_record["content"]
            version = draft_record["content_version"]
            stored_assets: list[dict[str, Any]] = []
            for descriptor in draft["assets"]:
                asset_id = descriptor["asset_id"]
                uploaded = draft_record["uploaded_assets"].get(asset_id)
                if uploaded is None:
                    raise ContentValidationError(f"asset {asset_id} has not been uploaded")
                object_key = self.storage.object_key(
                    draft["content_type"],
                    draft["content_id"],
                    version,
                    asset_id,
                    uploaded["mime_type"],
                )
                stored_assets.append({
                    "asset_id": asset_id,
                    **uploaded,
                    **self.storage.describe(object_key),
                })
            manifest = build_manifest(draft, version, stored_assets)
            try:
                validate_manifest(manifest, f"draft:{draft_id}")
            except ContractError as error:
                raise ContentValidationError(f"generated Manifest is invalid: {error}") from error
            return manifest

    def list_contents(self) -> list[dict[str, Any]]:
        registry = read_json(self.registry_path)
        return sorted(
            [entry for entry in registry.get("contents", []) if isinstance(entry, dict)],
            key=lambda entry: entry.get("display_order", 0),
        )
