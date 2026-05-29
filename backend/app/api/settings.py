from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.bootstrap import REQUIRED_API_KEYS, reload_key_cache, secret_file_path

router = APIRouter(prefix="/api/settings", tags=["settings"])


class KeyValueIn(BaseModel):
    value: str


class KeyStatus(BaseModel):
    name: str
    set: bool
    masked_value: str | None


class KeyTestResult(BaseModel):
    ok: bool
    error: str | None = None


ProviderTester = Callable[[str], Awaitable[None]]


def _validate_key_name(name: str) -> None:
    if name not in REQUIRED_API_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown API key name: {name}")


def _mask_value(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "..." + value[-4:]
    return f"{value[:4]}...{value[-4:]}"


def _status_for(name: str) -> KeyStatus:
    value = os.environ.get(name)
    return KeyStatus(name=name, set=bool(value), masked_value=_mask_value(value))


async def _openai_tester(api_key: str) -> None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    await client.models.list()


async def _anthropic_tester(api_key: str) -> None:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    await client.models.list(limit=1)


async def _google_tester(api_key: str) -> None:
    from google import genai

    client = genai.Client(api_key=api_key)
    await asyncio.to_thread(lambda: list(client.models.list()))


async def _perplexity_tester(api_key: str) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": "Reply with ok."}],
                "max_tokens": 4,
            },
        )
        response.raise_for_status()


_PROVIDER_TESTERS: dict[str, ProviderTester] = {
    "GOOGLE_API_KEY": _google_tester,
    "OPENAI_API_KEY": _openai_tester,
    "ANTHROPIC_API_KEY": _anthropic_tester,
    "PERPLEXITY_API_KEY": _perplexity_tester,
}


@router.get("/keys", response_model=list[KeyStatus])
def list_keys() -> list[KeyStatus]:
    return [_status_for(name) for name in REQUIRED_API_KEYS]


@router.put("/keys/{name}", response_model=KeyStatus)
def save_key(name: str, payload: KeyValueIn) -> KeyStatus:
    _validate_key_name(name)
    value = payload.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="API key value cannot be empty")

    path = secret_file_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    reload_key_cache([name])
    return _status_for(name)


@router.delete("/keys/{name}", response_model=KeyStatus)
def clear_key(name: str) -> KeyStatus:
    _validate_key_name(name)
    path = secret_file_path(name)
    if path.exists():
        path.unlink()
    reload_key_cache([name])
    return _status_for(name)


@router.post(
    "/keys/{name}/test",
    response_model=KeyTestResult,
    response_model_exclude_none=True,
)
async def test_key(name: str) -> KeyTestResult:
    _validate_key_name(name)
    value = os.environ.get(name)
    if not value:
        return KeyTestResult(ok=False, error=f"{name} is not set")

    tester = _PROVIDER_TESTERS[name]
    try:
        await tester(value)
    except Exception as exc:  # pragma: no cover - exact provider exceptions vary.
        return KeyTestResult(ok=False, error=str(exc))
    return KeyTestResult(ok=True)
