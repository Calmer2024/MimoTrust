from __future__ import annotations

import asyncio
import json
from typing import Any

import boto3

from app.config import settings


async def store_job_artifacts(
    job_id: str,
    analysis: dict[str, Any],
    report_markdown: str,
) -> str | None:
    """Persist structured analysis/keyframe metadata and the audit report."""
    if not settings.s3_endpoint_url:
        return None

    def upload() -> str:
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        try:
            client.head_bucket(Bucket=settings.s3_bucket)
        except Exception:
            client.create_bucket(Bucket=settings.s3_bucket)
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=f"jobs/{job_id}/analysis.json",
            Body=json.dumps(analysis, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        if report_markdown:
            client.put_object(
                Bucket=settings.s3_bucket,
                Key=f"jobs/{job_id}/report.md",
                Body=report_markdown.encode("utf-8"),
                ContentType="text/markdown; charset=utf-8",
            )
        return f"/v1/jobs/{job_id}/report"

    return await asyncio.to_thread(upload)
