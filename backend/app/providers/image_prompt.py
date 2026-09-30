from __future__ import annotations

from app.domain.spaces import SpaceConfig, get_space


def enhance_landscape_render_prompt(prompt: str, space: SpaceConfig | None = None) -> str:
    """Add consistent image-generation guidance while preserving the user's request.

    ``space`` picks the guidance for a yard or a room; ``None`` keeps the original
    exterior (landscape) text so existing callers behave exactly as before.
    """
    space = space or get_space(None)
    user_prompt = prompt.strip() or space.render_prompt_fallback
    return f"{user_prompt}\n\n{space.render_prompt_guidance}"


# Space-neutral name; the original is kept because adapters, tests and scripts import it.
enhance_render_prompt = enhance_landscape_render_prompt
