"""One-command orchestration for the seven independently testable modules."""

from __future__ import annotations

import time
from collections import Counter
from inspect import isawaitable
from pathlib import Path
from typing import Any, Awaitable, Callable

from .config import env_int
from .evidence import run_m4_case
from .evidence_triage import run_m5_case
from .pipeline_metrics import build_pipeline_metrics
from .planning import run_m2_case
from .rendering import run_m7_case
from .retrieval import run_m3_case
from .synthesis import SynthesisValidationError, run_m6_case
from .workspace import CaseRunWorkspace, run_m1_case


ProgressCallback = Callable[[str], None | Awaitable[None]]
StreamCallback = Callable[[str, str], None | Awaitable[None]]
ProductCallback = Callable[[dict[str, Any]], None | Awaitable[None]]


async def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is None:
        return
    result = progress(message)
    if isawaitable(result):
        await result


async def _emit_stream(
    callback: StreamCallback | None, kind: str, text: str
) -> None:
    if callback is None or not text:
        return
    result = callback(kind, text)
    if isawaitable(result):
        await result


async def _emit_product(
    callback: ProductCallback | None, payload: dict[str, Any]
) -> None:
    if callback is None:
        return
    result = callback(payload)
    if isawaitable(result):
        await result


async def run_full_pipeline(
    cases_root: Path,
    case_id: str,
    run_id: str | None = None,
    *,
    planning_model: str,
    triage_model: str,
    report_model: str,
    report_thinking: str,
    planning_thinking: str = "disabled",
    triage_thinking: str = "disabled",
    retrieval_timeout_seconds: float = 10.0,
    progress: ProgressCallback | None = None,
    stream: StreamCallback | None = None,
    product: ProductCallback | None = None,
) -> tuple[CaseRunWorkspace, dict]:
    """Run M1-M7 in order while retaining every module's normal artifacts."""

    started = time.perf_counter()
    await _emit(progress, "M1 输入规范化与稳定编号")
    workspace, claims = run_m1_case(cases_root, case_id, run_id)
    resolved_run_id = workspace.run_id
    await _emit_product(product, _claims_product(claims))

    await _emit(progress, "M2 检索规划与核验需求")
    _, plan = await run_m2_case(
        cases_root,
        case_id,
        resolved_run_id,
        model=planning_model,
        thinking=planning_thinking,
        stream_callback=(
            lambda _kind, text: _emit_stream(stream, "m2_thinking", text)
        ) if stream and planning_thinking == "enabled" else None,
    )
    await _emit_product(product, _plan_product(plan))
    await _emit(progress, "M3 并发检索执行")
    async def emit_retrieval_batch(outcome: dict[str, Any]) -> None:
        await _emit_product(product, _retrieval_batch_product(outcome))

    _, retrieval = await run_m3_case(
        cases_root,
        case_id,
        resolved_run_id,
        timeout_seconds=retrieval_timeout_seconds,
        result_callback=emit_retrieval_batch,
    )
    await _emit_product(product, _retrieval_product(retrieval))
    await _emit(progress, "M4 证据池归一化")
    _, evidence_pool = run_m4_case(cases_root, case_id, resolved_run_id)
    await _emit_product(product, _evidence_product(evidence_pool))
    await _emit(progress, "M5 并发证据初筛")
    _, ledger = await run_m5_case(
        cases_root,
        case_id,
        resolved_run_id,
        triage_model=triage_model,
        thinking=triage_thinking,
        # M5 batches run concurrently; exposing their private token streams would
        # interleave unrelated reasoning. Publish only the completed ledger.
        stream_callback=None,
    )
    await _emit_product(product, _ledger_product(ledger, evidence_pool))
    await _emit(progress, "M6 最终研判")
    max_report_attempts = env_int("MIMO_REPORT_MAX_ATTEMPTS", 2)
    for attempt in range(1, max_report_attempts + 1):
        try:
            await run_m6_case(
                cases_root,
                case_id,
                resolved_run_id,
                report_model=report_model,
                thinking=report_thinking,
                stream_callback=(
                    lambda kind, text: _emit_stream(stream, kind, text)
                ) if stream else None,
            )
            break
        except SynthesisValidationError:
            if attempt >= max_report_attempts:
                raise
            await _emit(progress, "M6 输出未完成，复用现有证据重试")
    await _emit(progress, "M7 报告渲染")
    workspace, report = run_m7_case(cases_root, case_id, resolved_run_id)
    metrics = build_pipeline_metrics(
        workspace,
        wall_elapsed_ms=round((time.perf_counter() - started) * 1000),
    )
    workspace.write_artifact("07_pipeline_metrics.json", metrics)
    return workspace, report


def _claims_product(value: dict[str, Any]) -> dict[str, Any]:
    claims = value.get("主张") or []
    return {
        "kind": "claims",
        "title": "已理解内容",
        "summary": str(value.get("主题") or "已完成内容理解"),
        "items": [
            {
                "label": str(item.get("编号") or "主张"),
                "text": str(item.get("文本") or ""),
                "meta": str(item.get("表达") or ""),
            }
            for item in claims[:12]
            if isinstance(item, dict)
        ],
    }


def _plan_product(value: dict[str, Any]) -> dict[str, Any]:
    queries = value.get("查询") or []
    return {
        "kind": "plan",
        "title": "制定核验计划",
        "summary": f"规划了 {len(value.get('核验项') or [])} 个核验问题、{len(queries)} 项检索",
        "items": [
            {
                "label": str(item.get("编号") or "查询"),
                "text": str(item.get("文本") or ""),
                "meta": str(item.get("渠道") or ""),
            }
            for item in queries[:16]
            if isinstance(item, dict)
        ],
    }


def _retrieval_product(value: dict[str, Any]) -> dict[str, Any]:
    tasks = value.get("任务") or []
    items: list[dict[str, str]] = []
    total = 0
    for task in tasks:
        if not isinstance(task, dict):
            continue
        total += int(task.get("结果数") or 0)
        results = (task.get("原始响应") or {}).get("results") or []
        for result in results[:3]:
            if isinstance(result, dict) and len(items) < 18:
                items.append({
                    "label": str(task.get("查询编号") or "检索"),
                    "text": str(result.get("title") or result.get("url") or "公开来源"),
                    "meta": str(task.get("状态") or ""),
                    "url": str(result.get("url") or ""),
                })
    return {
        "kind": "retrieval",
        "title": "检索公开资料完成",
        "summary": f"{len(tasks)} 项检索共返回 {total} 条候选结果",
        "items": items,
    }


def _retrieval_batch_product(task: dict[str, Any]) -> dict[str, Any]:
    results = (task.get("原始响应") or {}).get("results") or []
    status = str(task.get("状态") or "已完成")
    result_count = int(task.get("结果数") or 0)
    query = str(task.get("查询文本") or "公开资料检索")
    return {
        "kind": "search_batch",
        "title": query,
        "summary": (
            f"找到 {result_count} 条相关来源"
            if status == "成功"
            else f"超过 {float(task.get('超时秒') or 0):g} 秒，已跳过，不影响其余检索"
            if status == "超时"
            else f"本项检索{status}"
        ),
        "items": [
            {
                "label": str(result.get("author") or "公开来源"),
                "text": str(result.get("title") or result.get("url") or "未命名来源"),
                "meta": _source_domain(str(result.get("url") or "")),
                "url": str(result.get("url") or ""),
            }
            for result in results[:4]
            if isinstance(result, dict)
        ],
    }


def _source_domain(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").removeprefix("www.")


def _evidence_product(value: dict[str, Any]) -> dict[str, Any]:
    evidence = value.get("证据") or []
    channels = Counter(
        str(channel)
        for item in evidence
        if isinstance(item, dict)
        for channel in (item.get("检索渠道") or [])
        if str(channel).strip()
    )
    distribution = "、".join(
        f"{name} {count} 条" for name, count in channels.most_common(4)
    )
    return {
        "kind": "evidence",
        "title": "汇总候选证据",
        "summary": (
            f"去重后保留 {len(evidence)} 条；{distribution}"
            if distribution
            else f"去重后保留 {len(evidence)} 条候选证据"
        ),
        "items": [
            {
                "label": str(item.get("证据编号") or "证据"),
                "text": str(item.get("标题") or item.get("链接") or "公开来源"),
                "meta": "、".join(str(part) for part in (item.get("检索渠道") or [])),
                "url": str(item.get("链接") or ""),
            }
            for item in evidence[:18]
            if isinstance(item, dict)
        ],
    }


def _ledger_product(
    value: dict[str, Any], evidence_pool: dict[str, Any]
) -> dict[str, Any]:
    assessments = value.get("证据判断") or []
    evidence_by_id = {
        item.get("证据编号"): item
        for item in evidence_pool.get("证据") or []
        if isinstance(item, dict)
    }
    items: list[dict[str, str]] = []
    relation_counts: Counter[str] = Counter()
    for item in assessments[:18]:
        if not isinstance(item, dict):
            continue
        identifier = item.get("证据编号")
        evidence = evidence_by_id.get(identifier) or {}
        relations = "、".join(
            f"{row.get('主张编号')}:{row.get('关系')}"
            for row in item.get("关系") or []
            if isinstance(row, dict)
        )
        for row in item.get("关系") or []:
            if isinstance(row, dict) and row.get("关系"):
                relation_counts[str(row["关系"])] += 1
        items.append({
            "label": str(identifier or "证据"),
            "text": str(item.get("关键信息") or evidence.get("标题") or "已完成关系核对"),
            "meta": relations or str(item.get("来源性质") or ""),
            "url": str(evidence.get("链接") or ""),
        })
    return {
        "kind": "triage",
        "title": "核对证据关系",
        "summary": "、".join(
            [f"已审阅 {len(assessments)} 条证据"]
            + [f"{name} {count} 条" for name, count in relation_counts.most_common()]
        ),
        "items": items,
    }
