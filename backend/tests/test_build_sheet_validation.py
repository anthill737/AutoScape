from app.domain import build_sheet_validation
from app.domain.build_sheet_validation import (
    validate_build_sheet_approved_retailers,
    validate_build_sheet_material_urls,
)


def _item(name: str, url: str) -> dict:
    return {
        "name": name,
        "quantity": 1,
        "unit": "each",
        "unit_cost_range": "$1 - $2",
        "total_cost_range": "$1 - $2",
        "vendor": "Test",
        "product_url": url,
        "notes": "",
    }


def test_validation_drops_unapproved_material_items_and_appends_assumption():
    draft = {
        "material_items": [
            _item("Deck board", "https://www.homedepot.com/p/deck-board/1"),
            _item("Joist hanger", "https://homedepot.com/p/joist-hanger/2"),
            _item("Outdoor light", "https://www.amazon.com/dp/abc"),
            _item("Concrete mix", "https://www.lowes.com/pd/concrete-mix/3"),
        ],
        "tool_list": ["Drill"],
        "build_steps": [],
        "total_cost_range": "$100 - $200",
        "skill_level": "Intermediate",
        "assumptions": ["Existing assumption"],
    }

    result = validate_build_sheet_approved_retailers(draft)

    assert len(result["material_items"]) == 3
    assert [item["name"] for item in result["material_items"]] == [
        "Deck board",
        "Joist hanger",
        "Concrete mix",
    ]
    assert "amazon.com" not in str(result["material_items"])
    assert any(
        "1 item" in assumption and "omitted" in assumption
        for assumption in result["assumptions"]
    )
    assert "warning" not in result


def test_validation_sets_warning_when_more_than_half_items_are_dropped():
    draft = {
        "material_items": [
            _item("Deck board", "https://www.homedepot.com/p/deck-board/1"),
            _item("Outdoor light", "https://www.amazon.com/dp/abc"),
            _item("Planter", "https://example.com/planter"),
        ],
        "assumptions": [],
    }

    result = validate_build_sheet_approved_retailers(draft)

    assert len(result["material_items"]) == 1
    assert result["warning"]
    assert "More than half" in result["warning"]


async def test_material_url_validation_keeps_all_items_and_rewrites_to_search_links():
    draft = {
        "material_items": [
            _item("Deck board", "https://www.homedepot.com/p/deck-board/1"),
            _item("Search result lumber", "https://www.homedepot.com/s/lumber"),
        ],
        "assumptions": ["Existing assumption"],
    }

    result = await validate_build_sheet_material_urls(draft)

    # Nothing is dropped, and no "failed validation" noise is added.
    assert [item["name"] for item in result["material_items"]] == [
        "Deck board",
        "Search result lumber",
    ]
    assert result["assumptions"] == ["Existing assumption"]
    assert not any("failed validation" in a for a in result["assumptions"])
    # Every item gets a working retailer search link.
    for item in result["material_items"]:
        assert item["product_url"].startswith("https://www.homedepot.com/s/")


async def test_material_url_validation_points_each_item_at_its_retailer_search():
    draft = {
        "material_items": [
            _item("Deck board", "https://www.homedepot.com/p/deck-board/1"),
            _item("Concrete mix", "https://www.lowes.com/pd/concrete-mix/3"),
        ],
        "assumptions": [],
    }

    result = await validate_build_sheet_material_urls(draft)

    assert len(result["material_items"]) == 2
    assert result["assumptions"] == []
    assert "warning" not in result
    # The retailer of the original approved URL is preserved in the search link.
    assert result["material_items"][0]["product_url"].startswith(
        "https://www.homedepot.com/s/"
    )
    assert result["material_items"][1]["product_url"].startswith(
        "https://www.lowes.com/search?searchTerm="
    )


async def test_material_url_validation_handles_many_items():
    draft = {
        "material_items": [
            _item(f"Deck board {index}", f"https://www.homedepot.com/p/deck-board/{index}")
            for index in range(6)
        ],
        "assumptions": [],
    }

    result = await validate_build_sheet_material_urls(draft)

    assert len(result["material_items"]) == 6
    assert all(
        item["product_url"].startswith("https://www.homedepot.com/s/")
        for item in result["material_items"]
    )
