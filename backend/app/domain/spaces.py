"""Per-space configuration for exterior (yard) and interior (room) projects.

Everything that differs between designing a yard and designing a room lives here as data:
feature categories, styles, dimension fields, project-level size inputs, approved retailers
and the prompt fragments the image, materials, dimension and search-grounding providers use.
Callers resolve a project's ``SpaceConfig`` with :func:`get_space` and read from it rather
than from scattered constants, so adding a third space is a matter of adding an entry.

The exterior entry reproduces the app's original landscape-only behaviour exactly; projects
created before ``space_type`` existed default to it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.domain.retailers import APPROVED_RETAILERS

EXTERIOR = "exterior"
INTERIOR = "interior"
DEFAULT_SPACE_TYPE = EXTERIOR

QUALITY_TIERS: list[str] = ["Budget", "Mid-range", "Premium"]


def _field(key: str, label: str) -> dict[str, str]:
    return {"key": key, "label": label}


def _size_field(key: str, label: str, required: bool) -> dict:
    return {"key": key, "label": label, "required": required}


@dataclass(frozen=True)
class SpaceConfig:
    """Everything the API and the providers need to know about one kind of space."""

    id: str
    label: str
    description: str
    photo_hint: str
    room_types: list[str]
    feature_categories: list[str]
    styles: list[str]
    quality_tiers: list[str]
    # category -> [{"key": "deck_width_ft", "label": "Deck Width (ft)"}, ...]
    dimension_fields: dict[str, list[dict[str, str]]]
    # Project-level size inputs: [{"key", "label", "required"}]
    size_fields: list[dict]
    retailers: list[dict[str, str]]
    # Prompt fragments
    render_prompt_guidance: str
    render_prompt_fallback: str
    build_sheet_role: str
    build_sheet_extra_rules: str
    search_instructions: str
    search_query_template: str
    dimension_prompt_context: str
    default_prompt_template: str

    # -- derived helpers -------------------------------------------------------------

    def dimension_keys(self, category: str) -> list[str]:
        return [field["key"] for field in self.dimension_fields.get(category, [])]

    def retailer_domains(self) -> list[str]:
        return [retailer["domain"] for retailer in self.retailers]

    def required_size_keys(self) -> list[str]:
        return [field["key"] for field in self.size_fields if field.get("required")]

    def room_label(self, room_type: str | None) -> str:
        """Human label for a project: the room type when the space has rooms, else the label."""
        if self.room_types and room_type:
            return room_type
        return self.label

    def search_query(self, category: str, room_type: str | None = None) -> str:
        room = (room_type or "room").lower()
        return self.search_query_template.format(category=category, room=room)

    def default_prompt(
        self,
        quality_tier: str,
        style: str,
        feature_categories: list[str],
        room_type: str | None = None,
    ) -> str:
        """Seed text for the composed prompt, matching what the frontend shows by default."""
        features = ", ".join(c.strip() for c in feature_categories if c and c.strip())
        features_str = f" featuring {features}" if features else ""
        room = (room_type or "room").lower()
        return self.default_prompt_template.format(
            tier=quality_tier.lower(),
            style=style.lower(),
            features=features_str,
            room=room,
        )

    def to_dict(self) -> dict:
        return asdict(self)


_EXTERIOR = SpaceConfig(
    id=EXTERIOR,
    label="Outdoor & Landscape",
    description="Yards, decks, patios, gardens, pools and other outdoor living areas.",
    photo_hint=(
        "Shoot from the far edge of the yard or the street so the whole area you want to "
        "redesign and the house are in frame."
    ),
    room_types=[],
    feature_categories=[
        "Deck",
        "Patio",
        "Garden Beds",
        "Fire Feature",
        "Pergola",
        "Pool",
        "Full Redesign",
    ],
    styles=["Modern", "Traditional", "Cottage", "Xeriscape", "Tropical", "Rustic"],
    quality_tiers=list(QUALITY_TIERS),
    dimension_fields={
        "Deck": [
            _field("deck_width_ft", "Deck Width (ft)"),
            _field("deck_length_ft", "Deck Length (ft)"),
            _field("deck_height_ft", "Deck Height (ft)"),
        ],
        "Patio": [
            _field("patio_width_ft", "Patio Width (ft)"),
            _field("patio_length_ft", "Patio Length (ft)"),
        ],
        "Garden Beds": [
            _field("bed_width_ft", "Bed Width (ft)"),
            _field("bed_length_ft", "Bed Length (ft)"),
        ],
        "Fire Feature": [_field("fire_pit_diameter_ft", "Fire Pit Diameter (ft)")],
        "Pergola": [
            _field("pergola_width_ft", "Pergola Width (ft)"),
            _field("pergola_length_ft", "Pergola Length (ft)"),
            _field("pergola_height_ft", "Pergola Height (ft)"),
        ],
        "Pool": [
            _field("pool_width_ft", "Pool Width (ft)"),
            _field("pool_length_ft", "Pool Length (ft)"),
            _field("pool_depth_ft", "Pool Depth (ft)"),
        ],
        "Full Redesign": [],
    },
    size_fields=[
        _size_field("lot_size_sqft", "Lot size (sqft)", required=True),
        _size_field("house_sqft", "House size (sqft)", required=True),
    ],
    retailers=[dict(retailer) for retailer in APPROVED_RETAILERS],
    render_prompt_guidance=(
        "Use the input photo as the exact site reference. Preserve the existing house, "
        "yard boundaries, camera angle, and permanent structures unless the request "
        "explicitly changes them. Create a photorealistic finished residential "
        "landscape/deck/patio concept with buildable proportions, realistic materials, "
        "natural daylight, coherent shadows, and clean construction geometry. Avoid "
        "cartoon styling, warped architecture, impossible structures, no labels or text, "
        "watermarks, and before/after split layouts."
    ),
    render_prompt_fallback="Create a realistic outdoor landscape design.",
    build_sheet_role="professional landscape contractor and cost estimator",
    build_sheet_extra_rules="",
    search_instructions=(
        "You are a landscaping materials researcher. Answer with a concise list of specific "
        "products and materials, with product names and current prices where available. "
        "Only use the retailer sites you are allowed to search."
    ),
    search_query_template=(
        "List the best products and materials for a {category} landscaping project. "
        "Include product names, sources, and current prices where available."
    ),
    dimension_prompt_context=(
        "The image shows a residential yard; the dimensions are for outdoor features "
        "such as decks, patios, beds and pools."
    ),
    default_prompt_template=(
        "Design a {tier} {style} outdoor space{features}. Preserve the existing home, "
        "camera angle, and yard boundaries. Show a photorealistic, buildable finished design "
        "with realistic materials, natural daylight, clean geometry, and no labels or text."
    ),
)

_INTERIOR = SpaceConfig(
    id=INTERIOR,
    label="Interior",
    description="Kitchens, bathrooms, living rooms and other rooms inside the home.",
    photo_hint=(
        "Stand in a doorway or corner and shoot toward the main wall so the floor, ceiling "
        "and any windows are in frame."
    ),
    room_types=[
        "Kitchen",
        "Bathroom",
        "Living Room",
        "Bedroom",
        "Home Office",
        "Basement",
        "Laundry / Mudroom",
        "Dining Room",
    ],
    feature_categories=[
        "Cabinets",
        "Countertops",
        "Flooring",
        "Paint & Wall Finish",
        "Backsplash & Tile",
        "Lighting",
        "Plumbing Fixtures",
        "Built-ins & Storage",
        "Furniture Layout",
        "Window Treatments",
        "Full Redesign",
    ],
    styles=[
        "Modern",
        "Scandinavian",
        "Mid-century",
        "Farmhouse",
        "Industrial",
        "Traditional",
        "Japandi",
        "Coastal",
    ],
    quality_tiers=list(QUALITY_TIERS),
    dimension_fields={
        "Cabinets": [
            _field("cabinet_linear_ft", "Cabinet run (linear ft)"),
            _field("upper_cabinet_linear_ft", "Upper cabinet run (linear ft)"),
        ],
        "Countertops": [_field("countertop_sqft", "Countertop area (sqft)")],
        "Flooring": [_field("floor_sqft", "Floor area (sqft)")],
        "Paint & Wall Finish": [_field("wall_sqft", "Wall area (sqft)")],
        "Backsplash & Tile": [_field("tile_sqft", "Tile area (sqft)")],
        "Lighting": [_field("fixture_count", "Light fixtures (count)")],
        "Plumbing Fixtures": [_field("fixture_count_plumbing", "Plumbing fixtures (count)")],
        "Built-ins & Storage": [_field("builtin_linear_ft", "Built-in run (linear ft)")],
        "Furniture Layout": [],
        "Window Treatments": [_field("window_count", "Windows (count)")],
        "Full Redesign": [],
    },
    size_fields=[
        _size_field("room_length_ft", "Room length (ft)", required=True),
        _size_field("room_width_ft", "Room width (ft)", required=True),
        _size_field("ceiling_height_ft", "Ceiling height (ft)", required=False),
    ],
    retailers=[
        {"name": "The Home Depot", "domain": "homedepot.com"},
        {"name": "Lowe's", "domain": "lowes.com"},
        {"name": "IKEA", "domain": "ikea.com"},
        {"name": "Floor & Decor", "domain": "flooranddecor.com"},
        {"name": "Build.com", "domain": "build.com"},
        {"name": "Wayfair", "domain": "wayfair.com"},
    ],
    render_prompt_guidance=(
        "Use the input photo as the exact room reference. Preserve the walls, windows, doors, "
        "ceiling height, and camera angle unless the request explicitly changes them. Create "
        "a photorealistic finished interior with realistic materials, coherent lighting from "
        "the existing windows and fixtures, correct scale furniture that sits on the floor, "
        "and buildable proportions. Avoid floating objects, impossible plumbing or structural "
        "changes, cartoon styling, labels or text, watermarks, and before/after split layouts."
    ),
    render_prompt_fallback="Create a realistic finished interior design for this room.",
    build_sheet_role="interior designer and remodel contractor and cost estimator",
    build_sheet_extra_rules=(
        "Include waste factors for flooring, tile and paint in the assumptions. Flag any step "
        "that needs a licensed electrician or plumber or a permit in skill_notes."
    ),
    search_instructions=(
        "You are an interior remodel materials researcher. Answer with a concise list of "
        "specific products and materials, with product names and current prices where "
        "available. Only use the retailer sites you are allowed to search."
    ),
    search_query_template=(
        "List the best products and materials for a {category} {room} remodel. "
        "Include product names, sources, and current prices where available."
    ),
    dimension_prompt_context=(
        "The image shows an interior room; the dimensions are for the room's finishes and "
        "fixtures such as cabinet runs, floor area and fixture counts."
    ),
    default_prompt_template=(
        "Redesign this {room} as a {tier} {style} interior{features}. Keep the walls, windows, "
        "doors, and camera angle. Show a photorealistic, buildable finished room with realistic "
        "materials, coherent lighting, correctly scaled furniture, and no labels or text."
    ),
)

SPACES: dict[str, SpaceConfig] = {EXTERIOR: _EXTERIOR, INTERIOR: _INTERIOR}


def get_space(space_type: str | None) -> SpaceConfig:
    """Resolve a space id; ``None`` and unknown values fall back to exterior."""
    if space_type is None:
        return SPACES[DEFAULT_SPACE_TYPE]
    return SPACES.get(str(space_type).strip().lower(), SPACES[DEFAULT_SPACE_TYPE])


def is_known_space(space_type: str | None) -> bool:
    return space_type is not None and str(space_type).strip().lower() in SPACES


def space_catalog() -> list[dict]:
    """JSON-able list of every space, in registry order, for ``GET /api/spaces``."""
    return [space.to_dict() for space in SPACES.values()]
