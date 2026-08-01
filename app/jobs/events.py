from __future__ import annotations

import asyncio
import json

from redis.asyncio import Redis

from app.jobs.models import JobEvent


class EventBus:
    async def publish(self, event: JobEvent) -> None: ...
    async def read(self, job_id: str, after: int, timeout: float = 15) -> list[JobEvent]: ...


class MemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._events: dict[str, list[JobEvent]] = {}
        self._conditions: dict[str, asyncio.Condition] = {}

    def _condition(self, job_id: str) -> asyncio.Condition:
        return self._conditions.setdefault(job_id, asyncio.Condition())

    async def publish(self, event: JobEvent) -> None:
        condition = self._condition(event.job_id)
        async with condition:
            self._events.setdefault(event.job_id, []).append(event.model_copy(deep=True))
            condition.notify_all()

    async def read(self, job_id: str, after: int, timeout: float = 15) -> list[JobEvent]:
        condition = self._condition(job_id)
        async with condition:
            ready = [item for item in self._events.get(job_id, []) if item.sequence > after]
            if ready:
                return [item.model_copy(deep=True) for item in ready]
            try:
                await asyncio.wait_for(condition.wait(), timeout=timeout)
            except TimeoutError:
                return []
            return [
                item.model_copy(deep=True)
                for item in self._events.get(job_id, [])
                if item.sequence > after
            ]


class RedisEventBus(EventBus):
    def __init__(self, redis_url: str) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    def _key(self, job_id: str) -> str:
        return f"mimotrust:job:{job_id}:events"

    async def publish(self, event: JobEvent) -> None:
        await self.redis.xadd(
            self._key(event.job_id),
            {"event": event.model_dump_json()},
            id=f"{event.sequence}-0",
            maxlen=500,
            approximate=True,
        )

    async def read(self, job_id: str, after: int, timeout: float = 15) -> list[JobEvent]:
        rows = await self.redis.xread(
            {self._key(job_id): f"{after}-0"},
            block=max(1, round(timeout * 1000)),
            count=100,
        )
        if not rows:
            return []
        return [JobEvent.model_validate_json(fields["event"]) for _, entries in rows for _, fields in entries]

