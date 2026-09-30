import asyncio
import json
import os

from google import genai
from google.genai import types

from app.domain.spaces import SpaceConfig
from app.providers.base import MaterialsAdapter, MissingApiKeyError, missing_api_key_message
from app.providers.build_sheet_schema import (
    SYSTEM_PROMPT,
    build_user_message,
    image_media_type,
    strip_code_fences,
    system_prompt_for,
)
from app.providers.dimension_defaults import (
    DIMENSION_SYSTEM_PROMPT,
    build_dimension_message,
    parse_dimension_json,
)
from app.providers.model_catalog import default_model_for

# Default Gemini text model; any generateContent-capable Gemini model can be passed in.
_MODEL = default_model_for("gemini_pro")
_MAX_OUTPUT_TOKENS = 16384

# Kept as module attributes for existing tests / probe scripts.
_SYSTEM_PROMPT = SYSTEM_PROMPT
_build_user_message = build_user_message
_normalize_json_response = strip_code_fences


class GeminiProAdapter(MaterialsAdapter):
    """Materials LLM adapter for Google Gemini text models."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or _MODEL

    async def suggest_dimension_defaults(
        self,
        render_image_bytes: bytes,
        feature_categories: list[str],
        lot_size_sqft: float | None,
        house_sqft: float | None,
        space: SpaceConfig | None = None,
        space_details: dict | None = None,
    ) -> dict[str, str]:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("GOOGLE_API_KEY", "dimension defaults")
            )

        client = genai.Client(api_key=api_key)
        user_text = build_dimension_message(
            feature_categories, lot_size_sqft, house_sqft, space=space, space_details=space_details
        )
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: _extract_response_text(
                client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Content(
                            parts=[
                                types.Part(
                                    inline_data=types.Blob(
                                        mime_type=image_media_type(render_image_bytes),
                                        data=render_image_bytes,
                                    )
                                ),
                                types.Part(text=user_text),
                            ]
                        )
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=DIMENSION_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        max_output_tokens=4096,
                    ),
                )
            ),
        )
        return parse_dimension_json(raw)

    async def generate_build_sheet(
        self,
        render_image_bytes: bytes,
        dimensions: dict,
        quality_tier: str,
        search_results: list[dict],
        feature_categories: list[str],
        space: SpaceConfig | None = None,
    ) -> dict:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("GOOGLE_API_KEY", "the GeminiPro materials provider")
            )

        user_text = build_user_message(
            dimensions, quality_tier, search_results, feature_categories, space=space
        )

        client = genai.Client(api_key=api_key)
        response = await _call_gemini_pro(
            client,
            render_image_bytes,
            user_text,
            self.model,
            system_prompt=system_prompt_for(space),
        )
        return json.loads(strip_code_fences(response))


async def _call_gemini_pro(
    client: genai.Client,
    render_image_bytes: bytes,
    user_text: str,
    model: str = _MODEL,
    system_prompt: str = SYSTEM_PROMPT,
) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _call_gemini_pro_sync(
            client, render_image_bytes, user_text, model, system_prompt=system_prompt
        ),
    )


def _call_gemini_pro_sync(
    client: genai.Client,
    render_image_bytes: bytes,
    user_text: str,
    model: str = _MODEL,
    system_prompt: str = SYSTEM_PROMPT,
) -> str:
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                parts=[
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=image_media_type(render_image_bytes),
                            data=render_image_bytes,
                        )
                    ),
                    types.Part(text=user_text),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
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
