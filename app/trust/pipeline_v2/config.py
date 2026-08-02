"""Environment-backed runtime configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when an environment variable has an invalid value."""


def load_environment_file(path: Path | None) -> None:
    """Load KEY=VALUE pairs without overriding an existing process environment."""

    if path is None or not path.exists():
        return
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError(f"{path}:{line_number} 缺少等号")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        if not key:
            raise ConfigurationError(f"{path}:{line_number} 环境变量名为空")
        os.environ.setdefault(key, value)


def env_text(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} 必须是整数") from error
    if value < minimum:
        raise ConfigurationError(f"{name} 必须大于等于 {minimum}")
    return value


def env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = os.environ.get(name)
    try:
        value = default if raw is None else float(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} 必须是数字") from error
    if value < minimum:
        raise ConfigurationError(f"{name} 必须大于等于 {minimum:g}")
    return value


def env_choice(name: str, default: str, choices: set[str]) -> str:
    value = env_text(name, default)
    if value not in choices:
        raise ConfigurationError(
            f"{name} 必须是以下值之一：{', '.join(sorted(choices))}"
        )
    return value


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} 必须是 true 或 false")
