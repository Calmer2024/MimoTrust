import asyncio

from app.trust.pipeline_v2.retrieval import RetrievalTask, execute_retrieval_tasks
from app.trust.pipeline_v2.search_providers import ProviderPayload


class DelayedProvider:
    name = "exa"

    async def search(self, query: str, limit: int) -> ProviderPayload:
        await asyncio.sleep(0.03 if query == "slow" else 0.001)
        return ProviderPayload(
            http_status=200,
            content_type="application/json",
            data={"results": [{"title": query, "url": f"https://example.com/{query}"}]},
            result_count=1,
        )


class StartedProvider:
    name = "exa"

    def __init__(self) -> None:
        self.started: list[float] = []

    async def search(self, query: str, limit: int) -> ProviderPayload:
        self.started.append(asyncio.get_running_loop().time())
        return ProviderPayload(200, "application/json", {"results": []}, 0)


def _task(task_id: str, query_id: str, query: str) -> RetrievalTask:
    return RetrievalTask(
        task_id=task_id,
        query_id=query_id,
        verification_ids=("V1",),
        channel="web",
        provider="exa",
        query=query,
        limit=5,
        timeout_seconds=1,
    )


def test_retrieval_emits_completed_batches_without_changing_saved_order() -> None:
    emitted: list[str] = []

    async def run() -> list[dict]:
        return await execute_retrieval_tasks(
            [_task("T1", "Q1", "slow"), _task("T2", "Q2", "fast")],
            {"exa": DelayedProvider()},
            result_callback=lambda outcome: emitted.append(outcome["查询文本"]),
            start_stagger_ms=0,
        )

    outcomes = asyncio.run(run())

    assert emitted == ["fast", "slow"]
    assert [outcome["查询文本"] for outcome in outcomes] == ["slow", "fast"]


def test_retrieval_can_stagger_request_starts_without_serializing_results() -> None:
    provider = StartedProvider()

    async def run() -> None:
        await execute_retrieval_tasks(
            [_task("T1", "Q1", "one"), _task("T2", "Q2", "two")],
            {"exa": provider},
            start_stagger_ms=20,
        )

    asyncio.run(run())

    assert len(provider.started) == 2
    assert provider.started[1] - provider.started[0] >= 0.015
