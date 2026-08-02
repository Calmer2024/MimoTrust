from __future__ import annotations

import asyncio
from types import SimpleNamespace

import app.trust.pipeline_v2.pipeline as pipeline_module
from app.trust.pipeline_v2.synthesis import SynthesisValidationError


def test_full_pipeline_retries_only_m6_after_invalid_model_output(
    monkeypatch,
) -> None:
    workspace = SimpleNamespace(
        run_id="run-one",
        write_artifact=lambda *_args: None,
    )
    stage_calls: list[str] = []
    progress: list[str] = []

    def fake_m1(*_args, **_kwargs):
        stage_calls.append("M1")
        return workspace, {}

    async def fake_async_stage(name, *_args, **_kwargs):
        stage_calls.append(name)

    def fake_sync_stage(name, *_args, **_kwargs):
        stage_calls.append(name)

    attempts = 0

    async def fake_m6(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        stage_calls.append(f"M6-A{attempts:02d}")
        if attempts == 1:
            raise SynthesisValidationError("模型输出不是合法JSON")

    monkeypatch.setenv("MIMO_REPORT_MAX_ATTEMPTS", "2")
    monkeypatch.setattr(pipeline_module, "run_m1_case", fake_m1)
    monkeypatch.setattr(
        pipeline_module,
        "run_m2_case",
        lambda *args, **kwargs: fake_async_stage("M2", *args, **kwargs),
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_m3_case",
        lambda *args, **kwargs: fake_async_stage("M3", *args, **kwargs),
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_m4_case",
        lambda *args, **kwargs: fake_sync_stage("M4", *args, **kwargs),
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_m5_case",
        lambda *args, **kwargs: fake_async_stage("M5", *args, **kwargs),
    )
    monkeypatch.setattr(pipeline_module, "run_m6_case", fake_m6)
    monkeypatch.setattr(
        pipeline_module,
        "run_m7_case",
        lambda *_args, **_kwargs: (workspace, {"status": "ok"}),
    )
    monkeypatch.setattr(
        pipeline_module,
        "build_pipeline_metrics",
        lambda *_args, **_kwargs: {},
    )

    _, report = asyncio.run(
        pipeline_module.run_full_pipeline(
            SimpleNamespace(),
            "case-one",
            planning_model="mimo-v2.5",
            triage_model="mimo-v2.5-pro",
            report_model="mimo-v2.5-pro",
            report_thinking="enabled",
            progress=progress.append,
        )
    )

    assert report == {"status": "ok"}
    assert stage_calls == [
        "M1", "M2", "M3", "M4", "M5", "M6-A01", "M6-A02"
    ]
    assert progress.count("M6 最终研判") == 1
    assert "M6 输出未完成，复用现有证据重试" in progress
