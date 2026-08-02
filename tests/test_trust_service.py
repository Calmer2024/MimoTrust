from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main_module
import app.trust.service as service_module
from app.models import StructuredInformation
from app.trust.service import _client_result, verify_structured_information
from app.trust.pipeline_v2.synthesis import validate_compact_report


def test_report_without_cited_evidence_cannot_publish_a_strong_verdict() -> None:
    report = validate_compact_report(
        {
            "o": ["不实", "暂不建议传播", "模型记忆声称该说法错误。", []],
            "c": [["C1", "不实", "不足", [], "未找到支持材料。", ""]],
            "n": ["存在引导", ["夸大"], "该内容可能引导读者。"],
            "g": [],
        },
        {"案例编号": "case-one", "主张": [{"编号": "C1"}]},
        {"证据": []},
    )

    assert report["整体判断"]["结论"] == "证据不足"
    assert report["主张核验"][0]["结论"] == "证据不足"
    assert report["主张核验"][0]["证据充分度"] == "不足"
    assert report["叙事分析"]["判断"] == "证据不足"
    assert report["待补证据"]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_client_result_projects_m7_audited_artifacts(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "07_report.json",
        {
            "版本": "m7-report-v1",
            "案例编号": "case-one",
            "主题": "完整报告投影测试",
            "整体判断": {
                "结论": "可信",
                "摘要": "核验完成",
                "传播建议": "可正常传播",
                "关键证据": ["E1"],
            },
            "主张核验": [
                {
                    "主张编号": "C1",
                    "主张文本": "这是一条完整的测试主张",
                    "表达": "直接",
                    "结论": "属实",
                    "证据充分度": "充分",
                    "依据": [
                        {
                            "证据编号": "E1",
                            "标题": "权威来源",
                            "链接": "https://example.com/source",
                            "关系": "支持",
                        }
                    ],
                    "说明": "原始资料直接支持。",
                    "不确定性": "",
                }
            ],
            "叙事分析": {"判断": "无明显引导", "方式": [], "说明": "无"},
            "待补证据": ["补充一手材料"],
            "关键证据": [
                {
                    "证据编号": "E1",
                    "标题": "权威来源",
                    "链接": "https://example.com/source",
                    "发布日期": "",
                    "作者": "",
                }
            ],
        },
    )
    _write_json(
        tmp_path / "07_pipeline_metrics.json",
        {
            "阶段耗时合计毫秒": 1200,
            "阶段": {"M1": {"耗时毫秒": 10}, "M7": {"耗时毫秒": 5}},
            "检索": {"结果数": 5},
        },
    )
    _write_json(
        tmp_path / "02_verification_plan.json",
        {"查询": [{"编号": "Q1", "文本": "测试查询"}]},
    )
    (tmp_path / "07_report.md").write_text("# 报告", encoding="utf-8")

    result = _client_result(
        SimpleNamespace(run_dir=tmp_path, case_id="case-one", run_id="run-one")
    )

    assert result["status"] == "completed"
    assert result["overall_verdict"] == "可信"
    assert result["claim_checks"][0]["claim_id"] == "C1"
    assert result["evidence_used"][0]["id"] == "E1"
    assert result["search_plan"]["web_queries"] == ["测试查询"]
    assert result["report"]["主题"] == "完整报告投影测试"
    assert result["report"]["待补证据"] == ["补充一手材料"]
    assert result["evidence_gaps"] == ["补充一手材料"]


def test_empty_structured_information_skips_verification() -> None:
    result = asyncio.run(
        verify_structured_information(
            StructuredInformation(主题="没有可核验主张", 主张=[])
        )
    )
    assert result["status"] == "skipped"
    assert result["case_id"].startswith("case-")
    assert result["message"] == "当前内容没有需要外部事实核验的现实世界主张。"


def test_cached_verification_restores_complete_report(monkeypatch) -> None:
    workspace = SimpleNamespace(case_id="case-one", run_id="run-one")
    monkeypatch.setattr(
        service_module.CaseRunWorkspace,
        "open_existing",
        lambda *_args: workspace,
    )
    monkeypatch.setattr(
        service_module,
        "_client_result",
        lambda _workspace, mode: {
            "status": "completed",
            "verification_mode": mode,
            "report": {"主题": "从磁盘恢复的完整报告"},
        },
    )

    restored = service_module.hydrate_cached_verification(
        {
            "status": "completed",
            "case_id": "case-one",
            "run_id": "run-one",
            "verification_mode": "quality",
        }
    )

    assert restored["verification_mode"] == "quality"
    assert restored["report"]["主题"] == "从磁盘恢复的完整报告"


def test_verification_mode_selects_all_thinking_and_retrieval_budget(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: list[dict] = []
    progress: list[str] = []

    async def fake_pipeline(cases_root, case_id, **kwargs):
        captured.append(
            {
                "case_id": case_id,
                "payload": json.loads(
                    (cases_root / case_id / "input.json").read_text(encoding="utf-8")
                ),
                **kwargs,
            }
        )
        kwargs["progress"]("M1 输入规范化与稳定编号")
        return SimpleNamespace(
            run_dir=tmp_path,
            case_id=case_id,
            run_id="run-one",
        ), {}

    monkeypatch.setattr(service_module, "_cases_root", tmp_path / "cases")
    monkeypatch.setattr(service_module, "run_full_pipeline", fake_pipeline)
    monkeypatch.setattr(
        service_module,
        "_client_result",
        lambda workspace, mode: {
            "status": "completed",
            "case_id": workspace.case_id,
            "verification_mode": mode,
        },
    )
    structured = StructuredInformation(
        主题="档位透传测试",
        主张=[
            {
                "文本": "这是一条用于验证档位透传的完整中文主张",
                "表达": "转述",
            }
        ],
    )

    result = asyncio.run(
        verify_structured_information(
            structured,
            "quality",
            source_url="https://example.com/video/1",
            progress=progress.append,
        )
    )
    speed_result = asyncio.run(
        verify_structured_information(
            structured,
            "speed",
            source_url="https://example.com/video/2",
            progress=progress.append,
        )
    )

    assert captured[0]["report_thinking"] == "enabled"
    assert captured[0]["planning_thinking"] == "enabled"
    assert captured[0]["triage_thinking"] == "enabled"
    assert captured[0]["retrieval_timeout_seconds"] == 20.0
    assert captured[1]["report_thinking"] == "disabled"
    assert captured[1]["planning_thinking"] == "disabled"
    assert captured[1]["triage_thinking"] == "disabled"
    assert captured[1]["retrieval_timeout_seconds"] == 10.0
    assert captured[0]["payload"] == structured.model_dump(by_alias=True)
    assert progress == ["M1 输入规范化与稳定编号"] * 2
    assert result["verification_mode"] == "quality"
    assert speed_result["verification_mode"] == "speed"


def test_verify_endpoint_persists_result_to_requested_cache(monkeypatch) -> None:
    structured = {
        "主题": "缓存核验测试",
        "主张": [
            {
                "文本": "这是一条用于验证缓存写回行为的完整中文主张",
                "表达": "直接",
            }
        ],
    }
    stored = {"structured_data": structured}
    writes: list[tuple[str, dict]] = []

    async def fake_verify(_structured, _mode):
        return {"status": "completed", "overall_verdict": "可信"}

    monkeypatch.setattr(main_module, "verify_structured_information", fake_verify)
    monkeypatch.setattr(main_module.cache, "get", lambda _key: dict(stored))
    monkeypatch.setattr(
        main_module.cache,
        "set",
        lambda key, value: writes.append((key, value)),
    )

    key = "a" * 64
    response = TestClient(main_module.app).post(
        "/api/verify",
        json={
            "structured_data": structured,
            "verification_mode": "quality",
            "cache_key": key,
        },
    )

    assert response.status_code == 200
    assert writes[0][0] == key
    assert writes[0][1]["verification"]["overall_verdict"] == "可信"
