import json
import os

from google import genai
from google.genai import types

from app.domain.retailers import APPROVED_RETAILER_PROMPT_CONSTRAINT
from app.providers.base import MaterialsAdapter, MissingApiKeyError, missing_api_key_message

_MODEL = "gemini-2.5-pro"
_MAX_OUTPUT_TOKENS = 16384

_SYSTEM_PROMPT = (
    """You are a professional landscape contractor and cost estimator.
Given a rendered design image, project dimensions, quality tier, feature categories,
and product research data, generate a comprehensive build sheet.

"""
    + APPROVED_RETAILER_PROMPT_CONSTRAINT
    + """

Respond with ONLY valid JSON (no markdown, no explanation) matching this exact schema:
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
  "assumptions": ["string"]
}"""
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


class GeminiProAdapter(MaterialsAdapter):
    """Materials LLM adapter for Google gemini-2.5-pro."""

    async def generate_build_sheet(
        self,
        render_image_bytes: bytes,
        dimensions: dict,
        quality_tier: str,
        search_results: list[dict],
        feature_categories: list[str],
    ) -> dict:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("GOOGLE_API_KEY", "the GeminiPro materials provider")
            )

        user_text = _build_user_message(
            dimensions, quality_tier, search_results, feature_categories
        )

        client = genai.Client(api_key=api_key)
        response = await _call_gemini_pro(client, render_image_bytes, user_text)
        return json.loads(_normalize_json_response(response))


async def _call_gemini_pro(client: genai.Client, render_image_bytes: bytes, user_text: str) -> str:
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _call_gemini_pro_sync(client, render_image_bytes, user_text),
    )


def _call_gemini_pro_sync(client: genai.Client, render_image_bytes: bytes, user_text: str) -> str:
    response = client.models.generate_content(
        model=_MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="image/jpeg",
                            data=render_image_bytes,
                        )
                    ),
                    types.Part(text=user_text),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            max_output_tokens=_MAX_OUTPUT_TOKENS,
        ),
    )
    return _extract_response_text(response)


def _extract_response_text(response) -> str:
    text = getattr(response, "text", None)
    if text:
        return text

    parts_text: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts_text.append(part_text)

    if parts_text:
        return "".join(parts_text)

    finish_reasons = [
        str(getattr(candidate, "finish_reason", ""))
        for candidate in getattr(response, "candidates", []) or []
        if getattr(candidate, "finish_reason", None)
    ]
    reason = f" finish_reason={', '.join(finish_reasons)}" if finish_reasons else ""
    raise ValueError(f"GeminiPro returned no text content.{reason}")


def _normalize_json_response(response_text: str) -> str:
    stripped = response_text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
