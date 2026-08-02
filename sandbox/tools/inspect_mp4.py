#!/usr/bin/env python3
"""Read the metadata needed by MiMoTrust manifests from local MP4 files."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


CONTAINER_TYPES = {b"moov", b"trak", b"mdia", b"minf", b"stbl"}


def iter_boxes(data: bytes, start: int = 0, end: int | None = None):
    limit = len(data) if end is None else end
    offset = start
    while offset + 8 <= limit:
        size, box_type = struct.unpack_from(">I4s", data, offset)
        header_size = 8
        if size == 1:
            if offset + 16 > limit:
                return
            size = struct.unpack_from(">Q", data, offset + 8)[0]
            header_size = 16
        elif size == 0:
            size = limit - offset
        if size < header_size or offset + size > limit:
            return
        yield box_type, offset + header_size, offset + size
        offset += size


def find_boxes(data: bytes, wanted: bytes, start: int = 0, end: int | None = None):
    def walk(start: int, end: int):
        for box_type, payload_start, box_end in iter_boxes(data, start, end):
            if box_type == wanted:
                yield payload_start, box_end
            if box_type in CONTAINER_TYPES:
                yield from walk(payload_start, box_end)

    yield from walk(start, len(data) if end is None else end)


def movie_duration_ms(data: bytes) -> int:
    payload_start, _ = next(find_boxes(data, b"mvhd"))
    version = data[payload_start]
    if version == 1:
        timescale = struct.unpack_from(">I", data, payload_start + 20)[0]
        duration = struct.unpack_from(">Q", data, payload_start + 24)[0]
    else:
        timescale = struct.unpack_from(">I", data, payload_start + 12)[0]
        duration = struct.unpack_from(">I", data, payload_start + 16)[0]
    if not timescale:
        raise ValueError("MP4 mvhd timescale is zero")
    return round(duration * 1000 / timescale)


def media_header_duration_ms(data: bytes, payload_start: int) -> int | None:
    version = data[payload_start]
    if version == 1:
        timescale = struct.unpack_from(">I", data, payload_start + 20)[0]
        duration = struct.unpack_from(">Q", data, payload_start + 24)[0]
    else:
        timescale = struct.unpack_from(">I", data, payload_start + 12)[0]
        duration = struct.unpack_from(">I", data, payload_start + 16)[0]
    return round(duration * 1000 / timescale) if timescale else None


def tracks(data: bytes) -> list[dict[str, object]]:
    result = []
    for track_start, track_end in find_boxes(data, b"trak"):
        handler_start, _ = next(find_boxes(data, b"hdlr", track_start, track_end))
        handler_type = data[handler_start + 8 : handler_start + 12].decode("ascii")
        media_header_start, _ = next(find_boxes(data, b"mdhd", track_start, track_end))
        result.append(
            {
                "type": handler_type,
                "duration_ms": media_header_duration_ms(data, media_header_start),
            }
        )
    return result


def track_durations_ms(data: bytes) -> list[int]:
    durations = []
    for payload_start, _ in find_boxes(data, b"mdhd"):
        duration = media_header_duration_ms(data, payload_start)
        if duration is not None:
            durations.append(duration)
    return durations


def track_dimensions(data: bytes) -> tuple[int, int]:
    dimensions: list[tuple[int, int]] = []
    for payload_start, _ in find_boxes(data, b"tkhd"):
        version = data[payload_start]
        matrix_end = payload_start + (88 if version == 1 else 76)
        width_fixed, height_fixed = struct.unpack_from(">II", data, matrix_end)
        width, height = width_fixed >> 16, height_fixed >> 16
        if width and height:
            dimensions.append((width, height))
    if not dimensions:
        raise ValueError("MP4 has no visual track dimensions")
    return max(dimensions, key=lambda item: item[0] * item[1])


def codecs(data: bytes) -> list[str]:
    known = {
        b"avc1": "H.264",
        b"avc3": "H.264",
        b"hvc1": "H.265",
        b"hev1": "H.265",
        b"mp4a": "MP4A",
    }
    result = []
    for marker, label in known.items():
        if marker in data and label not in result:
            result.append(label)
    return result


def inspect(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    width, height = track_dimensions(data)
    detected_codecs = codecs(data)
    track_durations = track_durations_ms(data)
    detected_tracks = tracks(data)
    video_duration = next(
        (track["duration_ms"] for track in detected_tracks if track["type"] == "vide"),
        None,
    )
    return {
        "path": str(path),
        "size_bytes": len(data),
        "duration_ms": video_duration or movie_duration_ms(data),
        "movie_duration_ms": movie_duration_ms(data),
        "track_durations_ms": track_durations,
        "tracks": detected_tracks,
        "width": width,
        "height": height,
        "codecs": detected_codecs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([inspect(path) for path in args.files], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
