"""
Tests for the ProviderAdapter abstraction and image-gen adapters.

Live provider calls are skipped when API keys are absent.
"""

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from google.genai import errors as genai_errors

from app.providers import ImageProviderAuthError, ImageProviderQuotaError
from app.providers.base import MissingApiKeyError, ProviderAdapter
from app.providers.gemini_flash import _GEMINI_MODEL, GeminiFlashImageAdapter
from app.providers.gpt_image import _GPT_IMAGE_MODEL, GptImageAdapter
from app.providers.image_prompt import enhance_landscape_render_prompt
from app.providers.image_provider import ImageProvider

_FAKE_JPEG = b"\xff\xd8\xff\xe0jpeg"
_FAKE_PNG = b"\x89PNG\r\n\x1a\npng"

# ---------------------------------------------------------------------------
# Structural / contract tests
# ---------------------------------------------------------------------------


def test_provider_adapter_is_abstract():
    """ProviderAdapter cannot be instantiated directly."""
    with pytest.raises(TypeError):
        ProviderAdapter()  # type: ignore[abstract]


def test_gemini_adapter_is_subclass():
    assert issubclass(GeminiFlashImageAdapter, ProviderAdapter)


def test_gpt_adapter_is_subclass():
    assert issubclass(GptImageAdapter, ProviderAdapter)


def test_image_provider_enum_has_both_providers():
    assert ImageProvider.GeminiFlashImage is not None
    assert ImageProvider.GptImage is not None


def test_image_provider_domain_exceptions_are_importable():
    assert issubclass(ImageProviderQuotaError, Exception)
    assert issubclass(ImageProviderAuthError, Exception)


def test_gemini_make_adapter_returns_instance():
    adapter = ImageProvider.GeminiFlashImage.make_adapter()
    assert isinstance(adapter, ProviderAdapter)
    assert isinstance(adapter, GeminiFlashImageAdapter)


def test_gpt_make_adapter_returns_instance():
    adapter = ImageProvider.GptImage.make_adapter()
    assert isinstance(adapter, ProviderAdapter)
    assert isinstance(adapter, GptImageAdapter)


def _recorded_gemini_quota_error() -> genai_errors.ClientError:
    return genai_errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "message": f"Quota exceeded for model {_GEMINI_MODEL}",
                "status": "RESOURCE_EXHAUSTED",
            }
        },
    )


def _recorded_gemini_auth_error() -> genai_errors.ClientError:
    return genai_errors.ClientError(
        401,
        {
            "error": {
                "code": 401,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "UNAUTHENTICATED",
            }
        },
    )


# ---------------------------------------------------------------------------
# Missing API key tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    adapter = GeminiFlashImageAdapter()
    with pytest.raises(MissingApiKeyError, match="GOOGLE_API_KEY"):
        await adapter.generate("aGVsbG8=", "add a deck")


@pytest.mark.asyncio
async def test_gemini_adapter_maps_resource_exhausted_to_quota_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    adapter = GeminiFlashImageAdapter()

    with (
        patch("app.providers.gemini_flash.genai.Client", return_value=SimpleNamespace()),
        patch.object(GeminiFlashImageAdapter, "_generate_one", new_callable=AsyncMock) as mock_gen,
    ):
        mock_gen.side_effect = _recorded_gemini_quota_error()
        with pytest.raises(ImageProviderQuotaError) as exc_info:
            await adapter.generate(base64.b64encode(_FAKE_JPEG).decode(), "add a deck")

    assert str(exc_info.value) == (
        f"Gemini quota exceeded for model {_GEMINI_MODEL}. Enable billing at "
        "https://aistudio.google.com/app/apikey or switch the Image Provider dropdown "
        "to GptImage for this request."
    )


@pytest.mark.asyncio
async def test_gemini_adapter_maps_401_to_auth_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    adapter = GeminiFlashImageAdapter()

    with (
        patch("app.providers.gemini_flash.genai.Client", return_value=SimpleNamespace()),
        patch.object(GeminiFlashImageAdapter, "_generate_one", new_callable=AsyncMock) as mock_gen,
    ):
        mock_gen.side_effect = _recorded_gemini_auth_error()
        with pytest.raises(ImageProviderAuthError):
            await adapter.generate(base64.b64encode(_FAKE_JPEG).decode(), "add a deck")


@pytest.mark.asyncio
async def test_gpt_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    adapter = GptImageAdapter()
    with pytest.raises(MissingApiKeyError, match="OPENAI_API_KEY"):
        await adapter.generate("aGVsbG8=", "add a fire feature")


@pytest.mark.asyncio
async def test_gpt_image_adapter_preserves_jpeg_input_mime(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    edit = AsyncMock(
        return_value=SimpleNamespace(
            data=[
                SimpleNamespace(b64_json=base64.b64encode(b"one").decode(), url=None),
                SimpleNamespace(b64_json=base64.b64encode(b"two").decode(), url=None),
                SimpleNamespace(b64_json=base64.b64encode(b"three").decode(), url=None),
            ]
        )
    )
    mock_client = SimpleNamespace(images=SimpleNamespace(edit=edit))

    with patch("app.providers.gpt_image.AsyncOpenAI", return_value=mock_client):
        await GptImageAdapter().generate(
            base64.b64encode(_FAKE_JPEG).decode(), "green"
        )

    image_arg = edit.call_args.kwargs["image"]
    assert image_arg[0] == "image.jpg"
    assert image_arg[2] == "image/jpeg"


@pytest.mark.asyncio
async def test_gpt_image_adapter_requests_gpt_image_2_medium_quality(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    edit = AsyncMock(
        return_value=SimpleNamespace(
            data=[
                SimpleNamespace(b64_json=base64.b64encode(b"one").decode(), url=None),
                SimpleNamespace(b64_json=base64.b64encode(b"two").decode(), url=None),
                SimpleNamespace(b64_json=base64.b64encode(b"three").decode(), url=None),
            ]
        )
    )
    mock_client = SimpleNamespace(images=SimpleNamespace(edit=edit))

    with patch("app.providers.gpt_image.AsyncOpenAI", return_value=mock_client):
        await GptImageAdapter().generate(
            base64.b64encode(_FAKE_JPEG).decode(), "add a cedar deck"
        )

    kwargs = edit.call_args.kwargs
    assert kwargs["model"] == "gpt-image-2"
    assert _GPT_IMAGE_MODEL == "gpt-image-2"
    assert kwargs["quality"] == "medium"
    assert "input_fidelity" not in kwargs
    assert "add a cedar deck" in kwargs["prompt"]
    assert "photorealistic" in kwargs["prompt"]
    assert "no labels or text" in kwargs["prompt"]


@pytest.mark.asyncio
async def test_gemini_adapter_preserves_png_input_mime(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    with (
        patch("app.providers.gemini_flash.genai.Client", return_value=SimpleNamespace()),
        patch.object(GeminiFlashImageAdapter, "_generate_one", new_callable=AsyncMock) as mock_gen,
    ):
        mock_gen.side_effect = [b"one", b"two", b"three"]
        result = await GeminiFlashImageAdapter().generate(
            base64.b64encode(_FAKE_PNG).decode(), "add a patio"
        )

    assert result == [b"one", b"two", b"three"]
    for call in mock_gen.call_args_list:
        assert call.args[2] == "image/png"


@pytest.mark.asyncio
async def test_gemini_adapter_uses_current_pro_image_model_and_enhanced_prompt():
    captured = {}

    def generate_content(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=b"image"))]
                    )
                )
            ]
        )

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    output = await GeminiFlashImageAdapter()._generate_one(
        client,
        _FAKE_JPEG,
        "image/jpeg",
        enhance_landscape_render_prompt("add a stone patio"),
    )

    assert output == b"image"
    assert captured["model"] == "gemini-3-pro-image-preview"
    assert captured["config"].response_modalities == ["IMAGE"]
    assert captured["config"].media_resolution is None
    prompt_part = captured["contents"][0].parts[1].text
    image_part = captured["contents"][0].parts[0]
    assert image_part.inline_data.mime_type == "image/jpeg"
    assert "add a stone patio" in prompt_part
    assert "photorealistic" in prompt_part


@pytest.mark.asyncio
async def test_gpt_image_adapter_rejects_unknown_image_type(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(ValueError, match="JPEG, PNG, or WebP"):
        await GptImageAdapter().generate(base64.b64encode(b"not an image").decode(), "green")


# ---------------------------------------------------------------------------
# Live provider tests (skipped without real keys)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="requires live GOOGLE_API_KEY and valid image")
@pytest.mark.asyncio
async def test_gemini_live_generate_returns_three_renders():
    import base64
    import os

    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set")

    # Provide a real base64-encoded JPEG to run this test manually.
    dummy_b64 = base64.b64encode(b"\xff\xd8\xff" + b"\x00" * 100).decode()
    adapter = GeminiFlashImageAdapter()
    renders = await adapter.generate(dummy_b64, "add a wooden deck with railing")
    assert len(renders) == 3
    assert all(isinstance(r, bytes) and len(r) > 0 for r in renders)


@pytest.mark.skip(reason="requires live OPENAI_API_KEY and valid image")
@pytest.mark.asyncio
async def test_gpt_live_generate_returns_three_renders():
    import base64
    import os

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    dummy_b64 = base64.b64encode(b"\x89PNG\r\n" + b"\x00" * 100).decode()
    adapter = GptImageAdapter()
    renders = await adapter.generate(dummy_b64, "add a pergola with string lights")
    assert len(renders) == 3
    assert all(isinstance(r, bytes) and len(r) > 0 for r in renders)
