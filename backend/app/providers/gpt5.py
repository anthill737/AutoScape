import base64
import json
import os

from openai import AsyncOpenAI

from app.domain.retailers import APPROVED_RETAILER_PROMPT_CONSTRAINT
from app.providers.base import MaterialsAdapter, MissingApiKeyError, missing_api_key_message

_MODEL = "gpt-5"
_MAX_COMPLETION_TOKENS = 8192

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


def _image_media_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _response_text(response) -> str:
    if not response.choices:
        raise ValueError("OpenAI GPT-5 response did not include any choices")

    choice = response.choices[0]
    content = choice.message.content
    if isinstance(content, str) and content.strip():
        return content

    finish_reason = getattr(choice, "finish_reason", None)
    raise ValueError(
        "OpenAI GPT-5 response did not include JSON content"
        + (f" (finish_reason={finish_reason})" if finish_reason else "")
    )


class Gpt5Adapter(MaterialsAdapter):
    """Materials LLM adapter for OpenAI gpt-5."""

    async def generate_build_sheet(
        self,
        render_image_bytes: bytes,
        dimensions: dict,
        quality_tier: str,
        search_results: list[dict],
        feature_categories: list[str],
    ) -> dict:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("OPENAI_API_KEY", "the Gpt5 materials provider")
            )

        image_b64 = base64.b64encode(render_image_bytes).decode()
        media_type = _image_media_type(render_image_bytes)
        user_text = _build_user_message(
            dimensions, quality_tier, search_results, feature_categories
        )

        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                        },
                        {"type": "text", "text": user_text},
                    ],
                },
            ],
            reasoning_effort="minimal",
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
        )
        return json.loads(_response_text(response))
