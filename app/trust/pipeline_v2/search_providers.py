"""Provider adapters for M3 raw retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from .config import env_bool, env_choice, env_text


EXA_SEARCH_URL = "https://api.exa.ai/search"


@dataclass(frozen=True)
class ProviderPayload:
    """One provider-native response plus minimal execution metadata."""

    http_status: int
    content_type: str
    data: Any
    result_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, limit: int) -> ProviderPayload:
        """Execute one query and return the provider-native response."""


class ExaProvider:
    name = "exa"

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        *,
        search_url: str | None = None,
        search_type: str | None = None,
        user_location: str | None = None,
        include_highlights: bool | None = None,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.search_url = search_url or env_text("EXA_SEARCH_URL", EXA_SEARCH_URL)
        self.search_type = search_type or env_choice(
            "EXA_SEARCH_TYPE",
            "auto",
            {"auto", "fast", "instant", "deep-lite", "deep", "deep-reasoning"},
        )
        self.user_location = user_location or env_text("EXA_USER_LOCATION", "CN")
        self.include_highlights = (
            env_bool("EXA_INCLUDE_HIGHLIGHTS", True)
            if include_highlights is None
            else include_highlights
        )

    async def search(self, query: str, limit: int) -> ProviderPayload:
        if not self.api_key:
            raise RuntimeError("未设置 EXA_API_KEY")
        response = await self.client.post(
            self.search_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "query": query,
                "type": self.search_type,
                "numResults": limit,
                "userLocation": self.user_location,
                **(
                    {"contents": {"highlights": True}}
                    if self.include_highlights
                    else {}
                ),
            },
        )
        response.raise_for_status()
        payload = response.json()
        cost = payload.get("costDollars")
        if isinstance(cost, dict):
            reported_cost = _number_or_none(cost.get("total"))
        else:
            reported_cost = _number_or_none(cost)
        return ProviderPayload(
            http_status=response.status_code,
            content_type=response.headers.get("content-type", "application/json"),
            data=payload,
            result_count=len(payload.get("results") or []),
            metadata={
                "请求编号": payload.get("requestId"),
                "搜索类型": payload.get("searchType"),
                "报告费用美元": reported_cost,
            },
        )


def _number_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
