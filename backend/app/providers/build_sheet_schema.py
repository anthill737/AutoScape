"""Shared Build Sheet JSON schema and prompt text used by every Materials LLM adapter.

Kept in one place so the three vendors produce the same shape and so structured-output
schemas (Anthropic ``output_config``, OpenAI ``json_schema``, Gemini ``response_schema``)
stay in sync with the prose description in the system prompt.
"""

from __future__ import annotations

import json

from app.domain.retailers import APPROVED_RETAILER_PROMPT_CONSTRAINT

# Product links are rebuilt server-side as retailer search URLs (see
# app.domain.build_sheet_validation), so the model is told NOT to invent them.
SYSTEM_PROMPT = (
    """You are a professional landscape contractor and cost estimator.
Given a rendered design image, project dimensions, quality tier, feature categories,
and product research data, generate a comprehensive build sheet.

"""
    + APPROVED_RETAILER_PROMPT_CONSTRAINT
    + """

Respond with ONLY valid JSON (no markdown, no explanation) matching this exact schema.
Keep it concise but complete: include 6-10 material items, 6-10 build steps, and 3-6
concrete assumptions. Leave "product_url" as an empty string; working retailer links are
added automatically from the item name and vendor.
{
  "material_items": [
    {
      "name": "string",
      "quantity": number,
      "unit": "string",
      "unit_cost_range": "string (e.g. '$12 - $15')",
      "total_cost_range": "string (e.g. '$144 - $180')",
      "vendor": "string (one of the approved retailers)",
      "product_url": "",
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

# Strict schema: every object lists all properties as required and forbids extras, which
# is what OpenAI strict mode and Anthropic structured outputs both expect.
BUILD_SHEET_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "material_items": {
            "type": "array",
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
                "additionalProperties": False,
            },
        },
        "tool_list": {"type": "array", "items": {"type": "string"}},
        "build_steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "number"},
                    "description": {"type": "string"},
                    "estimated_time": {"type": "string"},
                    "skill_notes": {"type": "string"},
                },
                "required": ["step_number", "description", "estimated_time", "skill_notes"],
                "additionalProperties": False,
            },
        },
        "total_cost_range": {"type": "string"},
        "skill_level": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "material_items",
        "tool_list",
        "build_steps",
        "total_cost_range",
        "skill_level",
        "assumptions",
    ],
    "additionalProperties": False,
}


def build_user_message(
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
        f"Product Research Data (from web search grounding):\n{search_str}\n\n"
        "Generate the build sheet JSON based on the rendered design image and the above context."
    )


def image_media_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
