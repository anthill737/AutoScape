"""Dimension suggestions should work with whichever text vendor has a key."""

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.spaces import get_space
from app.providers import dimension_defaults as dd
from app.providers.base import MissingApiKeyError
from app.providers.materials_llm import MaterialsLLM

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50


def _only(monkeypatch, *names: str) -> None:
    for env in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    for env in names:
        monkeypatch.setenv(env, "test-key")


def test_pick_provider_prefers_requested_when_key_present(monkeypatch):
    _only(monkeypatch, "OPENAI_API_KEY", "GOOGLE_API_KEY")
    assert dd.pick_provider("gemini_pro") is MaterialsLLM.GeminiPro


def test_pick_provider_falls_back_in_preference_order(monkeypatch):
    _only(monkeypatch, "OPENAI_API_KEY")
    # Claude requested but no Anthropic key: OpenAI is the first configured vendor.
    assert dd.pick_provider("claude_sonnet") is MaterialsLLM.Gpt5
    _only(monkeypatch, "GOOGLE_API_KEY")
    assert dd.pick_provider(None) is MaterialsLLM.GeminiPro


def test_pick_provider_raises_clear_message_without_any_key(monkeypatch):
    _only(monkeypatch)
    with pytest.raises(MissingApiKeyError, match="No text-model API key is set"):
        dd.pick_provider("claude_sonnet")


def test_build_dimension_message_lists_expected_keys():
    text = dd.build_dimension_message(["Deck", "Pool"], 5000.0, None)
    assert "deck_width_ft" in text and "pool_depth_ft" in text
    assert "House size: unknown" in text
    assert "Lot size: 5000.0 sqft" in text
    assert "residential yard" in text
    # Exterior is the default space.
    assert text == dd.build_dimension_message(["Deck", "Pool"], 5000.0, None, get_space("exterior"))


def test_build_dimension_message_interior_lists_interior_keys_and_room_size():
    text = dd.build_dimension_message(
        ["Cabinets", "Flooring", "Lighting"],
        None,
        None,
        space=get_space("interior"),
        space_details={"room_length_ft": 14, "room_width_ft": 12},
    )
    assert (
        "Return these keys: cabinet_linear_ft, upper_cabinet_linear_ft, floor_sqft, fixture_count"
        in text
    )
    assert "Room length: 14 ft" in text
    assert "Room width: 12 ft" in text
    assert "Ceiling height: unknown" in text
    assert "interior room" in text
    assert "Lot size" not in text and "House size" not in text
    assert "deck_width_ft" not in text


def test_build_dimension_message_interior_without_categories():
    text = dd.build_dimension_message([], None, None, space=get_space("interior"))
    assert "Feature Categories: General remodel" in text
    assert "your choice of snake_case *_ft keys" in text


@pytest.mark.asyncio
async def test_suggest_forwards_space_and_details_to_the_adapter(monkeypatch):
    _only(monkeypatch, "ANTHROPIC_API_KEY")
    seen: dict = {}

    class FakeAdapter:
        def __init__(self, model=None):
            pass

        async def suggest_dimension_defaults(self, **kwargs):
            seen.update(kwargs)
            return {"floor_sqft": "168"}

    interior = get_space("interior")
    with patch.object(MaterialsLLM, "make_adapter", lambda self, model=None: FakeAdapter(model)):
        result = await dd.suggest_dimension_defaults(
            _PNG,
            ["Flooring"],
            None,
            None,
            space=interior,
            space_details={"room_length_ft": 14, "room_width_ft": 12},
        )

    assert result == {"floor_sqft": "168"}
    assert seen["space"] is interior
    assert seen["space_details"] == {"room_length_ft": 14, "room_width_ft": 12}


def test_parse_dimension_json_strips_fences_and_normalises_values():
    raw = '```json\n{"deck_width_ft": 12, "deck_length_ft": "16", "skip": null}\n```'
    assert dd.parse_dimension_json(raw) == {"deck_width_ft": "12", "deck_length_ft": "16"}


@pytest.mark.asyncio
async def test_suggest_uses_fallback_vendor_and_ignores_foreign_model(monkeypatch):
    _only(monkeypatch, "OPENAI_API_KEY")
    seen: dict = {}

    class FakeAdapter:
        def __init__(self, model=None):
            seen["model"] = model

        async def suggest_dimension_defaults(self, **kwargs):
            seen["kwargs"] = kwargs
            return {"deck_width_ft": "12"}

    with patch.object(MaterialsLLM, "make_adapter", lambda self, model=None: FakeAdapter(model)):
        result = await dd.suggest_dimension_defaults(
            _PNG, ["Deck"], 5000.0, 2000.0, materials_llm="claude_sonnet", model="claude-opus-5-5"
        )

    assert result == {"deck_width_ft": "12"}
    # The Claude model id must not be sent to the OpenAI adapter that actually ran.
    assert seen["model"] is None
    assert seen["kwargs"]["feature_categories"] == ["Deck"]


@pytest.mark.asyncio
async def test_gpt5_adapter_suggests_dimensions_with_json_mode(monkeypatch):
    import unittest.mock

    import app.providers.gpt5 as _mod

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    message = unittest.mock.MagicMock()
    message.content = '{"deck_width_ft": "12", "deck_length_ft": "16"}'
    message.refusal = None
    choice = unittest.mock.MagicMock()
    choice.message = message
    response = unittest.mock.MagicMock()
    response.choices = [choice]
    client = unittest.mock.AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    monkeypatch.setattr(_mod, "AsyncOpenAI", unittest.mock.MagicMock(return_value=client))

    result = await _mod.Gpt5Adapter(model="gpt-6-luna").suggest_dimension_defaults(
        render_image_bytes=_PNG, feature_categories=["Deck"], lot_size_sqft=5000.0, house_sqft=None
    )

    assert result == {"deck_width_ft": "12", "deck_length_ft": "16"}
    kwargs = client.chat.completions.create.await_args.kwargs
    assert kwargs["model"] == "gpt-6-luna"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["messages"][1]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_gemini_adapter_suggests_dimensions(monkeypatch):
    import unittest.mock

    import app.providers.gemini_pro as _mod

    monkeypatch.setenv("GOOGLE_API_KEY", "g-test")
    response = unittest.mock.MagicMock()
    response.text = '{"pool_width_ft": "14"}'
    client = unittest.mock.MagicMock()
    client.models.generate_content.return_value = response
    monkeypatch.setattr(_mod.genai, "Client", unittest.mock.MagicMock(return_value=client))

    result = await _mod.GeminiProAdapter().suggest_dimension_defaults(
        render_image_bytes=_PNG, feature_categories=["Pool"], lot_size_sqft=None, house_sqft=None
    )

    assert result == {"pool_width_ft": "14"}
    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["config"].response_mime_type == "application/json"
    assert kwargs["contents"][0].parts[0].inline_data.mime_type == "image/png"
