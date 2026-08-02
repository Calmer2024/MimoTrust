"""One-command orchestration for the seven independently testable modules."""

from __future__ import annotations

import time
from inspect import isawaitable
from pathlib import Path
from typing import Awaitable, Callable

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


async def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is None:
        return
    result = progress(message)
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
    progress: ProgressCallback | None = None,
) -> tuple[CaseRunWorkspace, dict]:
    """Run M1-M7 in order while retaining every module's normal artifacts."""

    started = time.perf_counter()
    await _emit(progress, "M1 输入规范化与稳定编号")
    workspace, _ = run_m1_case(cases_root, case_id, run_id)
    resolved_run_id = workspace.run_id

    await _emit(progress, "M2 检索规划与核验需求")
    await run_m2_case(
        cases_root, case_id, resolved_run_id, model=planning_model
    )
    await _emit(progress, "M3 并发检索执行")
    await run_m3_case(cases_root, case_id, resolved_run_id)
    await _emit(progress, "M4 证据池归一化")
    run_m4_case(cases_root, case_id, resolved_run_id)
    await _emit(progress, "M5 并发证据初筛")
    await run_m5_case(
        cases_root, case_id, resolved_run_id, triage_model=triage_model
    )
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
