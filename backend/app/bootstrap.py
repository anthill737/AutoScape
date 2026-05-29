from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path

from dotenv import dotenv_values

REQUIRED_API_KEYS = (
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "PERPLEXITY_API_KEY",
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ENV_LOCAL = _PROJECT_ROOT / "backend" / ".env.local"
_SECRETS_DIR = _PROJECT_ROOT / "secrets"

logger = logging.getLogger(__name__)


def secret_file_path(name: str) -> Path:
    if name not in REQUIRED_API_KEYS:
        raise ValueError(f"Unknown API key name: {name}")
    return _SECRETS_DIR / name


def _set_required_key(name: str, value: str | None) -> bool:
    if not value:
        return False
    if os.environ.get(name):
        return False
    os.environ[name] = value
    return True


def _load_backend_env_local() -> list[str]:
    if not _BACKEND_ENV_LOCAL.is_file():
        return []

    env_values = dotenv_values(_BACKEND_ENV_LOCAL)
    loaded_names: list[str] = []
    for name in REQUIRED_API_KEYS:
        if _set_required_key(name, env_values.get(name)):
            loaded_names.append(name)
    return loaded_names


def _load_secret_files() -> list[str]:
    found_files: list[str] = []
    for name in REQUIRED_API_KEYS:
        secret_file = _SECRETS_DIR / name
        if not secret_file.is_file():
            continue

        found_files.append(secret_file.name)
        _set_required_key(name, secret_file.read_text(encoding="utf-8").strip())
    return found_files


def load_startup_secrets() -> list[str]:
    """Load required provider keys without overriding existing environment values."""

    _load_backend_env_local()
    found_secret_files = _load_secret_files()
    if found_secret_files:
        logger.info("[startup] secret files found: %s", ", ".join(found_secret_files))
    return found_secret_files


def reload_key_cache(names: Iterable[str] | None = None) -> list[str]:
    """Reload settings-managed API keys from secrets/ into the process cache."""

    key_names = tuple(names) if names is not None else REQUIRED_API_KEYS
    loaded_names: list[str] = []
    for name in key_names:
        secret_file = secret_file_path(name)
        if secret_file.is_file():
            value = secret_file.read_text(encoding="utf-8").strip()
            if value:
                os.environ[name] = value
                loaded_names.append(name)
                continue
        os.environ.pop(name, None)
    return loaded_names


def startup_key_presence() -> tuple[list[str], list[str]]:
    present = [name for name in REQUIRED_API_KEYS if os.environ.get(name)]
    missing = [name for name in REQUIRED_API_KEYS if name not in present]
    return present, missing


LOADED_SECRET_FILES = load_startup_secrets()
