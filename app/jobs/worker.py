from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from app.jobs.artifacts import store_job_artifacts
from app.jobs.models import EvidenceSummary, MobileResultCard, utc_now
from app.jobs.runtime import JobRuntime
from app.models import AnalyzeRequest, AnalyzeResponse
from app.trust.pipeline_v2.retrieval import RetrievalConfigurationError


STAGE_DETAILS = {
    "M1 输入规范化与稳定编号": ("claim_structuring", "正在整理并编号待核验主张", 46),
    "M2 检索规划与核验需求": ("evidence_retrieval", "正在制定检索与核验计划", 54),
    "M3 并发检索执行": ("evidence_retrieval", "正在并发检索公开来源", 66),
    "M4 证据池归一化": ("evidence_retrieval", "正在合并与去重候选证据", 72),
    "M5 并发证据初筛": ("evidence_triage", "正在核对证据关系与独立性", 81),
    "M6 最终研判": ("report_generating", "正在综合研判全部主张", 90),
    "M6 输出未完成，复用现有证据重试": ("report_generating", "研判输出未完成，正在复用证据重试", 92),
    "M7 报告渲染": ("report_generating", "正在生成完整核验报告", 96),
}


def stream_event_kind(kind: str) -> str:
    return "thinking_delta" if kind.endswith("thinking") else "report_delta"


class JobCancelled(Exception):
    pass


def _evidence_summaries(verification: dict[str, Any]) -> list[EvidenceSummary]:
    output: list[EvidenceSummary] = []
    for item in verification.get("evidence_used", [])[:2]:
        if not isinstance(item, dict):
            continue
        output.append(EvidenceSummary(
            title=str(item.get("title") or item.get("name") or "公开来源"),
            url=item.get("url"),
            source_name=item.get("source_name") or item.get("domain"),
        ))
    return output


def should_retry_with_visual(result: AnalyzeResponse) -> bool:
    """Escalate sparse video extraction before declaring that there is nothing to verify."""
    claims = getattr(getattr(result, "structured_data", None), "claims", None) or []
    visual_analyzed = bool(
        getattr(getattr(result, "coverage", None), "visual_analyzed", False)
    )
    return not claims and not visual_analyzed


def build_mobile_card(job_id: str, result: AnalyzeResponse, completed_at: datetime) -> MobileResultCard:
    verification = result.verification or {}
    claims = getattr(getattr(result, "structured_data", None), "claims", None) or []
    if verification.get("status") == "skipped" and not claims:
        return MobileResultCard(
            job_id=job_id,
            verdict="无需核验",
            headline="未识别到可核验主张",
            conclusion=str(
                verification.get("message")
                or "当前内容没有需要外部事实核验的现实世界主张。"
            ),
            evidence_count=0,
            elapsed_ms=result.full_pipeline_milliseconds,
            completed_at=completed_at,
        )
    verdict = str(verification.get("overall_verdict") or "待核实")
    headline_map = {
        "属实": "证据支持主要说法",
        "部分属实": "部分说法存在关键差异",
        "误导": "内容可能造成误导",
        "虚假": "关键说法与证据不符",
        "证据不足": "暂缺足够证据",
        "待核实": "仍需更多可靠来源",
    }
    uncertainty = verification.get("uncertainties") or []
    return MobileResultCard(
        job_id=job_id,
        verdict=verdict,
        headline=headline_map.get(verdict, f"核验结论：{verdict}"),
        conclusion=str(verification.get("conclusion") or "核验已完成，请查看逐项证据。"),
        evidence_count=int(verification.get("evidence_selected_count") or len(verification.get("source_ids") or [])),
        elapsed_ms=result.full_pipeline_milliseconds,
        completed_at=completed_at,
        key_evidence=_evidence_summaries(verification),
        uncertainty_note=str(uncertainty[0]) if uncertainty else None,
    )


async def process_job(runtime: JobRuntime, job_id: str) -> None:
    started = time.perf_counter()
    stream_buffers = {
        "m2_thinking": "",
        "thinking": "",
        "report": "",
    }
    last_stream_emit = {kind: started for kind in stream_buffers}

    def elapsed() -> int:
        return round((time.perf_counter() - started) * 1000)

    async def ensure_not_cancelled() -> None:
        current = await runtime.store.get(job_id)
        if current and current.cancel_requested:
            raise JobCancelled()

    async def flush_stream(kind: str, *, force: bool = False) -> None:
        text = stream_buffers.get(kind, "")
        if not text:
            return
        now = time.perf_counter()
        if not force and len(text) < 120 and now - last_stream_emit[kind] < 0.2:
            return
        stream_buffers[kind] = ""
        last_stream_emit[kind] = now
        stage, display_text, progress = {
            "m2_thinking": ("evidence_retrieval", "正在制定检索与核验计划", 54),
            "thinking": ("report_generating", "正在形成最终核验报告", 90),
            "report": ("report_generating", "正在形成最终核验报告", 90),
        }[kind]
        await runtime.emit(
            job_id,
            stage,
            "running",
            display_text,
            progress,
            elapsed_ms=elapsed(),
            event_kind=stream_event_kind(kind),
            payload={"text": text},
        )

    async def on_stream(kind: str, text: str) -> None:
        if not text:
            return
        if kind not in stream_buffers:
            return
        stream_buffers[kind] += text
        await flush_stream(kind, force="\n" in text)

    async def on_product(payload: dict[str, Any]) -> None:
        current = await runtime.store.get(job_id)
        await runtime.emit(
            job_id,
            "evidence_retrieval",
            "running",
            str(payload.get("title") or "已生成阶段结果"),
            current.progress_hint if current else 0,
            elapsed_ms=elapsed(),
            event_kind="artifact",
            payload=payload,
        )

    try:
        job = await runtime.store.get(job_id)
        if not job:
            return
        if job.cancel_requested:
            await runtime.emit(job_id, "cancelled", "cancelled", "核验已取消", 100, status="cancelled", completed_at=utc_now())
            return
        await runtime.emit(
            job_id, "content_resolving", "running", "正在读取分享内容", 8,
            status="running", started_at=utc_now(), elapsed_ms=elapsed(),
        )
        from app.content import analyze_upload_bundle
        from app.main import analyze_content

        await runtime.emit(job_id, "media_extracting", "running", "正在理解视频、字幕与画面", 22, elapsed_ms=elapsed())
        if job.source.type == "agent_context":
            result = await analyze_upload_bundle(
                "分享文字核验",
                job.source.value,
                [],
            )
        else:
            result = await analyze_content(AnalyzeRequest(
                url=job.source.value,
                input_kind="auto",
                mode=job.mode,
                refresh=False,
                verify=False,
            ))
        await ensure_not_cancelled()
        if (
            job.source.type != "agent_context"
            and job.mode == "auto"
            and should_retry_with_visual(result)
        ):
            await runtime.emit(
                job_id,
                "media_extracting",
                "running",
                "口播信息不足，正在补充分析画面",
                34,
                elapsed_ms=elapsed(),
            )
            result = await analyze_content(AnalyzeRequest(
                url=job.source.value,
                input_kind="auto",
                mode="visual",
                refresh=True,
                verify=False,
            ))
            await ensure_not_cancelled()
        metadata = result.metadata
        await on_product({
            "kind": "content",
            "title": "已读取分享内容",
            "summary": str(metadata.title or result.summary or "已完成内容解析"),
            "items": [
                {
                    "label": "来源",
                    "text": str(metadata.platform),
                    "meta": str(metadata.content_type),
                    "url": str(metadata.webpage_url or ""),
                }
            ],
        })
        await runtime.emit(
            job_id, "claim_structuring", "running",
            f"已识别 {len(result.structured_data.claims)} 条待核验主张",
            42,
            elapsed_ms=elapsed(),
            content_metadata={
                "title": result.metadata.title,
                "platform": result.metadata.platform,
                "uploader": result.metadata.uploader,
                "duration_seconds": result.metadata.duration_seconds,
                "content_type": result.metadata.content_type,
                "strategy": result.strategy,
                "topic": result.structured_data.topic,
                "claim_count": len(result.structured_data.claims),
                "transcript_chars": result.transcript_chars,
            },
        )

        async def on_stage(stage: str) -> None:
            await ensure_not_cancelled()
            mapped = STAGE_DETAILS.get(stage)
            if mapped:
                retrying = stage.startswith("M6 输出未完成")
                if retrying:
                    for kind in stream_buffers:
                        stream_buffers[kind] = ""
                await runtime.emit(
                    job_id,
                    mapped[0],
                    "running",
                    mapped[1],
                    mapped[2],
                    elapsed_ms=elapsed(),
                    event_kind="stream_reset" if retrying else "stage",
                )

        from app.trust.service import verify_structured_information
        result.verification = await verify_structured_information(
            result.structured_data,
            job.verification_mode,
            source_url=result.metadata.webpage_url,
            source_context=result.full_source_text,
            progress=on_stage,
            stream=on_stream,
            product=on_product,
        )
        for kind in stream_buffers:
            await flush_stream(kind, force=True)
        result.full_pipeline_milliseconds = max(result.full_pipeline_milliseconds, elapsed())
        completed_at = utc_now()
        card = build_mobile_card(job_id, result, completed_at)
        try:
            report_url = await store_job_artifacts(
                job_id,
                result.model_dump(mode="json"),
                str((result.verification or {}).get("report_markdown") or ""),
            )
        except Exception:
            report_url = None
        if report_url:
            card.report_url = report_url
        payload = {
            "card": card.model_dump(mode="json"),
            "analysis": result.model_dump(mode="json"),
        }
        await runtime.emit(
            job_id, "completed", "completed", card.headline, 100,
            status="completed", completed_at=completed_at,
            elapsed_ms=elapsed(), result=payload,
        )
    except JobCancelled:
        await runtime.emit(
            job_id, "cancelled", "cancelled", "核验已取消", 100,
            status="cancelled", completed_at=utc_now(), elapsed_ms=elapsed(),
        )
    except RetrievalConfigurationError as exc:
        await runtime.emit(
            job_id,
            "failed",
            "failed",
            "公开来源检索未配置，请配置 EXA_API_KEY 后重试",
            100,
            status="failed",
            completed_at=utc_now(),
            elapsed_ms=elapsed(),
            error_code=type(exc).__name__,
            error_message=str(exc)[:500],
        )
    except Exception as exc:
        await runtime.emit(
            job_id, "failed", "failed", "本次核验未完成，可稍后重试", 100,
            status="failed", completed_at=utc_now(), elapsed_ms=elapsed(),
            error_code=type(exc).__name__, error_message=str(exc)[:500],
        )


async def run_job(ctx: dict[str, Any], job_id: str) -> None:
    runtime = ctx["runtime"]
    await process_job(runtime, job_id)


async def startup(ctx: dict[str, Any]) -> None:
    runtime = JobRuntime("distributed")
    await runtime.initialize()
    ctx["runtime"] = runtime


class WorkerSettings:
    functions = [run_job]
    on_startup = startup
    queue_name = "mimotrust:jobs"
    max_jobs = 4
    job_timeout = 1800
