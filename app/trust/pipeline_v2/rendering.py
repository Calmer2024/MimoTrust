"""M7: validate and render the M6 report without semantic inference."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pipeline_metrics import build_pipeline_metrics
from .workspace import CaseRunWorkspace


RENDER_PROTOCOL_VERSION = "1"


class ReportRenderingError(ValueError):
    """Raised when saved report artifacts cannot be rendered without guessing."""


def build_presentation_report(
    claims: dict[str, Any],
    evidence_pool: dict[str, Any],
    report_draft: dict[str, Any],
) -> dict[str, Any]:
    """Join stable C/E references to display fields without changing judgments."""

    case_ids = {
        claims.get("案例编号"),
        evidence_pool.get("案例编号"),
        report_draft.get("案例编号"),
    }
    if len(case_ids) != 1 or None in case_ids:
        raise ReportRenderingError("M7 输入产物案例编号不一致")

    topic = _required_text(claims.get("主题"), "01_claims.主题")
    claim_map = _claim_map(claims)
    evidence_map = _evidence_map(evidence_pool)
    overall = _overall(report_draft.get("整体判断"), set(evidence_map))

    raw_checks = report_draft.get("主张核验")
    if not isinstance(raw_checks, list):
        raise ReportRenderingError("06_report_draft.主张核验 必须是数组")
    rendered_checks: list[dict[str, Any]] = []
    seen_claims: set[str] = set()
    cited_evidence: set[str] = set()
    for index, raw_check in enumerate(raw_checks, start=1):
        path = f"06_report_draft.主张核验[{index}]"
        if not isinstance(raw_check, dict):
            raise ReportRenderingError(f"{path} 必须是对象")
        claim_id = raw_check.get("主张编号")
        if claim_id not in claim_map or claim_id in seen_claims:
            raise ReportRenderingError(f"{path}.主张编号 无效或重复")
        seen_claims.add(claim_id)

        raw_basis = raw_check.get("依据")
        if not isinstance(raw_basis, list):
            raise ReportRenderingError(f"{path}.依据 必须是数组")
        basis: list[dict[str, Any]] = []
        seen_basis: set[str] = set()
        for basis_index, raw_item in enumerate(raw_basis, start=1):
            basis_path = f"{path}.依据[{basis_index}]"
            if not isinstance(raw_item, dict):
                raise ReportRenderingError(f"{basis_path} 必须是对象")
            evidence_id = raw_item.get("证据编号")
            if evidence_id not in evidence_map or evidence_id in seen_basis:
                raise ReportRenderingError(f"{basis_path}.证据编号 无效或重复")
            seen_basis.add(evidence_id)
            cited_evidence.add(evidence_id)
            basis.append(
                {
                    **_evidence_reference(evidence_map[evidence_id]),
                    "关系": _required_text(raw_item.get("关系"), f"{basis_path}.关系"),
                }
            )

        claim = claim_map[claim_id]
        rendered_checks.append(
            {
                "主张编号": claim_id,
                "主张文本": claim["文本"],
                "表达": claim["表达"],
                "结论": _required_text(raw_check.get("结论"), f"{path}.结论"),
                "证据充分度": _required_text(
                    raw_check.get("证据充分度"), f"{path}.证据充分度"
                ),
                "依据": basis,
                "说明": _required_text(raw_check.get("说明"), f"{path}.说明"),
                "不确定性": _optional_text(
                    raw_check.get("不确定性"), f"{path}.不确定性"
                ),
            }
        )

    missing_claims = set(claim_map) - seen_claims
    if missing_claims:
        raise ReportRenderingError(
            "06_report_draft 未覆盖主张：" + "、".join(sorted(missing_claims))
        )
    if not set(overall["关键证据"]).issubset(cited_evidence):
        raise ReportRenderingError("整体关键证据必须出现在逐主张依据中")

    narrative = _narrative(report_draft.get("叙事分析"))
    gaps = _string_list(report_draft.get("待补证据"), "06_report_draft.待补证据")
    return {
        "版本": RENDER_PROTOCOL_VERSION,
        "案例编号": claims["案例编号"],
        "主题": topic,
        "整体判断": overall,
        "主张核验": rendered_checks,
        "叙事分析": narrative,
        "待补证据": gaps,
        "关键证据": [
            _evidence_reference(evidence_map[evidence_id])
            for evidence_id in overall["关键证据"]
        ],
    }


def render_report_markdown(report: dict[str, Any]) -> str:
    """Render one validated presentation report as stable Markdown."""

    overall = report["整体判断"]
    lines = [
        f"# {_plain(report['主题'])}",
        "",
        "## 核验结论",
        "",
        f"**{_plain(overall['结论'])}**",
        "",
        _plain(overall["摘要"]),
        "",
        f"**传播建议：** {_plain(overall['传播建议'])}",
        "",
        "## 逐项核验",
    ]
    for check in report["主张核验"]:
        lines.extend(
            [
                "",
                f"### {_plain(check['主张编号'])} · {_plain(check['结论'])}",
                "",
                f"**主张：** {_plain(check['主张文本'])}",
                "",
                f"- 表达方式：{_plain(check['表达'])}",
                f"- 证据充分度：{_plain(check['证据充分度'])}",
                f"- 判断说明：{_plain(check['说明'])}",
            ]
        )
        if check["不确定性"]:
            lines.append(f"- 不确定性：{_plain(check['不确定性'])}")
        lines.extend(["", "**依据：**"])
        if check["依据"]:
            lines.extend(
                f"- {_evidence_link(item)}（{_plain(item['关系'])}）"
                for item in check["依据"]
            )
        else:
            lines.append("- 未引用具体证据。")

    narrative = report["叙事分析"]
    lines.extend(
        [
            "",
            "## 叙事分析",
            "",
            f"**{_plain(narrative['判断'])}**",
            "",
            _plain(narrative["说明"]),
        ]
    )
    if narrative["方式"]:
        lines.extend(["", "引导方式：" + "、".join(_plain(item) for item in narrative["方式"])])

    lines.extend(["", "## 待补证据", ""])
    if report["待补证据"]:
        lines.extend(f"- {_plain(item)}" for item in report["待补证据"])
    else:
        lines.append("- 无")

    lines.extend(["", "## 关键依据", ""])
    if report["关键证据"]:
        lines.extend(f"- {_evidence_link(item)}" for item in report["关键证据"])
    else:
        lines.append("- 无")
    return "\n".join(lines) + "\n"


def run_m7_case(
    cases_root: Path,
    case_id: str,
    run_id: str | None = None,
) -> tuple[CaseRunWorkspace, dict[str, Any]]:
    """Run deterministic M7 validation and rendering for one saved M6 report."""

    workspace = CaseRunWorkspace.open_existing(cases_root, case_id, run_id)
    stages = _read_run_stages(workspace)
    if stages.get("M6", {}).get("状态") != "completed":
        raise ReportRenderingError("必须先完成 M6 结构化报告")
    if stages.get("M7", {}).get("状态") == "completed":
        raise FileExistsError(f"该运行已经执行过 M7：{workspace.run_dir}")

    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    artifacts: list[str] = []
    try:
        claims_path = workspace.run_dir / "01_claims.json"
        pool_path = workspace.run_dir / "04_evidence_pool.json"
        draft_path = workspace.run_dir / "06_report_draft.json"
        claims = workspace.read_artifact("01_claims.json")
        evidence_pool = workspace.read_artifact("04_evidence_pool.json")
        report_draft = workspace.read_artifact("06_report_draft.json")

        audit = {
            "阶段": "M7",
            "版本": RENDER_PROTOCOL_VERSION,
            "案例编号": workspace.case_id,
            "来源": [
                _source_record(workspace.run_dir, path)
                for path in (claims_path, pool_path, draft_path)
            ],
            "规则": [
                "校验案例编号及全部C/E引用",
                "关联主张文本和证据展示字段",
                "不改写M6语义结论",
                "输出JSON与Markdown",
            ],
        }
        workspace.write_artifact("07_render_input.json", audit)
        artifacts.append("07_render_input.json")

        report = build_presentation_report(claims, evidence_pool, report_draft)
        markdown = render_report_markdown(report)
        workspace.write_artifact("07_report.json", report)
        artifacts.append("07_report.json")
        workspace.write_text_artifact("07_report.md", markdown)
        artifacts.append("07_report.md")

        metrics = {
            "阶段": "M7",
            "记录时间": datetime.now(timezone.utc).isoformat(),
            "耗时毫秒": _elapsed_ms(started),
            "主张数": len(report["主张核验"]),
            "引用证据数": len(
                {
                    item["证据编号"]
                    for check in report["主张核验"]
                    for item in check["依据"]
                }
            ),
            "JSON字节数": len(
                (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            ),
            "Markdown字符数": len(markdown),
        }
        workspace.write_artifact("07_render_metrics.json", metrics)
        artifacts.append("07_render_metrics.json")
        pipeline_metrics = build_pipeline_metrics(
            workspace, m7_elapsed_ms=_elapsed_ms(started)
        )
        workspace.write_artifact("07_pipeline_metrics.json", pipeline_metrics)
        artifacts.append("07_pipeline_metrics.json")
    except Exception as error:
        workspace.record_stage(
            "M7",
            "failed",
            started_at,
            _elapsed_ms(started),
            artifacts,
            str(error),
        )
        raise

    workspace.record_stage(
        "M7",
        "completed",
        started_at,
        _elapsed_ms(started),
        artifacts,
        metrics={
            "主张数": metrics["主张数"],
            "引用证据数": metrics["引用证据数"],
            "Markdown字符数": metrics["Markdown字符数"],
        },
    )
    workspace.mark_latest_stage("M7")
    return workspace, report


def _claim_map(claims: Any) -> dict[str, dict[str, str]]:
    if not isinstance(claims, dict) or not isinstance(claims.get("主张"), list):
        raise ReportRenderingError("01_claims.json 结构不合法")
    output: dict[str, dict[str, str]] = {}
    for index, item in enumerate(claims["主张"], start=1):
        path = f"01_claims.主张[{index}]"
        if not isinstance(item, dict):
            raise ReportRenderingError(f"{path} 必须是对象")
        claim_id = _required_text(item.get("编号"), f"{path}.编号")
        if claim_id in output:
            raise ReportRenderingError(f"{path}.编号 重复")
        output[claim_id] = {
            "文本": _required_text(item.get("文本"), f"{path}.文本"),
            "表达": _required_text(item.get("表达"), f"{path}.表达"),
        }
    if not output:
        raise ReportRenderingError("01_claims.主张 不得为空")
    return output


def _evidence_map(evidence_pool: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(evidence_pool, dict) or not isinstance(
        evidence_pool.get("证据"), list
    ):
        raise ReportRenderingError("04_evidence_pool.json 结构不合法")
    output: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(evidence_pool["证据"], start=1):
        path = f"04_evidence_pool.证据[{index}]"
        if not isinstance(item, dict):
            raise ReportRenderingError(f"{path} 必须是对象")
        evidence_id = _required_text(item.get("证据编号"), f"{path}.证据编号")
        if evidence_id in output:
            raise ReportRenderingError(f"{path}.证据编号 重复")
        output[evidence_id] = item
    return output


def _overall(value: Any, evidence_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportRenderingError("06_report_draft.整体判断 必须是对象")
    key_ids = value.get("关键证据")
    if not isinstance(key_ids, list):
        raise ReportRenderingError("06_report_draft.整体判断.关键证据 必须是数组")
    normalized_ids: list[str] = []
    for evidence_id in key_ids:
        if evidence_id not in evidence_ids or evidence_id in normalized_ids:
            raise ReportRenderingError("整体判断.关键证据 包含无效或重复证据编号")
        normalized_ids.append(evidence_id)
    return {
        "结论": _required_text(value.get("结论"), "整体判断.结论"),
        "传播建议": _required_text(value.get("传播建议"), "整体判断.传播建议"),
        "摘要": _required_text(value.get("摘要"), "整体判断.摘要"),
        "关键证据": normalized_ids,
    }


def _narrative(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportRenderingError("06_report_draft.叙事分析 必须是对象")
    return {
        "判断": _required_text(value.get("判断"), "叙事分析.判断"),
        "方式": _string_list(value.get("方式"), "叙事分析.方式"),
        "说明": _required_text(value.get("说明"), "叙事分析.说明"),
    }


def _evidence_reference(item: dict[str, Any]) -> dict[str, Any]:
    evidence_id = item["证据编号"]
    title = _optional_text(item.get("标题"), f"{evidence_id}.标题")
    return {
        "证据编号": evidence_id,
        "标题": title or "未命名来源",
        "链接": _required_text(item.get("链接"), f"{evidence_id}.链接"),
        "发布日期": _optional_text(
            item.get("发布日期"), f"{evidence_id}.发布日期"
        ),
        "作者": _optional_text(item.get("作者"), f"{evidence_id}.作者"),
        "摘要": " ".join(_string_list(item.get("摘要") or [], f"{evidence_id}.摘要"))[:500],
    }


def _required_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReportRenderingError(f"{path} 必须是非空字符串")
    return value.strip()


def _optional_text(value: Any, path: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ReportRenderingError(f"{path} 必须是字符串或 null")
    return value.strip()


def _string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise ReportRenderingError(f"{path} 必须是数组")
    output: list[str] = []
    for index, item in enumerate(value, start=1):
        text = _required_text(item, f"{path}[{index}]")
        if text not in output:
            output.append(text)
    return output


def _evidence_link(item: dict[str, Any]) -> str:
    title = _markdown_label(f"{item['证据编号']} · {item['标题']}")
    url = str(item["链接"]).replace(" ", "%20").replace("(", "%28").replace(")", "%29")
    return f"[{title}]({url})"


def _markdown_label(value: str) -> str:
    return _plain(value).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _plain(value: Any) -> str:
    return " ".join(str(value).split())


def _source_record(run_dir: Path, path: Path) -> dict[str, Any]:
    return {
        "文件": path.relative_to(run_dir).as_posix(),
        "SHA256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _read_run_stages(workspace: CaseRunWorkspace) -> dict[str, Any]:
    try:
        record = workspace.read_artifact("run.json")
    except (OSError, json.JSONDecodeError):
        return {}
    stages = record.get("阶段")
    return stages if isinstance(stages, dict) else {}


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
