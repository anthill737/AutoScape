"""Suggest starting dimensions for a render's features using whichever text vendor is
configured.

Each Materials LLM adapter implements ``suggest_dimension_defaults``; this module picks
the adapter (the caller's preferred provider when its key is set, otherwise the first
provider with a key) so the panel auto-fills even when one vendor's key is missing.
"""

from __future__ import annotations

import json
import os

from app.providers.base import MissingApiKeyError
from app.providers.build_sheet_schema import strip_code_fences
from app.providers.materials_llm import MaterialsLLM
from app.providers.model_catalog import PROVIDERS_BY_SLUG

DIMENSION_SYSTEM_PROMPT = (
    "You are a landscape design assistant. Given a rendered design image and project details, "
    "suggest reasonable default dimensions for the features present.\n\n"
    "Respond with ONLY valid JSON (no markdown, no explanation) where keys are snake_case "
    'dimension field names (e.g. "deck_width_ft", "deck_length_ft") and values are numeric '
    'strings (e.g. "12", "16").\n\n'
    "Rules:\n"
    "- Include all relevant dimensions for each feature category provided\n"
    "- Use feet as the unit suffix (e.g. _ft, _sqft)\n"
    "- Infer reasonable defaults from the image and lot size\n"
    "- Return only the JSON object, nothing else"
)

# Field names the UI knows how to show, per feature category. Sent to the model so the
# keys line up with the form instead of relying on it to guess the naming.
DIMENSION_FIELDS_BY_CATEGORY: dict[str, list[str]] = {
    "Deck": ["deck_width_ft", "deck_length_ft", "deck_height_ft"],
    "Patio": ["patio_width_ft", "patio_length_ft"],
    "Garden Beds": ["bed_width_ft", "bed_length_ft"],
    "Fire Feature": ["fire_pit_diameter_ft"],
    "Pergola": ["pergola_width_ft", "pergola_length_ft", "pergola_height_ft"],
    "Pool": ["pool_width_ft", "pool_length_ft", "pool_depth_ft"],
}

# Order tried when the caller has no preference or the preferred vendor has no key.
PROVIDER_PREFERENCE: tuple[str, ...] = ("claude_sonnet", "gpt5", "gemini_pro")


def build_dimension_message(
    feature_categories: list[str],
    lot_size_sqft: float | None,
    house_sqft: float | None,
) -> str:
    features_str = ", ".join(feature_categories) if feature_categories else "General landscaping"
    lot_str = f"{lot_size_sqft} sqft" if lot_size_sqft else "unknown"
    house_str = f"{house_sqft} sqft" if house_sqft else "unknown"
    wanted = [
        key
        for category in feature_categories
        for key in DIMENSION_FIELDS_BY_CATEGORY.get(category, [])
    ]
    keys_str = ", ".join(wanted) if wanted else "your choice of snake_case *_ft keys"
    return (
        f"Feature Categories: {features_str}\n"
        f"Lot size: {lot_str}\n"
        f"House size: {house_str}\n"
        f"Return these keys: {keys_str}\n\n"
        "Based on the rendered design image and the project details above, "
        "suggest reasonable default dimensions for the features."
    )


def parse_dimension_json(raw: str) -> dict[str, str]:
    data = json.loads(strip_code_fences(raw))
    if not isinstance(data, dict):
        raise ValueError("dimension suggestion was not a JSON object")
    return {str(k): str(v) for k, v in data.items() if v is not None and str(v).strip()}


def _key_set(slug: str) -> bool:
    return bool(os.environ.get(PROVIDERS_BY_SLUG[slug].key_env))


def pick_provider(preferred: str | None) -> MaterialsLLM:
    """Preferred provider if its key is set, else the first configured one."""
    candidates: list[str] = []
    if preferred in PROVIDERS_BY_SLUG and preferred in {m.value for m in MaterialsLLM}:
        candidates.append(preferred)
    candidates += [slug for slug in PROVIDER_PREFERENCE if slug not in candidates]
    for slug in candidates:
        if _key_set(slug):
            return MaterialsLLM(slug)
    needed = ", ".join(PROVIDERS_BY_SLUG[s].key_env for s in PROVIDER_PREFERENCE)
    raise MissingApiKeyError(
        f"No text-model API key is set ({needed}). Add one in Settings to auto-fill "
        "dimensions, or type them in by hand."
    )


async def suggest_dimension_defaults(
    render_image_bytes: bytes,
    feature_categories: list[str],
    lot_size_sqft: float | None,
    house_sqft: float | None,
    materials_llm: str | None = None,
    model: str | None = None,
) -> dict[str, str]:
    """Return {dimension_key: numeric string} using the best available text vendor."""
    provider = pick_provider(materials_llm)
    # Only honour an explicit model when it belongs to the provider actually used.
    chosen_model = model if (materials_llm == provider.value and model) else None
    adapter = provider.make_adapter(model=chosen_model)
    return await adapter.suggest_dimension_defaults(
        render_image_bytes=render_image_bytes,
        feature_categories=feature_categories,
        lot_size_sqft=lot_size_sqft,
        house_sqft=house_sqft,
    )
