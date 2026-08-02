"""M1: validate compact extracted claims and assign stable identifiers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = "2"
EXPRESSION_VALUES = frozenset({"直接", "转述", "隐含"})
_TOP_LEVEL_FIELDS = frozenset({"主题", "主张"})
_CLAIM_FIELDS = frozenset({"文本", "表达"})


class InputValidationError(ValueError):
    """Raised when an upstream compact-claim artifact violates the M1 interface."""


def normalize_case_input(raw: Any, case_id: str | None = None) -> dict[str, Any]:
    """Return the formal M1 artifact from the compact content-extraction JSON.

    The function intentionally performs no semantic deduplication or classification.
    It only trims leading/trailing whitespace, removes exact duplicate claim objects,
    assigns C1... in retained input order, and adds mechanical metadata.
    """

    if not isinstance(raw, dict):
        raise InputValidationError("输入必须是 JSON 对象")

    _reject_unknown_fields(raw, _TOP_LEVEL_FIELDS, "输入")
    topic = _required_text(raw, "主题", "输入")
    raw_claims = raw.get("主张")
    if not isinstance(raw_claims, list) or not raw_claims:
        raise InputValidationError("输入.主张 必须是非空数组")

    claims: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_claim in enumerate(raw_claims, start=1):
        path = f"输入.主张[{index}]"
        if not isinstance(raw_claim, dict):
            raise InputValidationError(f"{path} 必须是对象")
        _reject_unknown_fields(raw_claim, _CLAIM_FIELDS, path)

        text = _required_text(raw_claim, "文本", path)
        expression = _required_text(raw_claim, "表达", path)
        if expression not in EXPRESSION_VALUES:
            allowed = "、".join(sorted(EXPRESSION_VALUES))
            raise InputValidationError(
                f"{path}.表达 必须是以下值之一：{allowed}"
            )

        fingerprint = (text, expression)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        claims.append({"文本": text, "表达": expression})

    if not claims:
        raise InputValidationError("输入.主张 不得全部为重复项")

    resolved_case_id = normalize_case_id(case_id) if case_id else _derive_case_id(topic, claims)
    return {
        "版本": PROTOCOL_VERSION,
        "案例编号": resolved_case_id,
        "主题": topic,
        "主张": [
            {"编号": f"C{index}", **claim}
            for index, claim in enumerate(claims, start=1)
        ],
    }


def write_json_atomic(path: Path, value: Any) -> None:
    """Persist one complete JSON artifact or leave the previous artifact unchanged."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _required_text(container: dict[str, Any], key: str, path: str) -> str:
    value = container.get(key)
    if not isinstance(value, str):
        raise InputValidationError(f"{path}.{key} 必须是非空字符串")
    normalized = value.strip()
    if not normalized:
        raise InputValidationError(f"{path}.{key} 不得为空")
    return normalized


def _reject_unknown_fields(
    container: dict[str, Any], allowed: frozenset[str], path: str
) -> None:
    unknown = sorted(str(key) for key in container.keys() if key not in allowed)
    if unknown:
        raise InputValidationError(f"{path} 包含不支持字段：{'、'.join(unknown)}")


def _derive_case_id(topic: str, claims: list[dict[str, str]]) -> str:
    canonical = json.dumps(
        {"主题": topic, "主张": claims},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"case-{digest}"


def normalize_case_id(value: str) -> str:
    if not isinstance(value, str):
        raise InputValidationError("案例编号必须是字符串")
    normalized = value.strip().lower()
    if not normalized:
        raise InputValidationError("案例编号不得为空")
    if not all(character.isascii() and (character.isalnum() or character in "-_") for character in normalized):
        raise InputValidationError("案例编号只能包含 ASCII 字母、数字、连字符和下划线")
    return normalized
