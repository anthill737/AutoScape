from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import bootstrap  # noqa: E402,F401 - imports startup secrets before provider adapters.
from app.providers.image_provider import ImageProvider  # noqa: E402

PROMPT = "make this green"

# 1x1 white JPEG.
ONE_BY_ONE_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
    "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx"
    "BhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK"
    "U1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3"
    "uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iii"
    "gD//2Q=="
)


async def _probe_provider(provider: ImageProvider) -> tuple[str, str, str | None]:
    adapter = provider.make_adapter()
    try:
        outputs = await adapter.generate(ONE_BY_ONE_JPEG_B64, PROMPT)
    except Exception as exc:  # noqa: BLE001 - diagnostic script must report full adapter failure.
        return provider.name, "failure", f"{exc.__class__.__name__}: {exc}"

    byte_lengths = ", ".join(str(len(output)) for output in outputs)
    return provider.name, "success", f"{len(outputs)} image(s); byte lengths: {byte_lengths}"


async def main() -> int:
    for provider in (ImageProvider.GeminiFlashImage, ImageProvider.GptImage):
        name, status, detail = await _probe_provider(provider)
        if status == "success":
            print(f"{name}: success ({detail})")
        else:
            print(f"{name}: failure ({detail})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
