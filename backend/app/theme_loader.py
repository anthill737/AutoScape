from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_THEMES_PATH = Path(__file__).resolve().parents[1] / "data" / "themes.json"
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_THEME_KEYS = ("bg", "fg", "accent")


class ThemeNotFoundError(LookupError):
    """Raised when a theme name is not present in the theme registry."""


def load_theme(name: str) -> dict:
    if _is_hex_color(name):
        return {"bg": name, "fg": name, "accent": name}

    registry = _load_registry()
    theme = registry.get(name)
    if not isinstance(theme, dict):
        raise ThemeNotFoundError(f"Theme not found: {name}")

    return _normalize_theme(name, theme)


def _load_registry() -> dict[str, Any]:
    if not _THEMES_PATH.is_file():
        return {}

    try:
        data = json.loads(_THEMES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ThemeNotFoundError(f"Theme registry is invalid: {_THEMES_PATH}") from exc

    if not isinstance(data, dict):
        raise ThemeNotFoundError(f"Theme registry must be an object: {_THEMES_PATH}")
    return data


def _normalize_theme(name: str, theme: dict[str, Any]) -> dict:
    normalized: dict[str, str] = {}
    for key in _THEME_KEYS:
        value = theme.get(key)
        if not isinstance(value, str) or not _is_hex_color(value):
            raise ThemeNotFoundError(f"Theme {name} is missing valid {key}")
        normalized[key] = value
    return normalized


def _is_hex_color(value: str) -> bool:
    return bool(_HEX_COLOR_RE.fullmatch(value))
