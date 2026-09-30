import asyncio
import base64
import json
import os

import anthropic

from app.providers.base import MaterialsAdapter, MissingApiKeyError, missing_api_key_message
from app.providers.build_sheet_schema import (
    BUILD_SHEET_SCHEMA,
    SYSTEM_PROMPT,
    build_user_message,
    image_media_type,
    strip_code_fences,
)
from app.providers.model_catalog import default_model_for

# Default Anthropic model; any model from the catalog can be passed in.
_MODEL = default_model_for("claude_sonnet")
# Adaptive thinking (on by default on current models) draws from this budget too.
_MAX_BUILD_SHEET_TOKENS = 16000

# Kept as module attributes for existing tests / probe scripts.
_SYSTEM_PROMPT = SYSTEM_PROMPT
_BUILD_SHEET_SCHEMA = BUILD_SHEET_SCHEMA
_build_user_message = build_user_message
_image_media_type = image_media_type

from app.providers.dimension_defaults import (
    DIMENSION_SYSTEM_PROMPT as _DIMENSION_SYSTEM_PROMPT,
)
from app.providers.dimension_defaults import build_dimension_message as _build_dimension_message
from app.providers.dimension_defaults import parse_dimension_json


def _image_block(image_b64: str, media_type: str) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
    }


def _first_text(message) -> str:
    # Skip thinking blocks (which have no ``text``) and return the first text block.
    for block in message.content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            return text
    return ""


async def suggest_dimension_defaults(
    render_image_bytes: bytes,
    feature_categories: list[str],
    lot_size_sqft: float | None,
    house_sqft: float | None,
    model: str | None = None,
) -> dict:
    """Return a dict of dimension field names -> numeric string defaults using Claude."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise MissingApiKeyError(
            missing_api_key_message("ANTHROPIC_API_KEY", "dimension defaults")
        )

    image_b64 = base64.b64encode(render_image_bytes).decode()
    media_type = image_media_type(render_image_bytes)
    user_text = _build_dimension_message(feature_categories, lot_size_sqft, house_sqft)

    client = anthropic.Anthropic(api_key=api_key)
    loop = asyncio.get_running_loop()
    raw = await loop.run_in_executor(
        None,
        lambda: _call_dimension_sync(client, image_b64, media_type, user_text, model or _MODEL),
    )
    return parse_dimension_json(raw)


def _call_dimension_sync(
    client: anthropic.Anthropic,
    image_b64: str,
    media_type: str,
    user_text: str,
    model: str = _MODEL,
) -> str:
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=_DIMENSION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [_image_block(image_b64, media_type), {"type": "text", "text": user_text}],
            }
        ],
    )
    return _first_text(message)


class ClaudeSonnetAdapter(MaterialsAdapter):
    """Materials LLM adapter for Anthropic Claude models."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or _MODEL

    async def suggest_dimension_defaults(
        self,
        render_image_bytes: bytes,
        feature_categories: list[str],
        lot_size_sqft: float | None,
        house_sqft: float | None,
    ) -> dict[str, str]:
        return await suggest_dimension_defaults(
            render_image_bytes, feature_categories, lot_size_sqft, house_sqft, model=self.model
        )

    async def generate_build_sheet(
        self,
        render_image_bytes: bytes,
        dimensions: dict,
        quality_tier: str,
        search_results: list[dict],
        feature_categories: list[str],
    ) -> dict:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message(
                    "ANTHROPIC_API_KEY", "the ClaudeSonnet materials provider"
                )
            )

        image_b64 = base64.b64encode(render_image_bytes).decode()
        media_type = image_media_type(render_image_bytes)
        user_text = build_user_message(
            dimensions, quality_tier, search_results, feature_categories
        )

        client = anthropic.Anthropic(api_key=api_key)
        response = await _call_claude(client, image_b64, media_type, user_text, self.model)
        if isinstance(response, dict):
            return response
        return json.loads(strip_code_fences(response))


async def _call_claude(
    client: anthropic.Anthropic,
    image_b64: str,
    media_type: str,
    user_text: str,
    model: str = _MODEL,
) -> dict | str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _call_claude_sync(client, image_b64, media_type, user_text, model),
    )


def _call_claude_sync(
    client: anthropic.Anthropic,
    image_b64: str,
    media_type: str,
    user_text: str,
    model: str = _MODEL,
) -> dict | str:
    # Structured outputs (output_config.format) guarantee schema-valid JSON in the first
    # text block. This replaces the old forced tool_choice, which current Claude models
    # reject with HTTP 400.
    message = client.messages.create(
        model=model,
        max_tokens=_MAX_BUILD_SHEET_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [_image_block(image_b64, media_type), {"type": "text", "text": user_text}],
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": BUILD_SHEET_SCHEMA}},
    )
    if getattr(message, "stop_reason", None) == "refusal":
        details = getattr(message, "stop_details", None)
        reason = getattr(details, "explanation", None) or "the request was declined"
        raise ValueError(f"Anthropic Claude refused the request: {reason}")

    text = _first_text(message)
    if not text.strip():
        raise ValueError("Anthropic Claude response did not include JSON content")
    return text
