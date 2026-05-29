from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic  # noqa: E402
from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

from app import bootstrap  # noqa: E402,F401 - imports startup secrets before provider adapters.
from app.providers.base import MissingApiKeyError, missing_api_key_message  # noqa: E402
from app.providers.claude_sonnet import _MODEL as _CLAUDE_MODEL  # noqa: E402
from app.providers.gemini_pro import _MODEL as _GEMINI_MODEL  # noqa: E402
from app.providers.gpt5 import _MODEL as _GPT_MODEL  # noqa: E402
from app.providers.materials_llm import MaterialsLLM  # noqa: E402

PROVIDERS = (MaterialsLLM.ClaudeSonnet, MaterialsLLM.Gpt5, MaterialsLLM.GeminiPro)
PROBE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}
PROMPT = 'Return exactly this JSON object: {"ok": true}'


def _api_key(name: str, provider_name: str) -> str:
    api_key = os.environ.get(name)
    if not api_key:
        raise MissingApiKeyError(
            missing_api_key_message(name, f"the {provider_name} materials provider")
        )
    return api_key


async def _probe_claude_sonnet() -> None:
    api_key = _api_key("ANTHROPIC_API_KEY", MaterialsLLM.ClaudeSonnet.name)
    client = anthropic.Anthropic(api_key=api_key)
    loop = asyncio.get_running_loop()
    message = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=64,
            messages=[{"role": "user", "content": PROMPT}],
            tools=[
                {
                    "name": "probe_materials_llm",
                    "description": "Return a tiny structured health-check payload.",
                    "input_schema": PROBE_SCHEMA,
                }
            ],
            tool_choice={"type": "tool", "name": "probe_materials_llm"},
        ),
    )
    tool_use = next(block for block in message.content if block.type == "tool_use")
    if tool_use.input != {"ok": True}:
        raise ValueError(f"Unexpected response: {tool_use.input}")


async def _probe_gpt5() -> None:
    api_key = _api_key("OPENAI_API_KEY", MaterialsLLM.Gpt5.name)
    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=_GPT_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You return only valid JSON."},
            {"role": "user", "content": PROMPT},
        ],
        max_completion_tokens=512,
    )
    payload = json.loads(response.choices[0].message.content)
    if payload != {"ok": True}:
        raise ValueError(f"Unexpected response: {payload}")


async def _probe_gemini_pro() -> None:
    api_key = _api_key("GOOGLE_API_KEY", MaterialsLLM.GeminiPro.name)
    client = genai.Client(api_key=api_key)
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=PROMPT,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=64,
            ),
        ),
    )
    payload = json.loads(response.text)
    if payload != {"ok": True}:
        raise ValueError(f"Unexpected response: {payload}")


PROBE_FUNCTIONS = {
    MaterialsLLM.ClaudeSonnet: _probe_claude_sonnet,
    MaterialsLLM.Gpt5: _probe_gpt5,
    MaterialsLLM.GeminiPro: _probe_gemini_pro,
}


async def _probe_provider(provider: MaterialsLLM) -> tuple[str, Exception | None]:
    try:
        await PROBE_FUNCTIONS[provider]()
    except Exception as exc:  # noqa: BLE001 - diagnostic script must report provider failures.
        return provider.name, exc
    return provider.name, None


async def main() -> int:
    for provider in PROVIDERS:
        name, exc = await _probe_provider(provider)
        if exc is None:
            print(f"{name}: OK")
        else:
            print(f"{name}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
