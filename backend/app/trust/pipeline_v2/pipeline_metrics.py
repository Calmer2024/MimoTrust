"""Aggregate stage-local audit metrics into one run summary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .workspace import CaseRunWorkspace


_USAGE_FIELDS = ("输入Token", "缓存输入Token", "输出Token", "思考Token", "总Token")


def build_pipeline_metrics(
    workspace: CaseRunWorkspace,
    *,
    m7_elapsed_ms: int = 0,
    wall_elapsed_ms: int | None = None,
) -> dict[str, Any]:
    """Build a best-effort summary without changing any stage result."""

    run_record = workspace.read_artifact("run.json")
    stage_records = run_record.get("阶段") or {}
    stages: dict[str, Any] = {}
    for number in range(1, 8):
        name = f"M{number}"
        record = stage_records.get(name) or {}
        elapsed = m7_elapsed_ms if name == "M7" and not record else record.get("耗时毫秒")
        stages[name] = {
            "状态": record.get("状态", "completed" if name == "M7" else "未执行"),
            "耗时毫秒": elapsed or 0,
        }

    m6_attempt_metrics = _m6_attempt_metrics(workspace)
    if m6_attempt_metrics:
        stages["M6"]["耗时毫秒"] = sum(
            _number(item.get("调用耗时毫秒")) for item in m6_attempt_metrics
        )

    usages: list[dict[str, Any]] = []
    planning = _read_optional(workspace, "02_planning_metrics.json")
    if isinstance(planning.get("用量"), dict):
        usages.append(planning["用量"])

    m5_attempt = (stage_records.get("M5") or {}).get("指标", {}).get("尝试编号")
    if isinstance(m5_attempt, int):
        triage = _read_optional(
            workspace, f"05_attempts/A{m5_attempt:02d}/metrics.json"
        )
        usage = triage.get("用量合计")
        if isinstance(usage, dict):
            usages.append(usage)

    for synthesis in m6_attempt_metrics:
        usage = synthesis.get("用量")
        if isinstance(usage, dict):
            usages.append(usage)

    retrieval = _read_optional(workspace, "03_retrieval_metrics.json")
    summary: dict[str, Any] = {
        "版本": "1",
        "案例编号": workspace.case_id,
        "运行编号": workspace.run_id,
        "记录时间": datetime.now(timezone.utc).isoformat(),
        "阶段耗时合计毫秒": sum(item["耗时毫秒"] for item in stages.values()),
        "阶段": stages,
        "LLM调用数": _llm_call_count(workspace, stage_records),
        "M6尝试次数": len(m6_attempt_metrics),
        "LLM用量合计": {
            field: sum(_number(item.get(field)) for item in usages)
            for field in _USAGE_FIELDS
        },
        "检索": {
            "任务数": retrieval.get("任务总数", 0),
            "结果数": retrieval.get("结果总数", 0),
            "状态": retrieval.get("状态", {}),
            "Exa报告费用美元": retrieval.get("Exa报告费用美元", 0.0),
        },
    }
    if wall_elapsed_ms is not None:
        summary["全流程墙钟耗时毫秒"] = wall_elapsed_ms
    return summary


def _llm_call_count(
    workspace: CaseRunWorkspace, stage_records: dict[str, Any]
) -> int:
    count = 1 if (workspace.run_dir / "02_planning_metrics.json").is_file() else 0
    m5_attempt = (stage_records.get("M5") or {}).get("指标", {}).get("尝试编号")
    if isinstance(m5_attempt, int):
        metrics = _read_optional(
            workspace, f"05_attempts/A{m5_attempt:02d}/metrics.json"
        )
        count += int(metrics.get("批次数") or 0)
    count += len(_m6_attempt_metrics(workspace))
    return count


def _m6_attempt_metrics(workspace: CaseRunWorkspace) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for path in sorted((workspace.run_dir / "06_attempts").glob("A*/metrics.json")):
        relative = path.relative_to(workspace.run_dir).as_posix()
        value = _read_optional(workspace, relative)
        if value:
            metrics.append(value)
    return metrics


def _read_optional(workspace: CaseRunWorkspace, filename: str) -> dict[str, Any]:
    try:
        value = workspace.read_artifact(filename)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0
