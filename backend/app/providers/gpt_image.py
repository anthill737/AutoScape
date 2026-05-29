import base64
import io
import os

from openai import AsyncOpenAI

from app.providers.base import MissingApiKeyError, ProviderAdapter, missing_api_key_message
from app.providers.image_prompt import enhance_landscape_render_prompt

_GPT_IMAGE_MODEL = "gpt-image-2"


def _image_file_tuple(image_bytes: bytes) -> tuple[str, io.BytesIO, str]:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image.jpg", io.BytesIO(image_bytes), "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image.png", io.BytesIO(image_bytes), "image/png"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image.webp", io.BytesIO(image_bytes), "image/webp"
    raise ValueError("GptImage input image must be a JPEG, PNG, or WebP file.")


class GptImageAdapter(ProviderAdapter):
    """Image Provider adapter for OpenAI gpt-image-2."""

    async def generate(self, image_b64: str, prompt: str) -> list[bytes]:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("OPENAI_API_KEY", "the GptImage provider")
            )

        image_bytes = base64.b64decode(image_b64)
        client = AsyncOpenAI(api_key=api_key)

        response = await client.images.edit(
            model=_GPT_IMAGE_MODEL,
            image=_image_file_tuple(image_bytes),
            prompt=enhance_landscape_render_prompt(prompt),
            n=3,
            quality="medium",
        )

        result: list[bytes] = []
        for item in response.data:
            if item.b64_json:
                result.append(base64.b64decode(item.b64_json))
            elif item.url:
                # Fallback: if URL was returned instead of b64.
                raise ValueError(
                    "GptImage returned a URL instead of b64_json — "
                    "set response_format='b64_json' or check model capabilities."
                )
            else:
                raise ValueError("GptImage returned an image item with neither b64_json nor url.")

        if len(result) != 3:
            raise ValueError(f"GptImage returned {len(result)} images; expected 3.")

        return result
