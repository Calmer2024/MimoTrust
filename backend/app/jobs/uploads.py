from __future__ import annotations

import json
import re
import shutil
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID, uuid4

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.config import settings
from app.content import MAX_UPLOAD_BYTES, MAX_UPLOAD_TOTAL_BYTES


class UploadBundleError(ValueError):
    pass


@dataclass(frozen=True)
class OpenUploadBundle:
    title: str
    text: str
    files: list[UploadFile]


def _upload_root() -> Path:
    return Path(settings.job_upload_dir).resolve()


def _bundle_path(bundle_id: str) -> Path:
    try:
        normalized = str(UUID(bundle_id))
    except ValueError as exc:
        raise UploadBundleError("上传材料编号无效") from exc
    return _upload_root() / normalized


async def stage_upload_bundle(
    title: str,
    text: str,
    files: list[UploadFile],
) -> str:
    if not text.strip() and not files:
        raise UploadBundleError("请至少提供文本或一个图片、音频、视频文件")
    if len(files) > 12:
        raise UploadBundleError("单次最多上传 12 个文件")

    bundle_id = str(uuid4())
    directory = _bundle_path(bundle_id)
    directory.mkdir(parents=True, exist_ok=False)
    manifest_files: list[dict[str, object]] = []
    total_bytes = 0
    try:
        for index, upload in enumerate(files, 1):
            original_name = Path(upload.filename or f"upload-{index}").name
            suffix = Path(original_name).suffix.lower()
            if not re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
                suffix = ""
            stored_name = f"{index:02d}{suffix}"
            destination = directory / stored_name
            file_bytes = 0
            with destination.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    file_bytes += len(chunk)
                    total_bytes += len(chunk)
                    if (
                        file_bytes > MAX_UPLOAD_BYTES
                        or total_bytes > MAX_UPLOAD_TOTAL_BYTES
                    ):
                        raise UploadBundleError(
                            "上传文件超过单文件 50 MB 或合计 150 MB 限制"
                        )
                    output.write(chunk)
            manifest_files.append(
                {
                    "stored_name": stored_name,
                    "filename": original_name,
                    "content_type": upload.content_type or "application/octet-stream",
                    "size": file_bytes,
                }
            )

        manifest = {
            "title": title.strip() or "手动多模态核验",
            "text": text,
            "files": manifest_files,
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        return bundle_id
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


@asynccontextmanager
async def open_upload_bundle(bundle_id: str) -> AsyncIterator[OpenUploadBundle]:
    directory = _bundle_path(bundle_id)
    manifest_path = directory / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadBundleError("上传材料不存在、已过期或清单损坏") from exc

    handles = []
    uploads: list[UploadFile] = []
    try:
        for item in manifest.get("files") or []:
            if not isinstance(item, dict):
                raise UploadBundleError("上传材料清单格式无效")
            stored_name = str(item.get("stored_name") or "")
            if not re.fullmatch(r"\d{2}(?:\.[a-z0-9]{1,10})?", stored_name):
                raise UploadBundleError("上传材料文件名无效")
            path = directory / stored_name
            handle = path.open("rb")
            handles.append(handle)
            content_type = str(
                item.get("content_type") or "application/octet-stream"
            )
            uploads.append(
                UploadFile(
                    file=handle,
                    filename=str(item.get("filename") or stored_name),
                    size=int(item.get("size") or path.stat().st_size),
                    headers=Headers({"content-type": content_type}),
                )
            )
        yield OpenUploadBundle(
            title=str(manifest.get("title") or "手动多模态核验"),
            text=str(manifest.get("text") or ""),
            files=uploads,
        )
    finally:
        for upload in uploads:
            await upload.close()
        for handle in handles:
            if not handle.closed:
                handle.close()


def cleanup_upload_bundle(bundle_id: str) -> None:
    shutil.rmtree(_bundle_path(bundle_id), ignore_errors=True)
