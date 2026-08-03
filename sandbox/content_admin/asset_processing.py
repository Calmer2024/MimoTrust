from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any, BinaryIO

from .manifest_builder import ContentValidationError, TEXT_MIME_TYPES


CHUNK_SIZE = 1024 * 1024
MAX_TEXT_BYTES = 8 * 1024 * 1024


def receive_asset(
    source: BinaryIO,
    target: Path,
    length: int,
    expected_mime: str,
    max_bytes: int,
) -> dict[str, Any]:
    if length < 1 or length > max_bytes:
        raise ContentValidationError(f"asset size must be between 1 and {max_bytes} bytes")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    remaining = length
    with temporary.open("wb") as handle:
        while remaining:
            chunk = source.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                temporary.unlink(missing_ok=True)
                raise ContentValidationError("asset upload ended before Content-Length")
            handle.write(chunk)
            remaining -= len(chunk)

    try:
        if expected_mime in TEXT_MIME_TYPES:
            _normalize_utf8_text(temporary)
        detected = detect_mime(temporary)
        if not mime_matches(expected_mime, detected):
            raise ContentValidationError(
                f"uploaded bytes are {detected}, expected {expected_mime}"
            )
        metadata = digest_file(temporary)
        metadata["mime_type"] = expected_mime
        metadata.update(probe_asset(temporary, expected_mime))
        _require_expected_media_stream(metadata, expected_mime)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(target)
    return metadata


def _normalize_utf8_text(path: Path) -> None:
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise ContentValidationError(f"text assets cannot exceed {MAX_TEXT_BYTES} bytes")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ContentValidationError("text assets must use UTF-8") from error
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    path.write_text(normalized, encoding="utf-8", newline="\n")


def digest_file(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"sha256": digest.hexdigest(), "size_bytes": size}


def detect_mime(path: Path) -> str:
    with path.open("rb") as handle:
        sample = handle.read(4096)
    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if sample.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if sample.startswith(b"RIFF") and sample[8:12] == b"WEBP":
        return "image/webp"
    if len(sample) >= 12 and sample[4:8] == b"ftyp":
        brand = sample[8:12]
        return "audio/mp4" if brand in {b"M4A ", b"M4B ", b"M4P "} else "video/mp4"
    if sample.startswith(b"ID3") or (len(sample) >= 2 and sample[0] == 0xFF and sample[1] & 0xE0 == 0xE0):
        return "audio/mpeg"
    try:
        text = sample.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "application/octet-stream"
    if text.startswith("WEBVTT"):
        return "text/vtt"
    return "text/plain"


def mime_matches(expected: str, detected: str) -> bool:
    if expected == detected:
        return True
    if {expected, detected} <= {"text/plain", "text/markdown"}:
        return True
    return {expected, detected} <= {"audio/mp4", "audio/x-m4a", "video/mp4"}


def _require_expected_media_stream(metadata: dict[str, Any], mime_type: str) -> None:
    if shutil.which("ffprobe") is None:
        return
    if mime_type.startswith("video/") and "video_codec" not in metadata:
        raise ContentValidationError("the uploaded MP4 does not contain a video stream")
    if mime_type.startswith("audio/") and "audio_codec" not in metadata:
        raise ContentValidationError("the uploaded audio file does not contain an audio stream")


def probe_asset(path: Path, mime_type: str) -> dict[str, Any]:
    if mime_type == "image/png":
        return _png_dimensions(path)
    if mime_type == "image/jpeg":
        return _jpeg_dimensions(path)
    if mime_type.startswith(("video/", "audio/")):
        return _ffprobe(path)
    return {}


def _png_dimensions(path: Path) -> dict[str, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24:
        raise ContentValidationError("PNG header is incomplete")
    width, height = struct.unpack(">II", header[16:24])
    return {"width": width, "height": height}


def _jpeg_dimensions(path: Path) -> dict[str, int]:
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            raise ContentValidationError("JPEG header is invalid")
        while True:
            marker_start = handle.read(1)
            if not marker_start:
                break
            if marker_start != b"\xff":
                continue
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if marker in {bytes([value]) for value in range(0xC0, 0xC4)} | {
                bytes([value]) for value in range(0xC5, 0xC8)
            } | {bytes([value]) for value in range(0xC9, 0xCC)} | {
                bytes([value]) for value in range(0xCD, 0xD0)
            }:
                length = struct.unpack(">H", handle.read(2))[0]
                data = handle.read(length - 2)
                if len(data) >= 5:
                    height, width = struct.unpack(">HH", data[1:5])
                    return {"width": width, "height": height}
                break
            raw_length = handle.read(2)
            if len(raw_length) != 2:
                break
            length = struct.unpack(">H", raw_length)[0]
            handle.seek(max(length - 2, 0), 1)
    raise ContentValidationError("JPEG dimensions could not be read")


def _ffprobe(path: Path) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if executable is None:
        return {}
    command = [
        executable,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=True)
        value = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        raise ContentValidationError(f"ffprobe could not inspect {path.name}") from error
    result: dict[str, Any] = {}
    duration = value.get("format", {}).get("duration")
    if duration:
        result["duration_ms"] = max(1, round(float(duration) * 1000))
    for stream in value.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video":
            if stream.get("width"):
                result["width"] = int(stream["width"])
            if stream.get("height"):
                result["height"] = int(stream["height"])
            if stream.get("codec_name"):
                result["video_codec"] = str(stream["codec_name"])
            frame_rate = stream.get("avg_frame_rate")
            if frame_rate and frame_rate != "0/0":
                numerator, denominator = frame_rate.split("/", 1)
                if float(denominator):
                    result["frame_rate"] = round(float(numerator) / float(denominator), 3)
        elif codec_type == "audio" and stream.get("codec_name"):
            result["audio_codec"] = str(stream["codec_name"])
    return result
