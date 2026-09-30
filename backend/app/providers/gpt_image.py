import base64
import io
import os

from openai import AsyncOpenAI

from app.providers.base import MissingApiKeyError, ProviderAdapter, missing_api_key_message
from app.providers.image_prompt import enhance_landscape_render_prompt
from app.providers.model_catalog import default_model_for

# Default OpenAI image model; any gpt-image-* model from the catalog can be passed in.
_GPT_IMAGE_MODEL = default_model_for("gpt_image")
_QUALITY = "medium"  # accepted by every gpt-image-* generation


def _image_file_tuple(image_bytes: bytes) -> tuple[str, io.BytesIO, str]:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image.jpg", io.BytesIO(image_bytes), "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image.png", io.BytesIO(image_bytes), "image/png"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image.webp", io.BytesIO(image_bytes), "image/webp"
    raise ValueError("GptImage input image must be a JPEG, PNG, or WebP file.")


class GptImageAdapter(ProviderAdapter):
    """Image Provider adapter for OpenAI gpt-image-* models (images.edit)."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or _GPT_IMAGE_MODEL

    async def generate(self, image_b64: str, prompt: str) -> list[bytes]:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("OPENAI_API_KEY", "the GptImage provider")
            )

        image_bytes = base64.b64decode(image_b64)
        client = AsyncOpenAI(api_key=api_key)

        response = await client.images.edit(
            model=self.model,
            image=_image_file_tuple(image_bytes),
            prompt=enhance_landscape_render_prompt(prompt),
            n=3,
            quality=_QUALITY,
        )

        result: list[bytes] = []
        for item in response.data:
            if item.b64_json:
                result.append(base64.b64decode(item.b64_json))
            elif item.url:
                # GPT image models always return b64_json; a URL means a non-GPT model.
                raise ValueError(
                    f"GptImage model {self.model} returned a URL instead of b64_json; "
                    "choose a gpt-image-* model."
                )
            else:
                raise ValueError("GptImage returned an image item with neither b64_json nor url.")

        if len(result) != 3:
            raise ValueError(f"GptImage returned {len(result)} images; expected 3.")

        return result
