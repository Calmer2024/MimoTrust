from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.models import StructuredInformation


class MimoError(RuntimeError):
    pass


STRUCTURED_INFORMATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "主题": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "description": "概括内容实际传播的核心问题，覆盖主要结论而非只写其引用的研究或案例。",
        },
        "主张": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "文本": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 300,
                        "pattern": r".*[\u4e00-\u9fff].*",
                        "description": "可独立核验的单一命题；保留原内容的范围、可能性和强度，不替作者修正或弱化。",
                    },
                    "表达": {
                        "type": "string",
                        "enum": ["直接", "转述", "隐含"],
                        "description": (
                            "直接=内容作者明确断言、认可，或用‘也就是说/所以/这意味着’作出的归纳；"
                            "转述=命题仅归属于新闻、研究或他人，作者未明确认可；"
                            "隐含=命题没有被明说，只通过反讽、反问、剪辑、语气或对比引导受众接受。"
                            "‘可能/涉嫌/或许’只表示确定性较低：只要作者明确说出，仍属于直接，不属于隐含。"
                        ),
                    },
                },
                "required": ["文本", "表达"],
                "additionalProperties": False,
            },
            "uniqueItems": True,
        },
    },
    "required": ["主题", "主张"],
    "additionalProperties": False,
}


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.mimo_api_key}",
        "api-key": settings.mimo_api_key,
        "Content-Type": "application/json",
    }


def _parse_json_content(content: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    candidate = fenced.group(1) if fenced else content
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as first_error:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError as second_error:
                raise MimoError(
                    "MiMo 返回了语法损坏的 JSON"
                ) from second_error
        raise MimoError("MiMo 返回了无法解析的摘要格式") from first_error


def _structured_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "mimo_trust_compact_claims_v2",
            "strict": True,
            "schema": STRUCTURED_INFORMATION_SCHEMA,
        },
    }


def _choice_content(data: dict[str, Any]) -> tuple[str, str]:
    try:
        choice = data["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise MimoError("MiMo 返回缺少 choices/message 字段") from exc
    content = str(
        message.get("content") or message.get("reasoning_content") or ""
    ).strip()
    if not content:
        raise MimoError("MiMo 返回了空内容")
    return content, str(choice.get("finish_reason") or "")


def _validate_structured_result(result: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = StructuredInformation.model_validate(result)
    except Exception as exc:
        if hasattr(exc, "errors"):
            errors = [
                {
                    "field": ".".join(str(part) for part in item.get("loc", [])),
                    "type": item.get("type"),
                    "message": item.get("msg"),
                }
                for item in exc.errors(include_url=False)
            ]
            detail = json.dumps(errors, ensure_ascii=False)
        else:
            detail = str(exc)
        raise MimoError(f"结构化信息未通过本地 Schema 校验：{detail}") from exc
    return validated.model_dump(by_alias=True)


async def _repair_structured_json(content: str, reason: str) -> dict[str, Any]:
    repair_payload = {
        "model": settings.summary_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是结构化 JSON 修复器。只修复语法、补齐结构和删除未完成的末尾项；"
                    "不得增加候选文本中不存在的新事实。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"失败原因：{reason or 'JSON 语法或结构错误'}。\n"
                    "请把下面候选结果修复为 compact-claims-v2。"
                    "若文本被截断，只保留已经完整出现的信息：\n"
                    f"{content[:24_000]}"
                ),
            },
        ],
        "temperature": 0,
        "max_completion_tokens": 4000,
        "thinking": {"type": "disabled"},
        "response_format": _structured_response_format(),
    }
    repaired = await _completion(repair_payload, timeout=180)
    repaired_content, finish_reason = _choice_content(repaired)
    if finish_reason == "length":
        raise MimoError("JSON 修复结果再次被截断")
    return _validate_structured_result(_parse_json_content(repaired_content))


async def _completion(payload: dict[str, Any], timeout: float = 120) -> dict[str, Any]:
    if not settings.mimo_api_key:
        raise MimoError("未配置 MIMO_API_KEY")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.mimo_base_url}/chat/completions",
            headers=_headers(),
            json=payload,
        )
    if response.is_error:
        detail = response.text[:500]
        raise MimoError(f"MiMo API 请求失败（{response.status_code}）：{detail}")
    return response.json()


async def structure_information(
    source_text: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    prompt = f"""
你是内容主张提取器。

你的任务是理解输入的视频、字幕、标题、画面文字或图文内容，将其压缩为少量、自包含、可交给事实核查流水线处理的核心主张。

你只负责提取“内容在表达什么”，不搜索资料，不判断真假，不替内容修正错误。

只输出以下 JSON，不输出分析、解释或 Markdown：

{{
  "主题": "一句话概括内容讨论的核心问题",
  "主张": [
    {{
      "文本": "脱离原文也能独立理解和核验的主张",
      "表达": "直接|转述|隐含"
    }}
  ]
}}

【是否进入事实核验】

先判断内容是否提出了需要外部证据核验的现实世界事实命题。只有这类命题才能进入“主张”。

如果内容明确只是以下类型，保留一句“主题”，并输出 "主张": []：
- 虚构剧情、虚构角色关系、世界观设定或对作品情节的主观解读；
- 粉丝理论、二创、角色扮演、玩梗、戏仿、段子或不按字面成立的娱乐化夸张；
- 审美喜好、个人感受、排行、价值判断、情绪表达或人生感悟；
- 假设题、脑洞、创作预告、游戏过程或故事续写，且没有断言现实已经发生；
- 无公共事实意义、无法通过外部信源核验的日常自述；
- 仅能改写成“这个视频声称/暗示某个虚构情节”的自指元主张。不得为了让纯娱乐内容显得可核验而添加“视频声称”作为主语。

以下情况不能跳过：
- 内容涉及现实人物、机构、事件、时间、地点、数据、历史、政策、法规、科学、健康、安全、公共利益或产品能力；
- 内容对作品背后的现实制作、发行、作者身份、抄袭、审查、商业行为或真实原型作出断言；
- 戏仿、反讽或娱乐表达中夹带了对现实对象的造假、违法、危害、阴谋、身份或动机指控。

混合内容只提取其中的现实世界事实主张。不能因为语气幽默、标题夸张或带有娱乐标签就跳过现实指控；只有明确属于纯娱乐内容且没有现实事实命题时才输出空数组。

【提取规则】

1. 只保留影响内容结论的核心主张，不凑数，不提取无关背景、情绪感叹、口号和常识性建议。

2. 每条主张只能对应一个可以独立形成核验结论的命题。如果一句话的不同部分可能分别为真或为假，必须拆开。

3. “文本”必须补全必要的人物、对象、时间和地点，使其脱离原文仍可理解；但不得改变原意，不得增加或删除“可能、涉嫌、全部、唯一、严重”等限定词。

4. 表达方式：
- 直接：内容明确断言并认可该主张。
- 转述：内容引用新闻、网传、他人说法或公开报道中的现实世界事实命题，但未明确表示认可。内容对自身虚构情节或玩梗的描述不因此成为转述主张。
- 隐含：内容没有直接说出，却通过反讽、反问、夸张、对比、剪辑、标题、语气或反复暗示，引导受众接受该主张。

5. 必须识别隐含的事实性指控或叙事引导，包括但不限于：
- 暗示事件、数据、经历或身份是伪造、摆拍或夸大；
- 暗示当事人在刷履历、博流量、制造新闻或进行利益包装；
- 暗示媒体与当事人配合炒作；
- 暗示某行为违法、违规、有害或存在不可告人的动机；
- 暗示个别案例能够证明某个群体、制度或技术普遍有问题。

6. 反讽和反问不能只按字面提取。若“这履历刷得真漂亮”“到底是献血还是献新闻”等表达明显引导观众认为献血记录可能造假或报道属于履历包装，应提取对应的隐含主张。

7. 隐含主张必须保持原内容的强度：
- “可能是假的”不能改写成“确定造假”；
- “涉嫌违规”不能改写成“已经违法”；
- 仅表达厌恶、嘲笑或不满，但没有形成可识别命题时，不提取；
- 不得仅凭常识猜测内容未暗示的动机。

8. 被转述的基础事实和围绕它形成的隐含指控可以同时保留，但不得重复表达同一个命题。

9. 必须保留内容的核心落点。输出前先识别标题、开场钩子、反复强调和结尾总结共同引导受众接受的结论；若该结论是可核验的现实命题，不能只提取铺垫它的研究、新闻或案例而遗漏该结论。

10. 严格区分“引用依据”和“作者结论”：“据报道、研究发现、某人表示”引出的内容通常是转述；“也就是说、所以、可见、这意味着、归根结底”之后由内容作者作出的归纳或认可，必须作为独立的直接主张。不能因为作者结论建立在转述材料上，就把作者结论也标成转述。输出前逐条自检“是谁在认可这个命题”；除非结论标记之后仍明确归属于被引用者，否则结论标记后的归纳不得标为转述。

“直接、转述、隐含”描述的是命题在内容中如何被表达，与命题真伪或确定性无关。作者明确说出的“可能、涉嫌、或许”仍是直接主张，不能因措辞不确定而标为隐含。不得擅自给作者明确说出的结论补上“研究结论意味着”等来源归属，从而改变其表达类型。

11. 若内容把有限条件下的研究、个别案例、相关性或可能性，外推为日常场景、普遍规律、确定因果或绝对结论，必须将“原始有限命题”和“外推后的结论”分成不同主张，并保持各自强度。不得用更谨慎的研究表述替换、弱化或吞掉内容实际传播的夸张结论。

12. 若内容用“发表于某期刊、获得某机构认证、来自某权威专家”等事实为核心结论增加可信度，该背书本身可以独立核验，必须保留为单独主张；不得只保留被背书的结论而省略其权威性依据。

13. 同义主张合并。数量随内容复杂度决定，优先简洁；主题尽量不超过40字，每条主张尽量不超过70字。

标题：{metadata.get("title", "")}
作者：{metadata.get("uploader", "")}
内容类型：{"图文轮播" if metadata.get("content_type") == "image_carousel" else "视频"}
简介：{metadata.get("description", "")[:1500]}
完整原文信息（可能包含字幕、OCR、画面观察和发布文案）：
{source_text[:settings.max_transcript_chars]}
""".strip()
    payload = {
        "model": settings.summary_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "严格遵守用户给出的主张提取协议和 JSON Schema。"
                    "优先完整覆盖核心传播结论、范围外推和权威背书；"
                    "逐条检查命题由引用者还是内容作者认可。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_completion_tokens": 2400,
        "thinking": {"type": "disabled"},
        "response_format": _structured_response_format(),
    }
    data = await _completion(payload)
    content, finish_reason = _choice_content(data)
    primary_usage = data.get("usage") or {}
    try:
        if finish_reason == "length":
            raise MimoError("结构化信息输出达到 token 上限并被截断")
        result = _validate_structured_result(_parse_json_content(content))
    except MimoError as exc:
        result = await _repair_structured_json(content, str(exc))
    result["_usage"] = primary_usage
    return result


async def analyze_keyframes(
    frames: list[tuple[int, float, Path]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Run OCR and grounded visual observation over adaptive keyframes."""
    prompt = """
逐张分析按时间顺序提供的视频关键帧。执行：
1. 原样提取有事实意义的屏幕文字（OCR），保留数字、日期、机构、地点；
2. 描述画面中直接可观察的事件，不推测地点、时间、身份或因果；
3. 判断帧主要类型：scene_change、periodic、first_frame 或 unknown；
4. 相邻帧文字相同可以保留，但不要凭空补全被遮挡文字。

输出纯 JSON：
{"frames":[{"frame_index":1,"timestamp_seconds":0,
"ocr_text":["屏幕原文"],"visual_observations":["直接观察"],
"frame_type":"first_frame"}],
"summary":"关键帧视觉概括","coverage_note":"OCR和画面覆盖说明"}
""".strip()
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for index, timestamp, path in frames:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        mime = {
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "image/jpeg")
        content.extend(
            [
                {
                    "type": "text",
                    "text": f"关键帧 {index}，时间 {timestamp:.2f} 秒：",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                },
            ]
        )
    payload = {
        "model": settings.summary_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 MiMo Trust 的关键帧 OCR 与视觉证据提取模块。"
                    "只报告可直接观察的信息。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"视频标题：{metadata.get('title', '')}",
                    },
                    *content,
                ],
            },
        ],
        "temperature": 0.1,
        "max_completion_tokens": 2400,
        "thinking": {"type": "disabled"},
    }
    data = await _completion(payload, timeout=240)
    result = _parse_json_content(data["choices"][0]["message"]["content"])
    result["_usage"] = data.get("usage") or {}
    return result


async def transcribe_audio(audio_path: Path) -> dict[str, Any]:
    mime = "audio/mpeg" if audio_path.suffix.lower() == ".mp3" else "audio/wav"
    encoded = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    payload = {
        "model": settings.asr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": f"data:{mime};base64,{encoded}"},
                    }
                ],
            }
        ],
        "asr_options": {"language": "auto"},
        "stream": False,
        "max_completion_tokens": 2000,
    }
    data = await _completion(payload, timeout=240)
    choice = data["choices"][0]
    usage = data.get("usage") or {}
    return {
        "text": choice["message"]["content"].strip(),
        "finish_reason": choice.get("finish_reason"),
        "processed_seconds": float(usage.get("seconds") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }


async def summarize_video(
    media_url_or_path: str | Path,
    metadata: dict[str, Any],
    fps: float = 0.2,
) -> dict[str, Any]:
    prompt = """
分析视频画面与屏幕文字，为后续信源核实提取视觉信息。
不要判断真假，不要用画面推测未出现的事实。输出纯 JSON：
{"summary":"视觉内容概括","key_points":["画面事件"],"topics":["主题词"],"on_screen_text":["关键屏幕文字"],"coverage_note":"视觉覆盖说明"}
""".strip()
    if isinstance(media_url_or_path, Path):
        raw = media_url_or_path.read_bytes()
        media_value = f"data:video/mp4;base64,{base64.b64encode(raw).decode('ascii')}"
    else:
        media_value = media_url_or_path
    payload = {
        "model": settings.summary_model,
        "messages": [
            {
                "role": "system",
                "content": "你是 MiMo Trust 的全模态视频内容概括模块。只概括，不核验。",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": media_value},
                        "fps": fps,
                        "media_resolution": "default",
                    },
                    {
                        "type": "text",
                        "text": f"{prompt}\n视频标题：{metadata.get('title', '')}",
                    },
                ],
            },
        ],
        "temperature": 0.2,
        "max_completion_tokens": 700,
        "thinking": {"type": "disabled"},
    }
    data = await _completion(payload, timeout=240)
    content = data["choices"][0]["message"]["content"]
    result = _parse_json_content(content)
    result["_usage"] = data.get("usage") or {}
    return result
