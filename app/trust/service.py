from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from app.models import StructuredInformation
from app.trust.pipeline_v2.config import env_text
from app.trust.pipeline_v2.normalization import (
    write_json_atomic,
)
from app.trust.pipeline_v2.pipeline import run_full_pipeline
from app.trust.pipeline_v2.workspace import CaseRunWorkspace


VerificationMode = Literal["speed", "quality"]
ProgressCallback = Callable[[str], None | Awaitable[None]]

_verification_lock = asyncio.Lock()
_cases_root = Path("data") / "trust" / "cases"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _case_id(payload: dict[str, Any], source_url: str | None) -> str:
    if source_url:
        digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
        return f"video-{digest}"
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"case-{digest}"


def _project_evidence(report: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for check in report.get("主张核验", []):
        if not isinstance(check, dict):
            continue
        for item in check.get("依据", []):
            if not isinstance(item, dict):
                continue
            evidence_id = str(item.get("证据编号") or "")
            if not evidence_id or evidence_id in evidence:
                continue
            evidence[evidence_id] = {
                "id": evidence_id,
                "title": str(item.get("标题") or ""),
                "url": str(item.get("链接") or ""),
                "published_date": str(item.get("发布日期") or ""),
                "author": str(item.get("作者") or ""),
                "relation": str(item.get("关系") or ""),
            }
    return list(evidence.values())


def _client_result(
    workspace: Any,
    verification_mode: VerificationMode = "speed",
) -> dict[str, Any]:
    report = _read_json(workspace.run_dir / "07_report.json")
    metrics = _read_json(workspace.run_dir / "07_pipeline_metrics.json")
    search_plan = _read_json(workspace.run_dir / "02_verification_plan.json")
    markdown = (workspace.run_dir / "07_report.md").read_text(encoding="utf-8")
    overall = report.get("整体判断") or {}
    narrative = report.get("叙事分析") or {}
    evidence = _project_evidence(report)
    checks: list[dict[str, Any]] = []
    uncertainties: list[str] = []
    for item in report.get("主张核验", []):
        if not isinstance(item, dict):
            continue
        uncertainty = str(item.get("不确定性") or "").strip()
        if uncertainty and uncertainty not in uncertainties:
            uncertainties.append(uncertainty)
        checks.append(
            {
                "claim_id": item.get("主张编号"),
                "claim": item.get("主张文本"),
                "category": item.get("表达"),
                "verdict": item.get("结论"),
                "evidence_sufficiency": item.get("证据充分度"),
                "basis": item.get("说明"),
                "uncertainty": uncertainty,
                "source_ids": [
                    source.get("证据编号")
                    for source in item.get("依据", [])
                    if isinstance(source, dict) and source.get("证据编号")
                ],
            }
        )
    for gap in report.get("待补证据", []):
        text = str(gap).strip()
        if text and text not in uncertainties:
            uncertainties.append(text)
    evidence_gaps = [
        str(gap).strip()
        for gap in report.get("待补证据", [])
        if str(gap).strip()
    ]

    raw_stages = metrics.get("阶段") or {}
    stages = {
        name: round(float((raw_stages.get(name) or {}).get("耗时毫秒") or 0) / 1000, 3)
        for name in (f"M{number}" for number in range(1, 8))
    }

    total_ms = int(
        metrics.get("全流程墙钟耗时毫秒")
        or metrics.get("阶段耗时合计毫秒")
        or 0
    )
    queries = [
        item for item in search_plan.get("查询", []) if isinstance(item, dict)
    ]
    source_ids = [
        str(value)
        for value in overall.get("关键证据", [])
        if str(value).strip()
    ]
    return {
        "status": "completed",
        "case_id": workspace.case_id,
        "run_id": workspace.run_id,
        "verification_mode": verification_mode,
        "overall_verdict": overall.get("结论", "待核实"),
        "conclusion": overall.get("摘要", ""),
        "sharing_advice": overall.get("传播建议", ""),
        "claim_checks": checks,
        "narrative_analysis": {
            "verdict": narrative.get("判断", ""),
            "methods": narrative.get("方式", []),
            "explanation": narrative.get("说明", ""),
        },
        "evidence_gaps": evidence_gaps,
        "uncertainties": uncertainties,
        "source_ids": source_ids,
        "evidence_used": evidence,
        "evidence_counts": {
            "reviewed": int((metrics.get("检索") or {}).get("结果数") or 0),
            "cited": len(evidence),
        },
        "evidence_reviewed_count": int(
            (metrics.get("检索") or {}).get("结果数") or 0
        ),
        "evidence_selected_count": len(evidence),
        "search_plan": {
            **search_plan,
            "reasoning": f"共规划 {len(queries)} 项一次性并发检索任务",
            "web_queries": [
                str(item.get("文本") or "") for item in queries
            ],
        },
        "timings": {
            "total_seconds": round(total_ms / 1000, 3),
            "stages": stages,
        },
        "usage": {
            "llm_calls": metrics.get("LLM调用数", 0),
            "llm_tokens": metrics.get("LLM用量合计", {}),
            "search": metrics.get("检索", {}),
        },
        "report_markdown": markdown,
        "report": report,
    }


def hydrate_cached_verification(
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Restore the complete client report from an existing audited run."""

    if verification.get("status") != "completed" or verification.get("report"):
        return verification
    case_id = str(verification.get("case_id") or "")
    run_id = str(verification.get("run_id") or "")
    if not case_id or not run_id:
        return verification
    try:
        workspace = CaseRunWorkspace.open_existing(_cases_root, case_id, run_id)
        mode = str(verification.get("verification_mode") or "speed")
        return _client_result(
            workspace,
            "quality" if mode == "quality" else "speed",
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return verification


async def verify_structured_information(
    structured: StructuredInformation,
    verification_mode: VerificationMode = "speed",
    *,
    source_url: str | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run the embedded M1-M7 pipeline over the native compact-claim JSON."""

    if not structured.claims:
        return {
            "status": "skipped",
            "case_id": _case_id(
                structured.model_dump(mode="json", by_alias=True), source_url
            ),
            "message": "当前内容没有需要外部事实核验的现实世界主张。",
        }
    if verification_mode not in {"speed", "quality"}:
        raise ValueError("verification_mode 必须是 speed 或 quality")

    payload = structured.model_dump(mode="json", by_alias=True)
    case_id = _case_id(payload, source_url)
    case_dir = _cases_root / case_id
    input_path = case_dir / "input.json"
    emit = progress or (lambda _: None)

    async with _verification_lock:
        case_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(input_path, payload)
        workspace, _ = await run_full_pipeline(
            _cases_root,
            case_id,
            planning_model=env_text("MIMO_PLANNING_MODEL", "mimo-v2.5"),
            triage_model=env_text("MIMO_TRIAGE_MODEL", "mimo-v2.5-pro"),
            report_model=env_text("MIMO_REPORT_MODEL", "mimo-v2.5-pro"),
            report_thinking=(
                "enabled" if verification_mode == "quality" else "disabled"
            ),
            progress=emit,
        )
    return _client_result(workspace, verification_mode)
