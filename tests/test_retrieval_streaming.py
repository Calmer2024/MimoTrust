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
        )

    outcomes = asyncio.run(run())

    assert emitted == ["fast", "slow"]
    assert [outcome["查询文本"] for outcome in outcomes] == ["slow", "fast"]
