import base64
import json
import os

from openai import AsyncOpenAI

from app.providers.base import MaterialsAdapter, MissingApiKeyError, missing_api_key_message
from app.providers.build_sheet_schema import (
    BUILD_SHEET_SCHEMA,
    SYSTEM_PROMPT,
    build_user_message,
    image_media_type,
)
from app.providers.dimension_defaults import (
    DIMENSION_SYSTEM_PROMPT,
    build_dimension_message,
    parse_dimension_json,
)
from app.providers.model_catalog import default_model_for

# Default OpenAI text model; any GPT-5.x / GPT-6.x model from the catalog can be passed in.
_MODEL = default_model_for("gpt5")
_MAX_COMPLETION_TOKENS = 16000
# "low" is accepted by every current GPT-5 / GPT-5.5 / GPT-5.6 / GPT-6 model. "minimal" is
# gpt-5 only and returns HTTP 400 on newer models.
_REASONING_EFFORT = "low"

# Kept as module attributes for existing tests / probe scripts.
_SYSTEM_PROMPT = SYSTEM_PROMPT
_build_user_message = build_user_message
_image_media_type = image_media_type


def _response_text(response) -> str:
    if not response.choices:
        raise ValueError("OpenAI response did not include any choices")

    choice = response.choices[0]
    refusal = getattr(choice.message, "refusal", None)
    if isinstance(refusal, str) and refusal.strip():
        raise ValueError(f"OpenAI refused the request: {refusal}")
    content = choice.message.content
    if isinstance(content, str) and content.strip():
        return content

    finish_reason = getattr(choice, "finish_reason", None)
    raise ValueError(
        "OpenAI response did not include JSON content"
        + (f" (finish_reason={finish_reason})" if finish_reason else "")
    )


class Gpt5Adapter(MaterialsAdapter):
    """Materials LLM adapter for OpenAI GPT text models (Chat Completions)."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or _MODEL

    async def suggest_dimension_defaults(
        self,
        render_image_bytes: bytes,
        feature_categories: list[str],
        lot_size_sqft: float | None,
        house_sqft: float | None,
    ) -> dict[str, str]:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("OPENAI_API_KEY", "dimension defaults")
            )

        image_b64 = base64.b64encode(render_image_bytes).decode()
        media_type = image_media_type(render_image_bytes)
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": DIMENSION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                        },
                        {
                            "type": "text",
                            "text": build_dimension_message(
                                feature_categories, lot_size_sqft, house_sqft
                            ),
                        },
                    ],
                },
            ],
            reasoning_effort=_REASONING_EFFORT,
            max_completion_tokens=4096,
        )
        return parse_dimension_json(_response_text(response))

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
        media_type = image_media_type(render_image_bytes)
        user_text = build_user_message(
            dimensions, quality_tier, search_results, feature_categories
        )

        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=self.model,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "build_sheet",
                    "strict": True,
                    "schema": BUILD_SHEET_SCHEMA,
                },
            },
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
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
            reasoning_effort=_REASONING_EFFORT,
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
        )
        return json.loads(_response_text(response))
