#!/usr/bin/env python3
"""Run the content admin locally with fake OSS storage for UI development."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .server import create_server
from .storage import FakeStorage


DEFAULT_TOKEN = "sandbox-local-development-token-only"
SANDBOX_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument(
        "--data",
        type=Path,
        default=SANDBOX_ROOT / "content_admin_data" / "dev",
    )
    args = parser.parse_args()
    data_root = args.data.resolve()
    registry_path = data_root / "content_registry" / "registry.json"
    if not registry_path.exists():
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "registry_version": "1.0",
                    "provider_id": "mimotrust_sandbox",
                    "updated_at": "2026-08-02T00:00:00Z",
                    "contents": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    server = create_server(
        "127.0.0.1",
        args.port,
        registry_path,
        data_root / "drafts",
        DEFAULT_TOKEN,
        "https://sandbox.mimotrust.local/content",
        storage=FakeStorage(),
    )
    print(f"sandbox content admin: http://127.0.0.1:{args.port}/admin")
    print(f"development token: {DEFAULT_TOKEN}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
