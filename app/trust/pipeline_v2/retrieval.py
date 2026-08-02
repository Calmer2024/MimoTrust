"""M3: expand a verification plan and execute raw searches concurrently."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import httpx

from .config import env_float, env_int
from .planning import ALLOWED_CHANNELS
from .search_providers import (
    ExaProvider,
    ProviderPayload,
    SearchProvider,
)
from .workspace import CaseRunWorkspace


RETRIEVAL_PROTOCOL_VERSION = "1"
_QUERY_ID_PATTERN = re.compile(r"^Q[1-9][0-9]*$")
_VERIFICATION_ID_PATTERN = re.compile(r"^V[1-9][0-9]*$")

_EXA_PROVIDER_NAME = "exa"
DEFAULT_EXA_NUM_RESULTS = 5
DEFAULT_EXA_TIMEOUT_SECONDS = 10.0


class RetrievalValidationError(ValueError):
    """Raised when a formal M2 plan cannot be executed safely."""


@dataclass(frozen=True)
class RetrievalTask:
    task_id: str
    query_id: str
    verification_ids: tuple[str, ...]
    channel: str
    provider: str
    query: str
    limit: int
    timeout_seconds: float

    def to_artifact(self) -> dict[str, Any]:
        return {
            "任务编号": self.task_id,
            "查询编号": self.query_id,
            "关联核验项": list(self.verification_ids),
            "渠道": self.channel,
            "提供方": self.provider,
            "查询文本": self.query,
            "结果上限": self.limit,
            "超时秒": self.timeout_seconds,
        }


def validate_retrieval_plan(plan: Any) -> dict[str, Any]:
    """Validate the M2-to-M3 interface without changing its semantics."""

    if not isinstance(plan, dict):
        raise RetrievalValidationError("02_verification_plan.json 必须是对象")
    case_id = plan.get("案例编号")
    if not isinstance(case_id, str) or not case_id.strip():
        raise RetrievalValidationError("检索计划.案例编号 必须是非空字符串")
    verifications = plan.get("核验项")
    queries = plan.get("查询")
    if not isinstance(verifications, list) or not verifications:
        raise RetrievalValidationError("检索计划.核验项 必须是非空数组")
    if not isinstance(queries, list) or not queries:
        raise RetrievalValidationError("检索计划.查询 必须是非空数组")

    verification_ids: set[str] = set()
    for index, item in enumerate(verifications, start=1):
        if not isinstance(item, dict):
            raise RetrievalValidationError(f"核验项[{index}] 必须是对象")
        identifier = item.get("编号")
        if not isinstance(identifier, str) or not _VERIFICATION_ID_PATTERN.fullmatch(
            identifier
        ):
            raise RetrievalValidationError(f"核验项[{index}].编号 不合法")
        if identifier in verification_ids:
            raise RetrievalValidationError(f"核验项编号重复：{identifier}")
        verification_ids.add(identifier)

    query_ids: set[str] = set()
    for index, item in enumerate(queries, start=1):
        path = f"查询[{index}]"
        if not isinstance(item, dict):
            raise RetrievalValidationError(f"{path} 必须是对象")
        identifier = item.get("编号")
        if not isinstance(identifier, str) or not _QUERY_ID_PATTERN.fullmatch(identifier):
            raise RetrievalValidationError(f"{path}.编号 不合法")
        if identifier in query_ids:
            raise RetrievalValidationError(f"查询编号重复：{identifier}")
        query_ids.add(identifier)
        channel = item.get("渠道")
        if channel not in ALLOWED_CHANNELS:
            raise RetrievalValidationError(f"{path}.渠道 不可执行：{channel}")
        text = item.get("文本")
        if not isinstance(text, str) or not text.strip():
            raise RetrievalValidationError(f"{path}.文本 必须是非空字符串")
        links = item.get("关联核验项")
        if not isinstance(links, list) or not links:
            raise RetrievalValidationError(f"{path}.关联核验项 必须是非空数组")
        unknown = {str(value) for value in links} - verification_ids
        if unknown:
            raise RetrievalValidationError(
                f"{path}.关联核验项 引用了不存在的编号：{'、'.join(sorted(unknown))}"
            )
    budget = plan.get("查询预算")
    if not isinstance(budget, int) or budget != len(queries):
        raise RetrievalValidationError("检索计划.查询预算 与查询数量不一致")
    return plan


def expand_retrieval_tasks(plan: dict[str, Any]) -> list[RetrievalTask]:
    """Map every logical query to one stable Exa task."""

    validate_retrieval_plan(plan)
    tasks: list[RetrievalTask] = []
    limit = env_int("EXA_NUM_RESULTS", DEFAULT_EXA_NUM_RESULTS)
    timeout_seconds = env_float(
        "EXA_TIMEOUT_SECONDS", DEFAULT_EXA_TIMEOUT_SECONDS, minimum=0.1
    )
    for query in plan["查询"]:
        tasks.append(
            RetrievalTask(
                task_id=f"T{len(tasks) + 1}",
                query_id=query["编号"],
                verification_ids=tuple(query["关联核验项"]),
                channel=query["渠道"],
                provider=_EXA_PROVIDER_NAME,
                query=query["文本"].strip(),
                limit=limit,
                timeout_seconds=timeout_seconds,
            )
        )
    return tasks


async def execute_retrieval_tasks(
    tasks: list[RetrievalTask],
    providers: Mapping[str, SearchProvider],
) -> list[dict[str, Any]]:
    """Execute every task concurrently while isolating timeout and provider errors."""

    return list(
        await asyncio.gather(
            *(_execute_one_task(task, providers) for task in tasks)
        )
    )


async def run_m3_case(
    cases_root: Path,
    case_id: str,
    run_id: str | None = None,
    *,
    providers: Mapping[str, SearchProvider] | None = None,
) -> tuple[CaseRunWorkspace, dict[str, Any]]:
    """Run M3 using the saved formal M2 artifact from the same immutable run."""

    workspace = CaseRunWorkspace.open_existing(cases_root, case_id, run_id)
    if "M3" in _read_run_stages(workspace):
        raise FileExistsError(f"该运行已经执行过 M3：{workspace.run_dir}")

    started_at = datetime.now(timezone.utc)
    stage_started = time.perf_counter()
    artifacts: list[str] = []
    owned_client: httpx.AsyncClient | None = None
    try:
        plan = validate_retrieval_plan(
            workspace.read_artifact("02_verification_plan.json")
        )
        if plan["案例编号"] != workspace.case_id:
            raise RetrievalValidationError("检索计划案例编号与运行目录不一致")
        tasks = expand_retrieval_tasks(plan)
        input_artifact = {
            "版本": RETRIEVAL_PROTOCOL_VERSION,
            "案例编号": workspace.case_id,
            "来源文件": "02_verification_plan.json",
            "检索计划": plan,
            "展开任务": [task.to_artifact() for task in tasks],
        }
        workspace.write_artifact("03_retrieval_input.json", input_artifact)
        artifacts.append("03_retrieval_input.json")

        resolved_providers = providers
        if resolved_providers is None:
            owned_client = httpx.AsyncClient(
                timeout=None,
                follow_redirects=True,
                headers={"User-Agent": "MimoTrust/0.1"},
            )
            resolved_providers = create_default_providers(owned_client)
        outcomes = await execute_retrieval_tasks(tasks, resolved_providers)
        retrieval = {
            "版本": RETRIEVAL_PROTOCOL_VERSION,
            "案例编号": workspace.case_id,
            "任务": outcomes,
        }
        workspace.write_artifact("03_retrieval.json", retrieval)
        artifacts.append("03_retrieval.json")

        metrics = build_retrieval_metrics(outcomes, _elapsed_ms(stage_started))
        workspace.write_artifact("03_retrieval_metrics.json", metrics)
        artifacts.append("03_retrieval_metrics.json")
    except Exception as error:
        workspace.record_stage(
            "M3",
            "failed",
            started_at,
            _elapsed_ms(stage_started),
            artifacts,
            str(error),
        )
        raise
    finally:
        if owned_client is not None:
            await owned_client.aclose()

    workspace.record_stage(
        "M3",
        "completed",
        started_at,
        _elapsed_ms(stage_started),
        artifacts,
        metrics={
            "任务总数": metrics["任务总数"],
            "结果总数": metrics["结果总数"],
            "状态": metrics["状态"],
            "Exa报告费用美元": metrics["Exa报告费用美元"],
        },
    )
    workspace.mark_latest_stage("M3")
    return workspace, retrieval


def create_default_providers(
    client: httpx.AsyncClient,
) -> dict[str, SearchProvider]:
    return {
        "exa": ExaProvider(client, os.environ.get("EXA_API_KEY", "")),
    }


def build_retrieval_metrics(
    outcomes: list[dict[str, Any]], total_elapsed_ms: int
) -> dict[str, Any]:
    statuses = Counter(item["状态"] for item in outcomes)
    provider_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"任务数": 0, "结果数": 0, "累计耗时毫秒": 0}
    )
    exa_cost = 0.0
    for item in outcomes:
        stats = provider_stats[item["提供方"]]
        stats["任务数"] += 1
        stats["结果数"] += item["结果数"]
        stats["累计耗时毫秒"] += item["耗时毫秒"]
        metadata = item.get("提供方元数据") or {}
        cost = metadata.get("报告费用美元")
        if isinstance(cost, (int, float)):
            exa_cost += float(cost)
    return {
        "阶段": "M3",
        "记录时间": datetime.now(timezone.utc).isoformat(),
        "总耗时毫秒": total_elapsed_ms,
        "任务总数": len(outcomes),
        "状态": dict(statuses),
        "结果总数": sum(item["结果数"] for item in outcomes),
        "Exa报告费用美元": round(exa_cost, 8),
        "提供方": dict(provider_stats),
    }


async def _execute_one_task(
    task: RetrievalTask, providers: Mapping[str, SearchProvider]
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started_monotonic = time.perf_counter()
    status = "成功"
    error: str | None = None
    payload: ProviderPayload | None = None
    failed_http_status: int | None = None
    failed_content_type: str | None = None
    failed_response: Any = None
    provider = providers.get(task.provider)
    try:
        if provider is None:
            raise RuntimeError(f"没有提供方适配器：{task.provider}")
        payload = await asyncio.wait_for(
            provider.search(task.query, task.limit),
            timeout=task.timeout_seconds,
        )
        if payload.result_count == 0:
            status = "无结果"
    except asyncio.TimeoutError:
        status = "超时"
        error = f"超过 {task.timeout_seconds:g} 秒任务预算"
    except httpx.HTTPStatusError as exc:
        status = "失败"
        failed_http_status = exc.response.status_code
        failed_content_type = exc.response.headers.get("content-type")
        try:
            failed_response = exc.response.json()
        except (ValueError, json.JSONDecodeError):
            failed_response = exc.response.text
        error = f"HTTPStatusError: HTTP {failed_http_status}"
    except Exception as exc:
        status = "失败"
        error = f"{type(exc).__name__}: {exc}"

    outcome: dict[str, Any] = {
        **task.to_artifact(),
        "状态": status,
        "开始时间": started_at.isoformat(),
        "结束时间": datetime.now(timezone.utc).isoformat(),
        "耗时毫秒": _elapsed_ms(started_monotonic),
        "结果数": payload.result_count if payload else 0,
        "HTTP状态": payload.http_status if payload else failed_http_status,
        "内容类型": payload.content_type if payload else failed_content_type,
        "提供方元数据": payload.metadata if payload else {},
        "原始响应": payload.data if payload else failed_response,
    }
    if error:
        outcome["错误"] = error
    return outcome


def _read_run_stages(workspace: CaseRunWorkspace) -> dict[str, Any]:
    try:
        record = workspace.read_artifact("run.json")
    except (OSError, json.JSONDecodeError):
        return {}
    stages = record.get("阶段")
    return stages if isinstance(stages, dict) else {}


def _elapsed_ms(started_monotonic: float) -> int:
    return round((time.perf_counter() - started_monotonic) * 1000)
