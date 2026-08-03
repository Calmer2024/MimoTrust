"""M4: deterministically normalize raw retrieval output into an evidence pool."""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .workspace import CaseRunWorkspace


EVIDENCE_PROTOCOL_VERSION = "1"
_TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref_src",
}


class EvidenceNormalizationError(ValueError):
    """Raised when an M3 artifact cannot be normalized deterministically."""


def normalize_url(value: Any) -> str | None:
    """Return a conservative canonical HTTP(S) URL for exact deduplication."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parts = urlsplit(value.strip())
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return None
        if parts.username or parts.password:
            return None
        hostname = parts.hostname.encode("idna").decode("ascii").lower()
        if ":" in hostname:
            hostname = f"[{hostname}]"
        port = parts.port
    except (UnicodeError, ValueError):
        return None

    scheme = parts.scheme.lower()
    default_port = (scheme == "http" and port == 80) or (
        scheme == "https" and port == 443
    )
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    query_items = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in _TRACKING_PARAMETERS
    ]
    return urlunsplit(
        (scheme, netloc, parts.path or "/", urlencode(query_items), "")
    )


def validate_retrieval_artifact(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceNormalizationError("03_retrieval.json 必须是对象")
    case_id = value.get("案例编号")
    tasks = value.get("任务")
    if not isinstance(case_id, str) or not case_id.strip():
        raise EvidenceNormalizationError("检索结果.案例编号 必须是非空字符串")
    if not isinstance(tasks, list):
        raise EvidenceNormalizationError("检索结果.任务 必须是数组")
    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise EvidenceNormalizationError(f"任务[{index}] 必须是对象")
        for field in ("任务编号", "查询编号", "渠道", "提供方"):
            if not isinstance(task.get(field), str) or not task[field].strip():
                raise EvidenceNormalizationError(
                    f"任务[{index}].{field} 必须是非空字符串"
                )
        if not isinstance(task.get("关联核验项"), list):
            raise EvidenceNormalizationError(
                f"任务[{index}].关联核验项 必须是数组"
            )
    return value


def build_evidence_pool(
    retrieval: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Extract compact evidence records and merge exact canonical-URL duplicates."""

    validate_retrieval_artifact(retrieval)
    evidence_by_url: dict[str, dict[str, Any]] = {}
    counters: Counter[str] = Counter()

    for task in retrieval["任务"]:
        raw_response = task.get("原始响应")
        results = raw_response.get("results") if isinstance(raw_response, dict) else []
        if not isinstance(results, list):
            counters["响应格式异常数"] += 1
            continue
        for result in results:
            counters["原始结果数"] += 1
            if not isinstance(result, dict):
                counters["结果格式异常数"] += 1
                continue
            canonical_url = normalize_url(result.get("url"))
            if canonical_url is None:
                counters["无效链接数"] += 1
                continue

            existing = evidence_by_url.get(canonical_url)
            if existing is None:
                existing = {
                    "证据编号": f"E{len(evidence_by_url) + 1}",
                    "标题": _optional_text(result.get("title")),
                    "链接": canonical_url,
                    "发布日期": _optional_text(result.get("publishedDate")),
                    "作者": _optional_text(result.get("author")),
                    "摘要": _text_list(result.get("highlights")),
                    "来源任务": [],
                    "来源查询": [],
                    "关联核验项": [],
                    "检索渠道": [],
                    "提供方": [],
                }
                evidence_by_url[canonical_url] = existing
            else:
                counters["URL重复合并数"] += 1
                _fill_missing(existing, "标题", result.get("title"))
                _fill_missing(existing, "发布日期", result.get("publishedDate"))
                _fill_missing(existing, "作者", result.get("author"))
                _extend_unique(existing["摘要"], _text_list(result.get("highlights")))

            _append_unique(existing["来源任务"], task["任务编号"])
            _append_unique(existing["来源查询"], task["查询编号"])
            _extend_unique(existing["关联核验项"], task["关联核验项"])
            _append_unique(existing["检索渠道"], task["渠道"])
            _append_unique(existing["提供方"], task["提供方"])

    evidence = list(evidence_by_url.values())
    metrics = {
        "原始结果数": counters["原始结果数"],
        "响应格式异常数": counters["响应格式异常数"],
        "结果格式异常数": counters["结果格式异常数"],
        "无效链接数": counters["无效链接数"],
        "URL重复合并数": counters["URL重复合并数"],
        "有效结果数": counters["原始结果数"]
        - counters["结果格式异常数"]
        - counters["无效链接数"],
        "证据数": len(evidence),
    }
    return {
        "版本": EVIDENCE_PROTOCOL_VERSION,
        "案例编号": retrieval["案例编号"],
        "证据": evidence,
    }, metrics


def run_m4_case(
    cases_root: Path,
    case_id: str,
    run_id: str | None = None,
) -> tuple[CaseRunWorkspace, dict[str, Any]]:
    """Run M4 from the saved M3 artifact and persist compact audit artifacts."""

    workspace = CaseRunWorkspace.open_existing(cases_root, case_id, run_id)
    if "M4" in _read_run_stages(workspace):
        raise FileExistsError(f"该运行已经执行过 M4：{workspace.run_dir}")

    started_at = datetime.now(timezone.utc)
    stage_started = time.perf_counter()
    artifacts: list[str] = []
    try:
        source_path = workspace.run_dir / "03_retrieval.json"
        source_bytes = source_path.read_bytes()
        retrieval = validate_retrieval_artifact(
            json.loads(source_bytes.decode("utf-8"))
        )
        if retrieval["案例编号"] != workspace.case_id:
            raise EvidenceNormalizationError("检索结果案例编号与运行目录不一致")

        input_artifact = {
            "版本": EVIDENCE_PROTOCOL_VERSION,
            "案例编号": workspace.case_id,
            "来源文件": "03_retrieval.json",
            "来源文件SHA256": hashlib.sha256(source_bytes).hexdigest(),
            "任务摘要": [_task_summary(task) for task in retrieval["任务"]],
            "规则": {
                "去重键": "规范化URL",
                "移除URL片段": True,
                "移除跟踪参数": True,
                "同标题不同URL合并": False,
                "语义判断": False,
            },
        }
        workspace.write_artifact("04_normalization_input.json", input_artifact)
        artifacts.append("04_normalization_input.json")

        evidence_pool, counters = build_evidence_pool(retrieval)
        workspace.write_artifact("04_evidence_pool.json", evidence_pool)
        artifacts.append("04_evidence_pool.json")

        metrics = {
            "阶段": "M4",
            "记录时间": datetime.now(timezone.utc).isoformat(),
            "总耗时毫秒": _elapsed_ms(stage_started),
            "任务总数": len(retrieval["任务"]),
            **counters,
        }
        workspace.write_artifact("04_normalization_metrics.json", metrics)
        artifacts.append("04_normalization_metrics.json")
    except Exception as error:
        workspace.record_stage(
            "M4",
            "failed",
            started_at,
            _elapsed_ms(stage_started),
            artifacts,
            str(error),
        )
        raise

    workspace.record_stage(
        "M4",
        "completed",
        started_at,
        _elapsed_ms(stage_started),
        artifacts,
        metrics={
            "原始结果数": metrics.get("原始结果数", 0),
            "证据数": metrics.get("证据数", 0),
            "URL重复合并数": metrics.get("URL重复合并数", 0),
        },
    )
    workspace.mark_latest_stage("M4")
    return workspace, evidence_pool


def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "任务编号": task["任务编号"],
        "查询编号": task["查询编号"],
        "关联核验项": task["关联核验项"],
        "渠道": task["渠道"],
        "提供方": task["提供方"],
        "状态": task.get("状态"),
        "报告结果数": task.get("结果数"),
    }


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        text = _optional_text(item)
        if text is not None:
            _append_unique(output, text)
    return output


def _fill_missing(target: dict[str, Any], field: str, value: Any) -> None:
    if target[field] is None:
        target[field] = _optional_text(value)


def _append_unique(target: list[Any], value: Any) -> None:
    if value not in target:
        target.append(value)


def _extend_unique(target: list[Any], values: list[Any]) -> None:
    for value in values:
        _append_unique(target, value)


def _read_run_stages(workspace: CaseRunWorkspace) -> dict[str, Any]:
    try:
        record = workspace.read_artifact("run.json")
    except (OSError, json.JSONDecodeError):
        return {}
    stages = record.get("阶段")
    return stages if isinstance(stages, dict) else {}


def _elapsed_ms(started_monotonic: float) -> int:
    return round((time.perf_counter() - started_monotonic) * 1000)
