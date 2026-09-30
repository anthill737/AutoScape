"""Suggest starting dimensions for a render's features using whichever text vendor is
configured.

Each Materials LLM adapter implements ``suggest_dimension_defaults``; this module picks
the adapter (the caller's preferred provider when its key is set, otherwise the first
provider with a key) so the panel auto-fills even when one vendor's key is missing.

Which dimension keys are requested, and how the project's size is described, come from
the project's ``SpaceConfig`` (yard: lot/house size; room: length/width/ceiling).
"""

from __future__ import annotations

import json
import os

from app.domain.spaces import SpaceConfig, get_space
from app.providers.base import MissingApiKeyError
from app.providers.build_sheet_schema import strip_code_fences
from app.providers.materials_llm import MaterialsLLM
from app.providers.model_catalog import PROVIDERS_BY_SLUG

DIMENSION_SYSTEM_PROMPT = (
    "You are a residential design assistant for landscaping and interior remodel projects. "
    "Given a rendered design image and project details, suggest reasonable default "
    "dimensions for the features present.\n\n"
    "Respond with ONLY valid JSON (no markdown, no explanation) where keys are snake_case "
    'dimension field names (e.g. "deck_width_ft", "floor_sqft") and values are numeric '
    'strings (e.g. "12", "16").\n\n'
    "Rules:\n"
    "- Include all relevant dimensions for each feature category provided\n"
    "- Use the unit in each key's suffix (_ft, _sqft, or a plain count)\n"
    "- Infer reasonable defaults from the image and the project size details\n"
    "- Return only the JSON object, nothing else"
)

# Field names the UI knows how to show, per feature category, for EXTERIOR projects. Kept
# for callers that import the constant; the per-space source of truth is SpaceConfig.
DIMENSION_FIELDS_BY_CATEGORY: dict[str, list[str]] = {
    category: get_space("exterior").dimension_keys(category)
    for category, fields in get_space("exterior").dimension_fields.items()
    if fields
}

# Order tried when the caller has no preference or the preferred vendor has no key.
PROVIDER_PREFERENCE: tuple[str, ...] = ("claude_sonnet", "gpt5", "gemini_pro")


def _size_lines(
    space: SpaceConfig,
    lot_size_sqft: float | None,
    house_sqft: float | None,
    space_details: dict | None,
) -> list[str]:
    """One ``Label: value unit`` line per size field, e.g. ``Lot size: 5000.0 sqft``."""
    details: dict = dict(space_details or {})
    if lot_size_sqft is not None:
        details.setdefault("lot_size_sqft", lot_size_sqft)
    if house_sqft is not None:
        details.setdefault("house_sqft", house_sqft)

    lines: list[str] = []
    for field in space.size_fields:
        key = field["key"]
        # "House size (sqft)" -> name "House size", unit "sqft"
        name, _, unit = field["label"].partition(" (")
        unit = unit.rstrip(")")
        value = details.get(key)
        lines.append(f"{name}: {value} {unit}".rstrip() if value else f"{name}: unknown")
    return lines


def build_dimension_message(
    feature_categories: list[str],
    lot_size_sqft: float | None,
    house_sqft: float | None,
    space: SpaceConfig | None = None,
    space_details: dict | None = None,
) -> str:
    space = space or get_space(None)
    general = "General landscaping" if space.id == "exterior" else "General remodel"
    features_str = ", ".join(feature_categories) if feature_categories else general
    wanted = [key for category in feature_categories for key in space.dimension_keys(category)]
    keys_str = ", ".join(wanted) if wanted else "your choice of snake_case *_ft keys"
    size_lines = "\n".join(_size_lines(space, lot_size_sqft, house_sqft, space_details))
    return (
        f"Feature Categories: {features_str}\n"
        f"{space.dimension_prompt_context}\n"
        f"{size_lines}\n"
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
    space: SpaceConfig | None = None,
    space_details: dict | None = None,
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
        space=space,
        space_details=space_details,
    )
