"""Live model catalog: which models each vendor currently offers for each role.

The app has three model *roles*:

* ``image``      - edit the site photo into a rendered design (OpenAI Images, Gemini image)
* ``materials``  - turn the chosen render into a Build Sheet (Anthropic, OpenAI, Gemini text)
* ``grounding``  - web-grounded product research (Perplexity Agent API)

Each role is served by one or more *providers* (a vendor + adapter pair, identified by
the stable slug the API and database already use, e.g. ``gpt_image``). For every
provider this module can list the models the vendor's API currently exposes, filtered
down to the ones that fit the role, so the UI can offer any available model instead of
a hardcoded one. Results are cached for a short TTL. When the key is missing or the
vendor call fails we fall back to a static list so the UI still works offline.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from app.providers.model_metadata import ModelMeta, annotate

logger = logging.getLogger(__name__)

CATALOG_TTL_SECONDS = 600
_VENDOR_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    # Curated quality / cost / status; see app.providers.model_metadata.
    meta: ModelMeta = field(default_factory=ModelMeta, compare=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "display_name": self.display_name, **self.meta.to_dict()}


Lister = Callable[[str], Awaitable[list[ModelInfo]]]


@dataclass(frozen=True)
class ProviderSpec:
    slug: str
    role: str
    vendor: str
    label: str
    key_env: str
    default_model: str
    fallback_models: tuple[str, ...]
    lister: Lister = field(repr=False, compare=False)


@dataclass
class ProviderModels:
    spec: ProviderSpec
    models: list[ModelInfo]
    source: str  # "live" | "fallback"
    key_set: bool
    error: str | None = None
    fetched_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "slug": self.spec.slug,
            "role": self.spec.role,
            "vendor": self.spec.vendor,
            "label": self.spec.label,
            "key_env": self.spec.key_env,
            "key_set": self.key_set,
            "default_model": self.spec.default_model,
            "models": [m.to_dict() for m in self.models],
            "source": self.source,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Vendor listers
# ---------------------------------------------------------------------------

_OPENAI_TEXT_EXCLUDE = re.compile(
    r"(image|audio|realtime|transcribe|tts|search|embedding|moderation|"
    r"codex|chat-latest|-pro\b|-cyber|-live|instruct|deep-research|computer-use)",
)
_OPENAI_TEXT_INCLUDE = re.compile(r"^(gpt-5|gpt-6)")


def _pretty(model_id: str) -> str:
    """Turn ``gpt-image-2.5-flare`` into ``GPT Image 2.5 Flare`` style labels."""
    name = model_id.split("/", 1)[-1]
    words = []
    for token in name.split("-"):
        if not token:
            continue
        if token.lower() in {"gpt", "tts"}:
            words.append(token.upper())
        elif token[0].isdigit():
            words.append(token)
        else:
            words.append(token.capitalize())
    return " ".join(words)


async def _openai_models(api_key: str) -> list[dict]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, timeout=_VENDOR_TIMEOUT_SECONDS)
    page = await client.models.list()
    return [{"id": m.id, "created": getattr(m, "created", 0) or 0} for m in page.data]


async def list_openai_image_models(api_key: str) -> list[ModelInfo]:
    models = await _openai_models(api_key)
    picked = [m for m in models if m["id"].startswith("gpt-image")]
    picked.sort(key=lambda m: (-m["created"], m["id"]))
    return [ModelInfo(m["id"], _pretty(m["id"])) for m in picked]


async def list_openai_text_models(api_key: str) -> list[ModelInfo]:
    models = await _openai_models(api_key)
    picked = [
        m
        for m in models
        if _OPENAI_TEXT_INCLUDE.search(m["id"]) and not _OPENAI_TEXT_EXCLUDE.search(m["id"])
    ]
    picked.sort(key=lambda m: (-m["created"], m["id"]))
    return [ModelInfo(m["id"], _pretty(m["id"])) for m in picked]


async def list_anthropic_models(api_key: str) -> list[ModelInfo]:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=_VENDOR_TIMEOUT_SECONDS)
    result: list[ModelInfo] = []
    async for m in client.models.list(limit=100):
        result.append(ModelInfo(m.id, m.display_name or _pretty(m.id)))
    return result


def _google_models_sync(api_key: str) -> list[tuple[str, str, list[str]]]:
    from google import genai

    client = genai.Client(api_key=api_key)
    rows: list[tuple[str, str, list[str]]] = []
    for m in client.models.list():
        name = (m.name or "").removeprefix("models/")
        if not name:
            continue
        rows.append((name, m.display_name or _pretty(name), list(m.supported_actions or [])))
    return rows


_GOOGLE_TEXT_EXCLUDE = re.compile(r"(-image|-tts|-audio|-live|embedding|robotics|computer-use|aqa)")


async def list_google_image_models(api_key: str) -> list[ModelInfo]:
    rows = await asyncio.to_thread(_google_models_sync, api_key)
    return [
        ModelInfo(name, display)
        for name, display, actions in rows
        if "generateContent" in actions and "-image" in name
    ]


async def list_google_text_models(api_key: str) -> list[ModelInfo]:
    rows = await asyncio.to_thread(_google_models_sync, api_key)
    return [
        ModelInfo(name, display)
        for name, display, actions in rows
        if "generateContent" in actions
        and name.startswith("gemini-")
        and not _GOOGLE_TEXT_EXCLUDE.search(name)
    ]


PERPLEXITY_MODELS_URL = "https://api.perplexity.ai/v1/models"


async def list_perplexity_models(api_key: str) -> list[ModelInfo]:
    # The Agent API model list is public; the key is accepted but not required.
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=_VENDOR_TIMEOUT_SECONDS) as client:
        response = await client.get(PERPLEXITY_MODELS_URL, headers=headers)
        response.raise_for_status()
        data = response.json()
    ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
    # Perplexity's own model first, then the rest alphabetically.
    ids.sort(key=lambda i: (not i.startswith("perplexity/"), i))
    return [ModelInfo(i, _pretty(i)) for i in ids]


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        slug="gpt_image",
        role="image",
        vendor="openai",
        label="OpenAI Images",
        key_env="OPENAI_API_KEY",
        default_model="gpt-image-2.5-flare",
        fallback_models=("gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "gpt-image-2"),
        lister=list_openai_image_models,
    ),
    ProviderSpec(
        slug="gemini_flash_image",
        role="image",
        vendor="google",
        label="Google Gemini Images",
        key_env="GOOGLE_API_KEY",
        default_model="gemini-3.1-flash-image",
        fallback_models=(
            "gemini-3.1-flash-image",
            "gemini-3.1-flash-lite-image",
            "gemini-3-pro-image",
        ),
        lister=list_google_image_models,
    ),
    ProviderSpec(
        slug="claude_sonnet",
        role="materials",
        vendor="anthropic",
        label="Anthropic Claude",
        key_env="ANTHROPIC_API_KEY",
        default_model="claude-opus-5-5",
        fallback_models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"),
        lister=list_anthropic_models,
    ),
    ProviderSpec(
        slug="gpt5",
        role="materials",
        vendor="openai",
        label="OpenAI GPT",
        key_env="OPENAI_API_KEY",
        default_model="gpt-5.6-terra",
        fallback_models=(
            "gpt-5.6-terra",
            "gpt-5.6-sol",
            "gpt-5.6-luna",
            "gpt-6-astra",
            "gpt-6-luna",
            "gpt-5.5",
        ),
        lister=list_openai_text_models,
    ),
    ProviderSpec(
        slug="gemini_pro",
        role="materials",
        vendor="google",
        label="Google Gemini",
        key_env="GOOGLE_API_KEY",
        default_model="gemini-3.8-flash",
        fallback_models=("gemini-3.8-flash", "gemini-3.1-pro-preview", "gemini-3.5-flash-lite"),
        lister=list_google_text_models,
    ),
    ProviderSpec(
        slug="perplexity",
        role="grounding",
        vendor="perplexity",
        label="Perplexity Agent API",
        key_env="PERPLEXITY_API_KEY",
        default_model="perplexity/sonar",
        fallback_models=("perplexity/sonar",),
        lister=list_perplexity_models,
    ),
)

PROVIDERS_BY_SLUG: dict[str, ProviderSpec] = {spec.slug: spec for spec in PROVIDERS}
ROLES: tuple[str, ...] = ("image", "materials", "grounding")


def default_model_for(slug: str) -> str:
    return PROVIDERS_BY_SLUG[slug].default_model


def annotate_models(spec: ProviderSpec, models: list[ModelInfo]) -> list[ModelInfo]:
    """Attach curated metadata and order: default first, then current models by quality,
    then everything else (snapshots, retired ids) so the UI can fold them away."""
    annotated = [
        ModelInfo(m.id, m.display_name, annotate(spec.slug, m.id)) for m in models
    ]
    annotated.sort(
        key=lambda m: (
            m.id != spec.default_model,
            not m.meta.current,
            -(m.meta.quality or 0),
            m.meta.cost_rank or 99,
            m.id,
        )
    )
    return annotated


# ---------------------------------------------------------------------------
# Catalog with cache
# ---------------------------------------------------------------------------


class ModelCatalog:
    """Fetches and caches per-provider model lists."""

    def __init__(self, ttl_seconds: float = CATALOG_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._cache: dict[str, ProviderModels] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, slug: str) -> asyncio.Lock:
        lock = self._locks.get(slug)
        if lock is None:
            lock = self._locks[slug] = asyncio.Lock()
        return lock

    @staticmethod
    def _fallback(spec: ProviderSpec, key_set: bool, error: str | None) -> ProviderModels:
        models = annotate_models(spec, [ModelInfo(m, _pretty(m)) for m in spec.fallback_models])
        return ProviderModels(
            spec=spec,
            models=models,
            source="fallback",
            key_set=key_set,
            error=error,
            fetched_at=time.monotonic(),
        )

    async def provider_models(self, spec: ProviderSpec, refresh: bool = False) -> ProviderModels:
        api_key = os.environ.get(spec.key_env, "")
        key_set = bool(api_key)
        cached = self._cache.get(spec.slug)
        if (
            cached is not None
            and not refresh
            and cached.key_set == key_set
            and time.monotonic() - cached.fetched_at < self._ttl
        ):
            return cached

        async with self._lock_for(spec.slug):
            cached = self._cache.get(spec.slug)
            if (
                cached is not None
                and not refresh
                and cached.key_set == key_set
                and time.monotonic() - cached.fetched_at < self._ttl
            ):
                return cached

            # Perplexity's list endpoint is public; every other vendor needs a key.
            if not key_set and spec.vendor != "perplexity":
                result = self._fallback(spec, key_set, f"{spec.key_env} is not set")
            else:
                try:
                    models = await spec.lister(api_key)
                    if not models:
                        raise ValueError("vendor returned no models for this role")
                    models = annotate_models(spec, models)
                    result = ProviderModels(
                        spec=spec,
                        models=models,
                        source="live",
                        key_set=key_set,
                        fetched_at=time.monotonic(),
                    )
                except Exception as exc:  # noqa: BLE001 - any vendor failure -> fallback list
                    logger.warning(
                        "[models] %s list failed (%s: %s); using fallback list",
                        spec.slug,
                        exc.__class__.__name__,
                        exc,
                    )
                    result = self._fallback(spec, key_set, f"{exc.__class__.__name__}: {exc}")

            self._cache[spec.slug] = result
            return result

    async def catalog(self, refresh: bool = False) -> dict[str, list[dict]]:
        results = await asyncio.gather(
            *(self.provider_models(spec, refresh=refresh) for spec in PROVIDERS)
        )
        out: dict[str, list[dict]] = {role: [] for role in ROLES}
        for pm in results:
            out[pm.spec.role].append(pm.to_dict())
        return out

    async def check_defaults(self) -> list[str]:
        """Return warnings for providers whose default model is missing from the live list."""
        warnings: list[str] = []
        results = await asyncio.gather(*(self.provider_models(spec) for spec in PROVIDERS))
        for pm in results:
            if pm.source != "live":
                continue
            ids = {m.id for m in pm.models}
            if pm.spec.default_model not in ids:
                warnings.append(
                    f"{pm.spec.slug}: default model {pm.spec.default_model!r} is not in the "
                    f"vendor's current list ({len(ids)} models); pick another in the UI or "
                    "update PROVIDERS in app/providers/model_catalog.py"
                )
        return warnings

    def clear(self) -> None:
        self._cache.clear()


catalog = ModelCatalog()
