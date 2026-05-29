from __future__ import annotations


def enhance_landscape_render_prompt(prompt: str) -> str:
    """Add consistent image-generation guidance while preserving the user's request."""
    user_prompt = prompt.strip()
    if not user_prompt:
        user_prompt = "Create a realistic outdoor landscape design."

    return (
        f"{user_prompt}\n\n"
        "Use the input photo as the exact site reference. Preserve the existing house, "
        "yard boundaries, camera angle, and permanent structures unless the request "
        "explicitly changes them. Create a photorealistic finished residential "
        "landscape/deck/patio concept with buildable proportions, realistic materials, "
        "natural daylight, coherent shadows, and clean construction geometry. Avoid "
        "cartoon styling, warped architecture, impossible structures, no labels or text, "
        "watermarks, and before/after split layouts."
    )
