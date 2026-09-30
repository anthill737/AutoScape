"""The space registry (exterior / interior) and the prompt helpers that read from it."""

import json

import pytest

from app.domain.build_sheet_validation import validate_build_sheet_material_urls
from app.domain.retailers import (
    APPROVED_RETAILER_PROMPT_CONSTRAINT,
    APPROVED_RETAILERS,
    approved_domains,
    retailer_prompt_constraint,
)
from app.domain.spaces import SPACES, SpaceConfig, get_space, space_catalog
from app.providers.build_sheet_schema import SYSTEM_PROMPT, build_user_message, system_prompt_for
from app.providers.dimension_defaults import DIMENSION_FIELDS_BY_CATEGORY
from app.providers.image_prompt import enhance_landscape_render_prompt, enhance_render_prompt

_EXPECTED_KEYS = {
    "id",
    "label",
    "description",
    "photo_hint",
    "room_types",
    "feature_categories",
    "styles",
    "quality_tiers",
    "dimension_fields",
    "size_fields",
    "retailers",
    "render_prompt_guidance",
    "render_prompt_fallback",
    "build_sheet_role",
    "build_sheet_extra_rules",
    "search_instructions",
    "search_query_template",
    "dimension_prompt_context",
    "default_prompt_template",
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_has_exactly_exterior_and_interior():
    assert list(SPACES) == ["exterior", "interior"]
    assert all(isinstance(space, SpaceConfig) for space in SPACES.values())
    assert all(space.id == key for key, space in SPACES.items())


def test_exterior_config_matches_legacy_constants():
    exterior = get_space("exterior")
    assert exterior.feature_categories == [
        "Deck",
        "Patio",
        "Garden Beds",
        "Fire Feature",
        "Pergola",
        "Pool",
        "Full Redesign",
    ]
    assert exterior.styles == [
        "Modern",
        "Traditional",
        "Cottage",
        "Xeriscape",
        "Tropical",
        "Rustic",
    ]
    assert exterior.quality_tiers == ["Budget", "Mid-range", "Premium"]
    assert exterior.retailers == APPROVED_RETAILERS
    assert exterior.room_types == []
    # The legacy dimension mapping is derived from the same data.
    legacy = {
        "Deck": ["deck_width_ft", "deck_length_ft", "deck_height_ft"],
        "Patio": ["patio_width_ft", "patio_length_ft"],
        "Garden Beds": ["bed_width_ft", "bed_length_ft"],
        "Fire Feature": ["fire_pit_diameter_ft"],
        "Pergola": ["pergola_width_ft", "pergola_length_ft", "pergola_height_ft"],
        "Pool": ["pool_width_ft", "pool_length_ft", "pool_depth_ft"],
    }
    assert DIMENSION_FIELDS_BY_CATEGORY == legacy
    for category, keys in legacy.items():
        assert exterior.dimension_keys(category) == keys
    assert exterior.dimension_fields["Full Redesign"] == []
    assert exterior.dimension_fields["Deck"][0] == {
        "key": "deck_width_ft",
        "label": "Deck Width (ft)",
    }
    assert [f["key"] for f in exterior.size_fields] == ["lot_size_sqft", "house_sqft"]
    assert exterior.required_size_keys() == ["lot_size_sqft", "house_sqft"]


def test_interior_config_shape():
    interior = get_space("interior")
    assert interior.room_types == [
        "Kitchen",
        "Bathroom",
        "Living Room",
        "Bedroom",
        "Home Office",
        "Basement",
        "Laundry / Mudroom",
        "Dining Room",
    ]
    assert "Cabinets" in interior.feature_categories
    assert interior.feature_categories[-1] == "Full Redesign"
    assert "Japandi" in interior.styles
    assert interior.quality_tiers == ["Budget", "Mid-range", "Premium"]
    # Every feature category has a dimension entry (possibly empty).
    assert set(interior.dimension_fields) == set(interior.feature_categories)
    assert interior.dimension_keys("Cabinets") == ["cabinet_linear_ft", "upper_cabinet_linear_ft"]
    assert interior.dimension_fields["Lighting"] == [
        {"key": "fixture_count", "label": "Light fixtures (count)"}
    ]
    assert interior.dimension_fields["Furniture Layout"] == []
    assert interior.required_size_keys() == ["room_length_ft", "room_width_ft"]
    assert interior.retailer_domains() == [
        "homedepot.com",
        "lowes.com",
        "ikea.com",
        "flooranddecor.com",
        "build.com",
        "wayfair.com",
    ]


@pytest.mark.parametrize("value", [None, "bogus", "", "  "])
def test_get_space_falls_back_to_exterior(value):
    assert get_space(value) is get_space("exterior")


def test_get_space_is_case_insensitive():
    assert get_space("INTERIOR") is get_space("interior")
    assert get_space(" Exterior ") is get_space("exterior")


def test_space_catalog_is_json_serialisable_with_documented_keys():
    catalog = space_catalog()
    assert [entry["id"] for entry in catalog] == ["exterior", "interior"]
    for entry in catalog:
        assert set(entry) == _EXPECTED_KEYS
        for field in entry["size_fields"]:
            assert set(field) == {"key", "label", "required"}
        for fields in entry["dimension_fields"].values():
            for field in fields:
                assert set(field) == {"key", "label"}
        for retailer in entry["retailers"]:
            assert set(retailer) == {"name", "domain"}
    # Round-trips through JSON unchanged.
    assert json.loads(json.dumps(catalog)) == catalog


# ---------------------------------------------------------------------------
# Prompt fragments
# ---------------------------------------------------------------------------


def test_default_prompt_template_formatting():
    exterior = get_space("exterior")
    assert exterior.default_prompt("Budget", "Modern", ["Deck", "Pergola"]) == (
        "Design a budget modern outdoor space featuring Deck, Pergola. Preserve the existing "
        "home, camera angle, and yard boundaries. Show a photorealistic, buildable finished "
        "design with realistic materials, natural daylight, clean geometry, and no labels or text."
    )
    assert exterior.default_prompt("Premium", "Rustic", []).startswith(
        "Design a premium rustic outdoor space. Preserve"
    )
    interior = get_space("interior")
    assert interior.default_prompt("Mid-range", "Japandi", ["Cabinets"], room_type="Kitchen") == (
        "Redesign this kitchen as a mid-range japandi interior featuring Cabinets. Keep the "
        "walls, windows, doors, and camera angle. Show a photorealistic, buildable finished room "
        "with realistic materials, coherent lighting, correctly scaled furniture, and no labels "
        "or text."
    )
    assert interior.default_prompt("Budget", "Modern", []).startswith(
        "Redesign this room as a budget modern interior. Keep"
    )


def test_search_query_uses_room_type_for_interior_only():
    assert get_space("exterior").search_query("Deck").startswith(
        "List the best products and materials for a Deck landscaping project."
    )
    assert get_space("interior").search_query("Cabinets", "Kitchen").startswith(
        "List the best products and materials for a Cabinets kitchen remodel."
    )
    assert "Cabinets room remodel" in get_space("interior").search_query("Cabinets")


def test_room_label():
    assert get_space("exterior").room_label(None) == "Outdoor & Landscape"
    assert get_space("exterior").room_label("Kitchen") == "Outdoor & Landscape"
    assert get_space("interior").room_label("Kitchen") == "Kitchen"
    assert get_space("interior").room_label(None) == "Interior"


def test_render_prompt_guidance_is_space_aware_and_default_is_unchanged():
    default_text = enhance_landscape_render_prompt("add a stone patio")
    assert default_text.startswith("add a stone patio\n\n")
    assert "yard boundaries" in default_text
    assert default_text == enhance_landscape_render_prompt(
        "add a stone patio", get_space("exterior")
    )
    assert enhance_render_prompt is enhance_landscape_render_prompt

    interior_text = enhance_landscape_render_prompt("white oak cabinets", get_space("interior"))
    assert interior_text.startswith("white oak cabinets\n\n")
    assert "exact room reference" in interior_text
    assert "yard" not in interior_text
    for text in (default_text, interior_text):
        assert "photorealistic" in text
        assert "labels or text" in text

    assert enhance_landscape_render_prompt("   ", get_space("interior")).startswith(
        get_space("interior").render_prompt_fallback
    )


def test_build_sheet_system_prompt_per_space():
    assert SYSTEM_PROMPT == system_prompt_for(get_space("exterior")) == system_prompt_for(None)
    assert "professional landscape contractor and cost estimator" in SYSTEM_PROMPT
    assert APPROVED_RETAILER_PROMPT_CONSTRAINT in SYSTEM_PROMPT

    interior_prompt = system_prompt_for(get_space("interior"))
    assert "interior designer and remodel contractor and cost estimator" in interior_prompt
    assert "IKEA (ikea.com)" in interior_prompt
    assert "Menards" not in interior_prompt
    assert "waste factors for flooring, tile and paint" in interior_prompt
    assert "licensed electrician or plumber" in interior_prompt
    assert '"material_items"' in interior_prompt


def test_retailer_prompt_constraint_helpers():
    assert retailer_prompt_constraint(APPROVED_RETAILERS) == APPROVED_RETAILER_PROMPT_CONSTRAINT
    assert "Do not include Amazon, Wayfair, Walmart," in APPROVED_RETAILER_PROMPT_CONSTRAINT
    interior_constraint = retailer_prompt_constraint(get_space("interior").retailers)
    # Wayfair is approved for interiors, so it must not be listed as banned.
    assert "Wayfair (wayfair.com)" in interior_constraint
    assert "Do not include Amazon, Walmart," in interior_constraint
    assert approved_domains(get_space("interior").retailers) == {
        "homedepot.com",
        "lowes.com",
        "ikea.com",
        "flooranddecor.com",
        "build.com",
        "wayfair.com",
    }


def test_build_user_message_names_the_space():
    exterior_text = build_user_message({}, "Budget", [], [])
    assert "Space: Outdoor & Landscape" in exterior_text
    assert "Feature Categories: General landscaping" in exterior_text
    assert "Product Research Data (from web search grounding):" in exterior_text
    interior_text = build_user_message(
        {"floor_sqft": 168}, "Premium", [], ["Flooring"], get_space("interior"), "Kitchen"
    )
    assert "Space: Kitchen" in interior_text
    assert "Feature Categories: Flooring" in interior_text
    assert "Product Research Data (from web search grounding):" in interior_text


# ---------------------------------------------------------------------------
# Search-link builders keyed by the space's retailers
# ---------------------------------------------------------------------------


def _item(name: str, vendor: str, url: str = "") -> dict:
    return {"name": name, "vendor": vendor, "product_url": url}


@pytest.mark.asyncio
async def test_interior_retailers_get_their_own_search_links():
    retailers = get_space("interior").retailers
    draft = {
        "material_items": [
            _item("SEKTION base cabinet", "IKEA"),
            _item("Porcelain tile", "Floor and Decor"),
            _item("Kitchen faucet", "Build.com"),
            _item("Pendant light", "Wayfair"),
            _item("Paint", "Some Unknown Store"),
            _item("Quartz slab", "", "https://www.lowes.com/pd/quartz/1"),
        ]
    }
    result = await validate_build_sheet_material_urls(draft, retailers=retailers)
    urls = [item["product_url"] for item in result["material_items"]]
    assert urls[0] == "https://www.ikea.com/us/en/search/?q=SEKTION+base+cabinet"
    assert urls[1] == "https://www.flooranddecor.com/search?q=Porcelain+tile"
    assert urls[2] == "https://www.build.com/search?term=Kitchen+faucet"
    assert urls[3] == "https://www.wayfair.com/keyword.php?keyword=Pendant+light"
    assert urls[4] == "https://www.homedepot.com/s/Paint"
    assert urls[5] == "https://www.lowes.com/search?searchTerm=Quartz+slab"
    assert result["material_items"][5]["vendor"] == "Lowe's"


@pytest.mark.asyncio
async def test_exterior_default_still_ignores_unapproved_vendors():
    draft = {"material_items": [_item("Pendant light", "Wayfair"), _item("Mulch", "Menards")]}
    result = await validate_build_sheet_material_urls(draft)
    urls = [item["product_url"] for item in result["material_items"]]
    assert urls[0] == "https://www.homedepot.com/s/Pendant%20light"
    assert urls[1] == "https://www.menards.com/main/search.html?search=Mulch"
