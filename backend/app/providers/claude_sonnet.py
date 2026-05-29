import asyncio
import base64
import json
import os

import anthropic

from app.domain.retailers import APPROVED_RETAILER_PROMPT_CONSTRAINT
from app.providers.base import MaterialsAdapter, MissingApiKeyError, missing_api_key_message

_MODEL = "claude-sonnet-4-6"
_MAX_BUILD_SHEET_TOKENS = 8192

_SYSTEM_PROMPT = (
    """You are a professional landscape contractor and cost estimator.
Given a rendered design image, project dimensions, quality tier, feature categories,
and product research data, generate a comprehensive build sheet.

"""
    + APPROVED_RETAILER_PROMPT_CONSTRAINT
    + """

Respond with ONLY valid JSON (no markdown, no explanation) matching this exact schema.
Keep it concise but complete: include 6-10 material items, 6-10 build steps, and 3-6
concrete assumptions.
{
  "material_items": [
    {
      "name": "string",
      "quantity": number,
      "unit": "string",
      "unit_cost_range": "string (e.g. '$12 - $15')",
      "total_cost_range": "string (e.g. '$144 - $180')",
      "vendor": "string",
      "product_url": "string (real URL from search results or empty string)",
      "notes": "string"
    }
  ],
  "tool_list": ["string"],
  "build_steps": [
    {
      "step_number": number,
      "description": "string",
      "estimated_time": "string (e.g. '2 hours')",
      "skill_notes": "string"
    }
  ],
  "total_cost_range": "string (e.g. '$3,500 - $5,200')",
  "skill_level": "string (Beginner | Intermediate | Advanced)",
  "assumptions": ["string (include at least 3 concrete assumptions)"]
}"""
)

_BUILD_SHEET_SCHEMA = {
    "type": "object",
    "properties": {
        "material_items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                    "unit_cost_range": {"type": "string"},
                    "total_cost_range": {"type": "string"},
                    "vendor": {"type": "string"},
                    "product_url": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": [
                    "name",
                    "quantity",
                    "unit",
                    "unit_cost_range",
                    "total_cost_range",
                    "vendor",
                    "product_url",
                    "notes",
                ],
            },
        },
        "tool_list": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "build_steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "number"},
                    "description": {"type": "string"},
                    "estimated_time": {"type": "string"},
                    "skill_notes": {"type": "string"},
                },
                "required": [
                    "step_number",
                    "description",
                    "estimated_time",
                    "skill_notes",
                ],
            },
        },
        "total_cost_range": {"type": "string"},
        "skill_level": {"type": "string"},
        "assumptions": {"type": "array", "minItems": 1, "items": {"type": "string"}},
    },
    "required": [
        "material_items",
        "tool_list",
        "build_steps",
        "total_cost_range",
        "skill_level",
        "assumptions",
    ],
}

_DIMENSION_SYSTEM_PROMPT = (
    "You are a landscape design assistant. Given a rendered design image and project details, "
    "suggest reasonable default dimensions for the features present.\n\n"
    "Respond with ONLY valid JSON (no markdown, no explanation) where keys are snake_case "
    'dimension field names (e.g. "deck_width_ft", "deck_length_ft") and values are numeric '
    'strings (e.g. "12", "16").\n\n'
    "Rules:\n"
    "- Include all relevant dimensions for each feature category provided\n"
    "- Use feet as the unit suffix (e.g. _ft, _sqft)\n"
    "- Infer reasonable defaults from the image and lot size\n"
    "- Return only the JSON object, nothing else"
)


def _build_user_message(
    dimensions: dict,
    quality_tier: str,
    search_results: list[dict],
    feature_categories: list[str],
) -> str:
    features_str = ", ".join(feature_categories) if feature_categories else "General landscaping"
    dims_str = json.dumps(dimensions, indent=2) if dimensions else "{}"
    search_str = json.dumps(search_results[:25], indent=2) if search_results else "[]"
    return (
        f"Feature Categories: {features_str}\n"
        f"Quality Tier: {quality_tier}\n"
        f"Project Dimensions:\n{dims_str}\n\n"
        f"Product Research Data (from Perplexity Search Grounding):\n{search_str}\n\n"
        "Generate the build sheet JSON based on the rendered design image and the above context."
    )


def _build_dimension_message(
    feature_categories: list[str],
    lot_size_sqft: float | None,
    house_sqft: float | None,
) -> str:
    features_str = ", ".join(feature_categories) if feature_categories else "General landscaping"
    lot_str = f"{lot_size_sqft} sqft" if lot_size_sqft else "unknown"
    house_str = f"{house_sqft} sqft" if house_sqft else "unknown"
    return (
        f"Feature Categories: {features_str}\n"
        f"Lot size: {lot_str}\n"
        f"House size: {house_str}\n\n"
        "Based on the rendered design image and the project details above, "
        "suggest reasonable default dimensions for the features."
    )


def _image_media_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


async def suggest_dimension_defaults(
    render_image_bytes: bytes,
    feature_categories: list[str],
    lot_size_sqft: float | None,
    house_sqft: float | None,
) -> dict:
    """Return a dict of dimension field names → numeric string defaults using ClaudeSonnet."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise MissingApiKeyError(
            missing_api_key_message("ANTHROPIC_API_KEY", "dimension defaults")
        )

    image_b64 = base64.b64encode(render_image_bytes).decode()
    media_type = _image_media_type(render_image_bytes)
    user_text = _build_dimension_message(feature_categories, lot_size_sqft, house_sqft)

    client = anthropic.Anthropic(api_key=api_key)
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(
        None,
        lambda: _call_dimension_sync(client, image_b64, media_type, user_text),
    )
    return json.loads(raw)


def _call_dimension_sync(
    client: anthropic.Anthropic, image_b64: str, media_type: str, user_text: str
) -> str:
    message = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=_DIMENSION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        ],
    )
    return message.content[0].text


class ClaudeSonnetAdapter(MaterialsAdapter):
    """Materials LLM adapter for Anthropic claude-sonnet-4-6."""

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
        media_type = _image_media_type(render_image_bytes)
        user_text = _build_user_message(
            dimensions, quality_tier, search_results, feature_categories
        )

        client = anthropic.Anthropic(api_key=api_key)
        response = await _call_claude(client, image_b64, media_type, user_text)
        if isinstance(response, dict):
            return response
        return json.loads(response)


async def _call_claude(
    client: anthropic.Anthropic, image_b64: str, media_type: str, user_text: str
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _call_claude_sync(client, image_b64, media_type, user_text),
    )


def _call_claude_sync(
    client: anthropic.Anthropic, image_b64: str, media_type: str, user_text: str
) -> dict | str:
    message = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_BUILD_SHEET_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": user_text,
                    },
                ],
            }
        ],
        tools=[
            {
                "name": "generate_build_sheet",
                "description": "Return the structured materials and build-sheet payload.",
                "input_schema": _BUILD_SHEET_SCHEMA,
            }
        ],
        tool_choice={"type": "tool", "name": "generate_build_sheet"},
    )
    for block in message.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input

    text = getattr(message.content[0], "text", "")
    if not text.strip():
        raise ValueError("Anthropic Claude response did not include JSON content")
    return text
