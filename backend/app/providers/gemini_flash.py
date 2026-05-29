import asyncio
import base64
import os

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.providers.base import MissingApiKeyError, ProviderAdapter, missing_api_key_message
from app.providers.exceptions import ImageProviderAuthError, ImageProviderQuotaError
from app.providers.image_prompt import enhance_landscape_render_prompt

_GEMINI_MODEL = "gemini-3-pro-image-preview"
_GOOGLE_API_KEY_LOCATION = "backend/.env.local or secrets/GOOGLE_API_KEY"


def _image_mime_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    raise ValueError("GeminiFlashImage input image must be a JPEG or PNG file.")


class GeminiFlashImageAdapter(ProviderAdapter):
    """Image Provider adapter for Google's highest-quality Gemini image model."""

    async def generate(self, image_b64: str, prompt: str) -> list[bytes]:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise MissingApiKeyError(
                missing_api_key_message("GOOGLE_API_KEY", "the GeminiFlashImage provider")
            )

        image_bytes = base64.b64decode(image_b64)
        mime_type = _image_mime_type(image_bytes)
        client = genai.Client(api_key=api_key)
        enhanced_prompt = enhance_landscape_render_prompt(prompt)

        tasks = [
            self._generate_one(client, image_bytes, mime_type, enhanced_prompt)
            for _ in range(3)
        ]
        try:
            return list(await asyncio.gather(*tasks))
        except genai_errors.ClientError as exc:
            _raise_domain_error(exc)
            raise

    async def _generate_one(
        self, client: genai.Client, image_bytes: bytes, mime_type: str, prompt: str
    ) -> bytes:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=_GEMINI_MODEL,
                contents=[
                    types.Content(
                        parts=[
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type=mime_type,
                                    data=image_bytes,
                                )
                            ),
                            types.Part(text=prompt),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                ),
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                return part.inline_data.data
        raise ValueError(f"GeminiFlashImage returned no image data for prompt: {prompt!r}")


def _raise_domain_error(exc: genai_errors.ClientError) -> None:
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "") or "").upper()
    if code == 429 and status == "RESOURCE_EXHAUSTED":
        raise ImageProviderQuotaError(
            f"Gemini quota exceeded for model {_GEMINI_MODEL}. Enable billing at "
            "https://aistudio.google.com/app/apikey or switch the Image Provider "
            "dropdown to GptImage for this request."
        ) from exc
    if code in {401, 403}:
        issue = _auth_issue(exc)
        raise ImageProviderAuthError(
            f"Gemini authentication failed for model {_GEMINI_MODEL}: {issue}. "
            f"Check GOOGLE_API_KEY in {_GOOGLE_API_KEY_LOCATION}."
        ) from exc


def _auth_issue(exc: genai_errors.ClientError) -> str:
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "") or "").upper()
    message = str(getattr(exc, "message", "") or "").strip()
    issue = f"HTTP {code}"
    if status:
        issue = f"{issue} {status}"
    if message:
        issue = f"{issue}: {message}"
    return issue
