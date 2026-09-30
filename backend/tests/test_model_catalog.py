"""Tests for the live model catalog and GET /api/models."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers import model_catalog as mc
from app.providers.image_provider import ImageProvider
from app.providers.materials_llm import MaterialsLLM


def test_every_provider_slug_has_a_default_and_fallbacks():
    slugs = {spec.slug for spec in mc.PROVIDERS}
    assert {p.value for p in ImageProvider} <= slugs
    assert {m.value for m in MaterialsLLM} <= slugs
    assert "perplexity" in slugs
    for spec in mc.PROVIDERS:
        assert spec.default_model in spec.fallback_models
        assert spec.role in mc.ROLES


def test_pretty_labels():
    assert mc._pretty("gpt-image-2.5-flare") == "GPT Image 2.5 Flare"
    assert mc._pretty("perplexity/sonar") == "Sonar"
    assert mc._pretty("gemini-3.1-flash-image") == "Gemini 3.1 Flash Image"


@pytest.mark.asyncio
async def test_missing_key_returns_fallback_without_calling_vendor(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    catalog = mc.ModelCatalog()
    spec = mc.PROVIDERS_BY_SLUG["gpt_image"]
    lister = AsyncMock()
    with _patched_lister(spec, lister):
        result = await catalog.provider_models(spec)
    assert result.source == "fallback"
    assert result.key_set is False
    assert [m.id for m in result.models] == list(spec.fallback_models)
    assert "OPENAI_API_KEY" in (result.error or "")
    lister.assert_not_called()


class _patched_lister:
    """ProviderSpec is frozen; swap the lister via object.__setattr__ for the test."""

    def __init__(self, spec: mc.ProviderSpec, lister):
        self.spec, self.lister, self.original = spec, lister, spec.lister

    def __enter__(self):
        object.__setattr__(self.spec, "lister", self.lister)

    def __exit__(self, *exc):
        object.__setattr__(self.spec, "lister", self.original)


@pytest.mark.asyncio
async def test_live_list_is_cached_until_refresh(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    catalog = mc.ModelCatalog()
    spec = mc.PROVIDERS_BY_SLUG["claude_sonnet"]
    lister = AsyncMock(return_value=[mc.ModelInfo("claude-opus-5-5", "Claude Opus 5.5")])
    with _patched_lister(spec, lister):
        first = await catalog.provider_models(spec)
        second = await catalog.provider_models(spec)
        third = await catalog.provider_models(spec, refresh=True)
    assert first.source == "live"
    assert second is first
    assert third is not first
    assert lister.await_count == 2


@pytest.mark.asyncio
async def test_vendor_failure_falls_back_and_reports_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g-test")
    catalog = mc.ModelCatalog()
    spec = mc.PROVIDERS_BY_SLUG["gemini_flash_image"]
    lister = AsyncMock(side_effect=RuntimeError("boom"))
    with _patched_lister(spec, lister):
        result = await catalog.provider_models(spec)
    assert result.source == "fallback"
    assert result.key_set is True
    assert "RuntimeError: boom" == result.error
    assert result.models[0].id == spec.default_model


@pytest.mark.asyncio
async def test_check_defaults_warns_when_default_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for name in ("GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    catalog = mc.ModelCatalog()
    image_spec = mc.PROVIDERS_BY_SLUG["gpt_image"]
    text_spec = mc.PROVIDERS_BY_SLUG["gpt5"]
    perplexity_spec = mc.PROVIDERS_BY_SLUG["perplexity"]
    with (
        _patched_lister(image_spec, AsyncMock(return_value=[mc.ModelInfo("gpt-image-9", "x")])),
        _patched_lister(text_spec, AsyncMock(return_value=[mc.ModelInfo(text_spec.default_model, "x")])),
        _patched_lister(perplexity_spec, AsyncMock(side_effect=RuntimeError("offline"))),
    ):
        warnings = await catalog.check_defaults()
    assert len(warnings) == 1
    assert warnings[0].startswith("gpt_image:")
    assert image_spec.default_model in warnings[0]


def test_api_models_groups_by_role(monkeypatch):
    for spec in mc.PROVIDERS:
        monkeypatch.delenv(spec.key_env, raising=False)
    perplexity_spec = mc.PROVIDERS_BY_SLUG["perplexity"]
    mc.catalog.clear()
    with _patched_lister(
        perplexity_spec,
        AsyncMock(return_value=[mc.ModelInfo("perplexity/sonar", "Sonar")]),
    ):
        with TestClient(app) as client:
            response = client.get("/api/models")
    mc.catalog.clear()

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"image", "materials", "grounding"}
    assert {p["slug"] for p in body["image"]} == {p.value for p in ImageProvider}
    assert {p["slug"] for p in body["materials"]} == {m.value for m in MaterialsLLM}
    grounding = body["grounding"][0]
    assert grounding["slug"] == "perplexity"
    assert grounding["source"] == "live"
    assert grounding["models"] == [{"id": "perplexity/sonar", "display_name": "Sonar"}]
    openai_image = next(p for p in body["image"] if p["slug"] == "gpt_image")
    assert openai_image["key_set"] is False
    assert openai_image["source"] == "fallback"
    assert openai_image["default_model"] in {m["id"] for m in openai_image["models"]}
