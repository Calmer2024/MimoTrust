from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.security import UnsafeUrlError, validate_public_url


router = APIRouter(prefix="/v1/controlled-content", tags=["controlled-content"])

MAX_EXCHANGE_RESPONSE_BYTES = 2 * 1024 * 1024


class GrantExchangeRequest(BaseModel):
    exchange_url: str = Field(min_length=8, max_length=2_048)
    grant_code: str = Field(min_length=1, max_length=4_096)
    audience: str = Field(min_length=1, max_length=256)
    content_id: str = Field(min_length=1, max_length=256)
    content_version: str = Field(min_length=1, max_length=128)


async def _exchange_with_gateway(request: GrantExchangeRequest) -> dict[str, object]:
    try:
        validate_public_url(request.exchange_url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    upstream_payload = request.model_dump(exclude={"exchange_url"})
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(20),
        ) as client:
            response = await client.post(request.exchange_url, json=upstream_payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="内容授权交换超时") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="内容授权交换网络失败") from exc

    if response.is_redirect:
        raise HTTPException(status_code=502, detail="内容授权交换不接受重定向")
    if not response.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"内容授权交换失败：上游状态 {response.status_code}",
        )
    if len(response.content) > MAX_EXCHANGE_RESPONSE_BYTES:
        raise HTTPException(status_code=502, detail="内容授权交换响应过大")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="内容授权交换返回了无效 JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("manifest"), dict):
        raise HTTPException(status_code=502, detail="内容授权交换响应缺少 manifest")
    return payload


@router.post("/exchange")
async def exchange_controlled_content_grant(
    request: GrantExchangeRequest,
) -> dict[str, object]:
    """Exchange a Sandbox grant through the local service used by the device."""
    return await _exchange_with_gateway(request)
