"""
Tests for the MaterialsAdapter abstraction and Materials LLM adapters.

Live provider calls are skipped when API keys are absent.
"""

import json
import unittest.mock

import pytest

from app.domain.retailers import APPROVED_RETAILER_PROMPT_CONSTRAINT, APPROVED_RETAILERS
from app.providers.base import MaterialsAdapter, MissingApiKeyError
from app.providers.claude_sonnet import ClaudeSonnetAdapter
from app.providers.gemini_pro import _MAX_OUTPUT_TOKENS, GeminiProAdapter
from app.providers.gpt5 import Gpt5Adapter
from app.providers.materials_llm import MaterialsLLM

_HOME_DEPOT = APPROVED_RETAILERS[0]

# ---------------------------------------------------------------------------
# Structural / contract tests
# ---------------------------------------------------------------------------


def test_materials_adapter_is_abstract():
    """MaterialsAdapter cannot be instantiated directly."""
    with pytest.raises(TypeError):
        MaterialsAdapter()  # type: ignore[abstract]


def test_claude_sonnet_is_subclass():
    assert issubclass(ClaudeSonnetAdapter, MaterialsAdapter)


def test_gpt5_is_subclass():
    assert issubclass(Gpt5Adapter, MaterialsAdapter)


def test_gemini_pro_is_subclass():
    assert issubclass(GeminiProAdapter, MaterialsAdapter)


def test_materials_llm_enum_has_all_three():
    assert MaterialsLLM.ClaudeSonnet is not None
    assert MaterialsLLM.Gpt5 is not None
    assert MaterialsLLM.GeminiPro is not None


def test_all_materials_system_prompts_include_approved_retailer_constraint():
    import app.providers.claude_sonnet as claude_sonnet
    import app.providers.gemini_pro as gemini_pro
    import app.providers.gpt5 as gpt5

    for prompt in (
        claude_sonnet._SYSTEM_PROMPT,
        gpt5._SYSTEM_PROMPT,
        gemini_pro._SYSTEM_PROMPT,
    ):
        assert APPROVED_RETAILER_PROMPT_CONSTRAINT in prompt


def test_claude_make_adapter_returns_instance():
    adapter = MaterialsLLM.ClaudeSonnet.make_adapter()
    assert isinstance(adapter, MaterialsAdapter)
    assert isinstance(adapter, ClaudeSonnetAdapter)


def test_gpt5_make_adapter_returns_instance():
    adapter = MaterialsLLM.Gpt5.make_adapter()
    assert isinstance(adapter, MaterialsAdapter)
    assert isinstance(adapter, Gpt5Adapter)


def test_gemini_pro_make_adapter_returns_instance():
    adapter = MaterialsLLM.GeminiPro.make_adapter()
    assert isinstance(adapter, MaterialsAdapter)
    assert isinstance(adapter, GeminiProAdapter)


# ---------------------------------------------------------------------------
# Missing API key tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claude_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    adapter = ClaudeSonnetAdapter()
    with pytest.raises(MissingApiKeyError, match="ANTHROPIC_API_KEY"):
        await adapter.generate_build_sheet(b"\xff\xd8\xff", {}, "Budget", [], ["Deck"])


@pytest.mark.asyncio
async def test_gpt5_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    adapter = Gpt5Adapter()
    with pytest.raises(MissingApiKeyError, match="OPENAI_API_KEY"):
        await adapter.generate_build_sheet(b"\xff\xd8\xff", {}, "Budget", [], ["Deck"])


@pytest.mark.asyncio
async def test_gemini_pro_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    adapter = GeminiProAdapter()
    with pytest.raises(MissingApiKeyError, match="GOOGLE_API_KEY"):
        await adapter.generate_build_sheet(b"\xff\xd8\xff", {}, "Budget", [], ["Deck"])


# ---------------------------------------------------------------------------
# Returned dict schema tests — mock at SDK client boundary
#
# Each test patches the underlying SDK client class so its completion method
# returns a stub response containing json.dumps(_MOCK_BUILD_SHEET).  The real
# generate_build_sheet implementation runs end-to-end: env-var check, image
# encoding, message assembly, JSON parse, and dict return are all exercised.
# ---------------------------------------------------------------------------

_MOCK_BUILD_SHEET = {
    "material_items": [
        {
            "name": "Pressure-treated 2x6 lumber",
            "quantity": 20,
            "unit": "board",
            "unit_cost_range": "$8 - $12",
            "total_cost_range": "$160 - $240",
            "vendor": _HOME_DEPOT["name"],
            "product_url": f"https://www.{_HOME_DEPOT['domain']}/p/123",
            "notes": "16-foot lengths",
        }
    ],
    "tool_list": ["Circular saw", "Drill", "Level", "Tape measure"],
    "build_steps": [
        {
            "step_number": 1,
            "description": "Mark and excavate footing locations",
            "estimated_time": "3 hours",
            "skill_notes": "Use a string line for alignment",
        }
    ],
    "total_cost_range": "$2,000 - $3,500",
    "skill_level": "Intermediate",
    "assumptions": ["Standard 12x16 ft deck", "Level ground assumed"],
}


@pytest.mark.asyncio
async def test_claude_returns_correct_schema(monkeypatch):
    """ClaudeSonnetAdapter returns a dict with all required Build Sheet keys.

    Patches anthropic.Anthropic so the real generate_build_sheet runs through
    the env-var guard, base64 encoding, message construction, and json.loads.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

    import app.providers.claude_sonnet as _mod

    mock_response = unittest.mock.MagicMock()
    mock_response.content = [unittest.mock.MagicMock(text=json.dumps(_MOCK_BUILD_SHEET))]
    mock_client = unittest.mock.MagicMock()
    mock_client.messages.create.return_value = mock_response

    mock_anthropic = unittest.mock.MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    monkeypatch.setattr(_mod, "anthropic", mock_anthropic)

    adapter = ClaudeSonnetAdapter()
    result = await adapter.generate_build_sheet(b"\xff\xd8\xff", {}, "Budget", [], ["Deck"])
    _assert_build_sheet_schema(result)


@pytest.mark.asyncio
async def test_dimension_defaults_send_png_media_type_for_png_render(monkeypatch):
    """Regression for PNG render bytes being mislabeled as JPEG for Anthropic."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

    import app.providers.claude_sonnet as _mod

    mock_response = unittest.mock.MagicMock()
    mock_response.content = [unittest.mock.MagicMock(text='{"deck_width_ft": "12"}')]
    mock_client = unittest.mock.MagicMock()
    mock_client.messages.create.return_value = mock_response

    mock_anthropic = unittest.mock.MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    monkeypatch.setattr(_mod, "anthropic", mock_anthropic)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    result = await _mod.suggest_dimension_defaults(png_bytes, ["Deck"], 5000.0, 2000.0)

    image_part = mock_client.messages.create.call_args.kwargs["messages"][0]["content"][0]
    assert image_part["source"]["media_type"] == "image/png"
    assert result == {"deck_width_ft": "12"}


@pytest.mark.asyncio
async def test_gpt5_returns_correct_schema(monkeypatch):
    """Gpt5Adapter returns a dict with all required Build Sheet keys.

    Patches AsyncOpenAI so the real generate_build_sheet runs through the
    env-var guard, base64 encoding, message construction, and json.loads.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")

    import app.providers.gpt5 as _mod

    mock_message = unittest.mock.MagicMock()
    mock_message.content = json.dumps(_MOCK_BUILD_SHEET)
    mock_choice = unittest.mock.MagicMock()
    mock_choice.message = mock_message
    mock_response = unittest.mock.MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = unittest.mock.AsyncMock()
    mock_client.chat.completions.create = unittest.mock.AsyncMock(return_value=mock_response)

    monkeypatch.setattr(_mod, "AsyncOpenAI", unittest.mock.MagicMock(return_value=mock_client))

    adapter = Gpt5Adapter()
    result = await adapter.generate_build_sheet(b"\xff\xd8\xff", {}, "Budget", [], ["Deck"])
    request_kwargs = mock_client.chat.completions.create.await_args.kwargs
    assert request_kwargs["max_completion_tokens"] == _mod._MAX_COMPLETION_TOKENS
    assert "max_tokens" not in request_kwargs
    _assert_build_sheet_schema(result)


@pytest.mark.asyncio
async def test_gemini_pro_returns_correct_schema(monkeypatch):
    """GeminiProAdapter returns a dict with all required Build Sheet keys.

    Patches genai.Client so the real generate_build_sheet runs through the
    env-var guard, message construction, run_in_executor dispatch, and json.loads.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "test-fake-key")

    import app.providers.gemini_pro as _mod

    mock_response = unittest.mock.MagicMock()
    mock_response.text = json.dumps(_MOCK_BUILD_SHEET)
    mock_client = unittest.mock.MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    mock_genai = unittest.mock.MagicMock()
    mock_genai.Client.return_value = mock_client
    monkeypatch.setattr(_mod, "genai", mock_genai)

    adapter = GeminiProAdapter()
    result = await adapter.generate_build_sheet(b"\xff\xd8\xff", {}, "Budget", [], ["Deck"])
    request_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert request_kwargs["config"].max_output_tokens == _MAX_OUTPUT_TOKENS
    assert _MAX_OUTPUT_TOKENS >= 8192
    _assert_build_sheet_schema(result)


@pytest.mark.asyncio
async def test_gemini_pro_reads_candidate_part_text_and_strips_json_fence(monkeypatch):
    """Regression for Gemini responses where response.text is None."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-fake-key")

    import app.providers.gemini_pro as _mod

    fenced_json = "```json\n" + json.dumps(_MOCK_BUILD_SHEET) + "\n```"
    mock_response = unittest.mock.MagicMock()
    mock_response.text = None
    mock_response.candidates = [
        unittest.mock.MagicMock(
            content=unittest.mock.MagicMock(
                parts=[unittest.mock.MagicMock(text=fenced_json)]
            )
        )
    ]
    mock_client = unittest.mock.MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    mock_genai = unittest.mock.MagicMock()
    mock_genai.Client.return_value = mock_client
    monkeypatch.setattr(_mod, "genai", mock_genai)

    adapter = GeminiProAdapter()
    result = await adapter.generate_build_sheet(b"\xff\xd8\xff", {}, "Budget", [], ["Deck"])
    _assert_build_sheet_schema(result)


def _assert_build_sheet_schema(result: dict) -> None:
    required_keys = {
        "material_items",
        "tool_list",
        "build_steps",
        "total_cost_range",
        "skill_level",
        "assumptions",
    }
    assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
    assert isinstance(result["material_items"], list)
    assert isinstance(result["tool_list"], list)
    assert isinstance(result["build_steps"], list)
    assert isinstance(result["total_cost_range"], str)
    assert isinstance(result["skill_level"], str)
    assert isinstance(result["assumptions"], list)


# ---------------------------------------------------------------------------
# Enum extensibility test — adding a fourth LLM is one file + one entry
# ---------------------------------------------------------------------------


def test_materials_llm_enum_values_encode_module_and_class():
    """Each enum entry carries its module path and class name for lazy-loading."""
    for member in MaterialsLLM:
        assert hasattr(member, "_module_path"), f"{member.name} missing _module_path"
        assert hasattr(member, "_class_name"), f"{member.name} missing _class_name"
        assert member._module_path.startswith("app.providers.")
        assert member._class_name.endswith("Adapter")
