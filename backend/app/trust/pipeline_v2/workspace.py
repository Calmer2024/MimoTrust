"""Durable per-case storage for modular pipeline artifacts."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .normalization import (
    InputValidationError,
    normalize_case_id,
    normalize_case_input,
    write_json_atomic,
)


_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_STAGE_ARTIFACTS = {
    "M1": ("00_input.json", "01_claims.json"),
    "M2": (
        "02_planning_input.json",
        "02_planning_output.json",
        "02_planning_metrics.json",
        "02_verification_plan.json",
    ),
    "M3": (
        "03_retrieval_input.json",
        "03_retrieval.json",
        "03_retrieval_metrics.json",
    ),
    "M4": (
        "04_normalization_input.json",
        "04_evidence_pool.json",
        "04_normalization_metrics.json",
    ),
    "M5": ("05_evidence_ledger.json",),
    "M6": ("06_report_draft.json",),
    "M7": (
        "07_render_input.json",
        "07_report.json",
        "07_report.md",
        "07_render_metrics.json",
        "07_pipeline_metrics.json",
    ),
}


@dataclass(frozen=True)
class CaseRunWorkspace:
    """One immutable run directory under a durable case directory."""

    cases_root: Path
    case_id: str
    run_id: str

    @property
    def case_dir(self) -> Path:
        return self.cases_root / self.case_id

    @property
    def run_dir(self) -> Path:
        return self.case_dir / "runs" / self.run_id

    @property
    def input_path(self) -> Path:
        return self.case_dir / "input.json"

    @property
    def latest_run_path(self) -> Path:
        return self.case_dir / "latest_run.json"

    @classmethod
    def create(
        cls, cases_root: Path, case_id: str, run_id: str | None = None
    ) -> "CaseRunWorkspace":
        normalized_case_id = normalize_case_id(case_id)
        resolved_run_id = run_id or datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
        if not _RUN_ID_PATTERN.fullmatch(resolved_run_id):
            raise InputValidationError(
                "运行编号只能包含 ASCII 字母、数字、连字符和下划线"
            )

        workspace = cls(
            cases_root=Path(cases_root),
            case_id=normalized_case_id,
            run_id=resolved_run_id,
        )
        if workspace.run_dir.exists():
            raise FileExistsError(f"运行目录已存在：{workspace.run_dir}")
        workspace.run_dir.mkdir(parents=True, exist_ok=False)
        return workspace

    @classmethod
    def open_existing(
        cls, cases_root: Path, case_id: str, run_id: str | None = None
    ) -> "CaseRunWorkspace":
        normalized_case_id = normalize_case_id(case_id)
        resolved_run_id = run_id
        case_dir = Path(cases_root) / normalized_case_id
        if resolved_run_id is None:
            latest_path = case_dir / "latest_run.json"
            try:
                latest = json.loads(latest_path.read_text(encoding="utf-8"))
                resolved_run_id = str(latest["运行编号"])
            except (OSError, json.JSONDecodeError, KeyError) as error:
                raise FileNotFoundError(
                    f"无法从 {latest_path} 确定可继续的运行编号"
                ) from error
        if not _RUN_ID_PATTERN.fullmatch(resolved_run_id):
            raise InputValidationError(
                "运行编号只能包含 ASCII 字母、数字、连字符和下划线"
            )
        workspace = cls(Path(cases_root), normalized_case_id, resolved_run_id)
        if not workspace.run_dir.is_dir():
            raise FileNotFoundError(f"运行目录不存在：{workspace.run_dir}")
        return workspace

    def write_artifact(self, filename: str, value: Any) -> Path:
        path = self.run_dir / filename
        write_json_atomic(path, value)
        return path

    def write_text_artifact(self, filename: str, value: str) -> Path:
        path = self.run_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        temporary_path.write_text(value, encoding="utf-8")
        temporary_path.replace(path)
        return path

    def read_artifact(self, filename: str) -> Any:
        return json.loads((self.run_dir / filename).read_text(encoding="utf-8"))

    def record_stage(
        self,
        stage: str,
        status: str,
        started_at: datetime,
        elapsed_ms: int,
        artifacts: list[str],
        error: str | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        status_path = self.run_dir / "run.json"
        if status_path.exists():
            record = json.loads(status_path.read_text(encoding="utf-8"))
        else:
            record = {
                "案例编号": self.case_id,
                "运行编号": self.run_id,
                "开始时间": started_at.isoformat(),
                "阶段": {},
            }
        stage_record: dict[str, Any] = {
            "状态": status,
            "开始时间": started_at.isoformat(),
            "耗时毫秒": elapsed_ms,
            "产物": artifacts,
        }
        if error:
            stage_record["错误"] = error
        if metrics:
            stage_record["指标"] = metrics
        record["状态"] = f"{stage.lower()}_{status}"
        record["更新时间"] = datetime.now(timezone.utc).isoformat()
        record.setdefault("阶段", {})[stage] = stage_record
        if error:
            record["错误"] = error
        else:
            record.pop("错误", None)
        self.write_artifact("run.json", record)

    def write_status(
        self,
        status: str,
        started_at: datetime,
        elapsed_ms: int,
        artifacts: list[str],
        error: str | None = None,
    ) -> None:
        self.record_stage(
            "M1",
            "completed" if status == "m1_completed" else "failed",
            started_at,
            elapsed_ms,
            artifacts,
            error,
        )

    def mark_latest_successful_run(self) -> None:
        self.mark_latest_stage("M1")

    def mark_latest_stage(self, stage: str) -> None:
        write_json_atomic(
            self.latest_run_path,
            {
                "案例编号": self.case_id,
                "运行编号": self.run_id,
                "状态": f"{stage.lower()}_completed",
                "运行目录": f"runs/{self.run_id}",
                "更新时间": datetime.now(timezone.utc).isoformat(),
            },
        )


def run_m1_case(
    cases_root: Path, case_id: str, run_id: str | None = None
) -> tuple[CaseRunWorkspace, dict[str, Any]]:
    """Run M1 from a case's fixed input file and persist all M1 artifacts."""

    workspace = CaseRunWorkspace.create(cases_root, case_id, run_id)
    started_at = datetime.now(timezone.utc)
    started_monotonic = time.perf_counter()
    artifacts: list[str] = []
    try:
        raw = json.loads(workspace.input_path.read_text(encoding="utf-8"))
        workspace.write_artifact("00_input.json", raw)
        artifacts.append("00_input.json")
        normalized = normalize_case_input(raw, case_id=workspace.case_id)
        workspace.write_artifact("01_claims.json", normalized)
        artifacts.append("01_claims.json")
    except (OSError, json.JSONDecodeError, InputValidationError) as error:
        workspace.write_status(
            "m1_failed",
            started_at,
            _elapsed_ms(started_monotonic),
            artifacts,
            str(error),
        )
        if isinstance(error, json.JSONDecodeError):
            raise InputValidationError(
                f"input.json 不是合法 JSON：{error.msg}"
            ) from error
        raise

    workspace.write_status(
        "m1_completed", started_at, _elapsed_ms(started_monotonic), artifacts
    )
    workspace.mark_latest_successful_run()
    return workspace, normalized


def fork_run_through_stage(
    cases_root: Path,
    case_id: str,
    source_run_id: str,
    target_run_id: str,
    through_stage: str,
) -> CaseRunWorkspace:
    """Create an immutable replay run from completed upstream JSON artifacts."""

    if through_stage not in _STAGE_ARTIFACTS:
        raise ValueError(f"不支持继承到阶段：{through_stage}")
    source = CaseRunWorkspace.open_existing(cases_root, case_id, source_run_id)
    source_record = source.read_artifact("run.json")
    source_stages = source_record.get("阶段")
    if not isinstance(source_stages, dict):
        raise ValueError("来源运行缺少阶段记录")

    stage_names = list(_STAGE_ARTIFACTS)
    inherited_stages = stage_names[: stage_names.index(through_stage) + 1]
    stage_artifacts: dict[str, list[str]] = {}
    for stage in inherited_stages:
        if source_stages.get(stage, {}).get("状态") != "completed":
            raise ValueError(f"来源运行的 {stage} 尚未完成")
        recorded = source_stages[stage].get("产物")
        if recorded is None:
            recorded = []
        if not isinstance(recorded, list) or not all(
            isinstance(filename, str) for filename in recorded
        ):
            raise ValueError(f"来源运行的 {stage}.产物 结构不合法")
        filenames = list(dict.fromkeys([*_STAGE_ARTIFACTS[stage], *recorded]))
        for filename in filenames:
            relative = Path(filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"来源运行包含不安全的产物路径：{filename}")
            if not (source.run_dir / filename).is_file():
                raise FileNotFoundError(f"来源运行缺少产物：{filename}")
        stage_artifacts[stage] = filenames

    target = CaseRunWorkspace.create(cases_root, case_id, target_run_id)
    created_at = datetime.now(timezone.utc)
    copied_stages: dict[str, Any] = {}
    for stage in inherited_stages:
        filenames = stage_artifacts[stage]
        for filename in filenames:
            if Path(filename).suffix == ".json":
                target.write_artifact(filename, source.read_artifact(filename))
            else:
                target.write_text_artifact(
                    filename,
                    (source.run_dir / filename).read_text(encoding="utf-8"),
                )
        copied_stages[stage] = {
            **source_stages[stage],
            "产物": filenames,
            "继承自运行": source.run_id,
        }
    target.write_artifact(
        "run.json",
        {
            "案例编号": target.case_id,
            "运行编号": target.run_id,
            "开始时间": created_at.isoformat(),
            "来源运行": source.run_id,
            "继承至阶段": through_stage,
            "阶段": copied_stages,
            "状态": f"{through_stage.lower()}_completed",
            "更新时间": created_at.isoformat(),
        },
    )
    target.mark_latest_stage(through_stage)
    return target


def _elapsed_ms(started_monotonic: float) -> int:
    return round((time.perf_counter() - started_monotonic) * 1000)
