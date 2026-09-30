import { parseApiError } from "./errors";

/** A named measurement the design-request form asks for, per feature category. */
export interface DimensionField {
  key: string;
  label: string;
}

/** A project-level size input (lot/house for outdoors, room size for interiors). */
export interface SizeField {
  key: string;
  label: string;
  required: boolean;
}

export interface Retailer {
  name: string;
  domain: string;
}

/**
 * Everything that makes a space type (outdoor vs interior) different: the vocabulary
 * of the forms, the measurements, the retailers, and the prompt seed. Served by
 * GET /api/spaces; the static fallbacks below mirror the backend so the UI still works
 * against an older backend.
 */
export interface SpaceConfig {
  id: string;
  label: string;
  description: string;
  photo_hint: string;
  room_types: string[];
  feature_categories: string[];
  styles: string[];
  quality_tiers: string[];
  dimension_fields: Record<string, DimensionField[]>;
  size_fields: SizeField[];
  retailers: Retailer[];
  /** Template with {tier} {style} {features} and, for interiors, {room}. */
  default_prompt_template: string;
}

export const EXTERIOR_SPACE: SpaceConfig = {
  id: "exterior",
  label: "Outdoor & Landscape",
  description: "Yards, decks, patios, gardens, pools and other outdoor living areas.",
  photo_hint:
    "Shoot from the far edge of the yard or the street so the whole area you want to redesign and the house are in frame.",
  room_types: [],
  feature_categories: [
    "Deck",
    "Patio",
    "Garden Beds",
    "Fire Feature",
    "Pergola",
    "Pool",
    "Full Redesign",
  ],
  styles: ["Modern", "Traditional", "Cottage", "Xeriscape", "Tropical", "Rustic"],
  quality_tiers: ["Budget", "Mid-range", "Premium"],
  dimension_fields: {
    Deck: [
      { key: "deck_width_ft", label: "Deck Width (ft)" },
      { key: "deck_length_ft", label: "Deck Length (ft)" },
      { key: "deck_height_ft", label: "Deck Height (ft)" },
    ],
    Patio: [
      { key: "patio_width_ft", label: "Patio Width (ft)" },
      { key: "patio_length_ft", label: "Patio Length (ft)" },
    ],
    "Garden Beds": [
      { key: "bed_width_ft", label: "Bed Width (ft)" },
      { key: "bed_length_ft", label: "Bed Length (ft)" },
    ],
    "Fire Feature": [{ key: "fire_pit_diameter_ft", label: "Fire Pit Diameter (ft)" }],
    Pergola: [
      { key: "pergola_width_ft", label: "Pergola Width (ft)" },
      { key: "pergola_length_ft", label: "Pergola Length (ft)" },
      { key: "pergola_height_ft", label: "Pergola Height (ft)" },
    ],
    Pool: [
      { key: "pool_width_ft", label: "Pool Width (ft)" },
      { key: "pool_length_ft", label: "Pool Length (ft)" },
      { key: "pool_depth_ft", label: "Pool Depth (ft)" },
    ],
    "Full Redesign": [],
  },
  size_fields: [
    { key: "lot_size_sqft", label: "Lot size (sqft)", required: true },
    { key: "house_sqft", label: "House size (sqft)", required: true },
  ],
  retailers: [
    { name: "The Home Depot", domain: "homedepot.com" },
    { name: "Lowe's", domain: "lowes.com" },
    { name: "Menards", domain: "menards.com" },
    { name: "Ace Hardware", domain: "acehardware.com" },
    { name: "Costco", domain: "costco.com" },
  ],
  default_prompt_template:
    "Design a {tier} {style} outdoor space{features}. Preserve the existing home, camera angle, and yard boundaries. Show a photorealistic, buildable finished design with realistic materials, natural daylight, clean geometry, and no labels or text.",
};

export const INTERIOR_SPACE: SpaceConfig = {
  id: "interior",
  label: "Interior",
  description: "Kitchens, bathrooms, living rooms and other rooms inside the home.",
  photo_hint:
    "Stand in a doorway or corner and shoot toward the main wall so the floor, ceiling and any windows are in frame.",
  room_types: [
    "Kitchen",
    "Bathroom",
    "Living Room",
    "Bedroom",
    "Home Office",
    "Basement",
    "Laundry / Mudroom",
    "Dining Room",
  ],
  feature_categories: [
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
  styles: [
    "Modern",
    "Scandinavian",
    "Mid-century",
    "Farmhouse",
    "Industrial",
    "Traditional",
    "Japandi",
    "Coastal",
  ],
  quality_tiers: ["Budget", "Mid-range", "Premium"],
  dimension_fields: {
    Cabinets: [
      { key: "cabinet_linear_ft", label: "Cabinet run (linear ft)" },
      { key: "upper_cabinet_linear_ft", label: "Upper cabinet run (linear ft)" },
    ],
    Countertops: [{ key: "countertop_sqft", label: "Countertop area (sqft)" }],
    Flooring: [{ key: "floor_sqft", label: "Floor area (sqft)" }],
    "Paint & Wall Finish": [{ key: "wall_sqft", label: "Wall area (sqft)" }],
    "Backsplash & Tile": [{ key: "tile_sqft", label: "Tile area (sqft)" }],
    Lighting: [{ key: "fixture_count", label: "Light fixtures (count)" }],
    "Plumbing Fixtures": [{ key: "fixture_count_plumbing", label: "Plumbing fixtures (count)" }],
    "Built-ins & Storage": [{ key: "builtin_linear_ft", label: "Built-in run (linear ft)" }],
    "Furniture Layout": [],
    "Window Treatments": [{ key: "window_count", label: "Windows (count)" }],
    "Full Redesign": [],
  },
  size_fields: [
    { key: "room_length_ft", label: "Room length (ft)", required: true },
    { key: "room_width_ft", label: "Room width (ft)", required: true },
    { key: "ceiling_height_ft", label: "Ceiling height (ft)", required: false },
  ],
  retailers: [
    { name: "The Home Depot", domain: "homedepot.com" },
    { name: "Lowe's", domain: "lowes.com" },
    { name: "IKEA", domain: "ikea.com" },
    { name: "Floor & Decor", domain: "flooranddecor.com" },
    { name: "Build.com", domain: "build.com" },
    { name: "Wayfair", domain: "wayfair.com" },
  ],
  default_prompt_template:
    "Redesign this {room} as a {tier} {style} interior{features}. Keep the walls, windows, doors, and camera angle. Show a photorealistic, buildable finished room with realistic materials, coherent lighting, correctly scaled furniture, and no labels or text.",
};

export const FALLBACK_SPACES: SpaceConfig[] = [EXTERIOR_SPACE, INTERIOR_SPACE];

export async function fetchSpaces(): Promise<SpaceConfig[]> {
  const res = await fetch("/api/spaces");
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to load space types: ${res.status}`));
  }
  const body = (await res.json()) as { spaces?: SpaceConfig[] };
  return Array.isArray(body.spaces) && body.spaces.length > 0 ? body.spaces : FALLBACK_SPACES;
}

export function findSpace(spaces: SpaceConfig[], id: string | null | undefined): SpaceConfig {
  return spaces.find((s) => s.id === id) ?? spaces.find((s) => s.id === "exterior") ?? EXTERIOR_SPACE;
}

/** Dimension inputs relevant to the selected feature categories, de-duplicated by key. */
export function dimensionFieldsFor(space: SpaceConfig, categories: string[]): DimensionField[] {
  const seen = new Set<string>();
  const fields: DimensionField[] = [];
  for (const cat of categories) {
    for (const f of space.dimension_fields[cat] ?? []) {
      if (!seen.has(f.key)) {
        seen.add(f.key);
        fields.push(f);
      }
    }
  }
  return fields;
}

/** Fill the space's prompt template from the picker selections. */
export function seedPromptFor(
  space: SpaceConfig,
  roomType: string | null | undefined,
  featureCategories: string[],
  style: string,
  qualityTier: string,
): string {
  const features =
    featureCategories.length > 0 ? ` featuring ${featureCategories.join(", ")}` : "";
  return space.default_prompt_template
    .replace("{tier}", qualityTier.toLowerCase())
    .replace("{style}", style.toLowerCase())
    .replace("{features}", features)
    .replace("{room}", (roomType ?? "room").toLowerCase());
}

/** "Kitchen" for an interior project with a room, otherwise the space label. */
export function spaceLabelFor(space: SpaceConfig, roomType: string | null | undefined): string {
  return space.id === "interior" && roomType ? roomType : space.label;
}
