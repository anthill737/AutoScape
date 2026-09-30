import { ApiError, parseApiError } from "./errors";

// Provider slugs are stable API/database values; the concrete model within a vendor is
// chosen per request from GET /api/models (see src/api/models.ts).
export const IMAGE_PROVIDERS = [
  { value: "gpt_image", label: "OpenAI Images" },
  { value: "gemini_flash_image", label: "Google Gemini Images" },
] as const;
export type ImageProvider = (typeof IMAGE_PROVIDERS)[number]["value"];

export const FEATURE_CATEGORIES = [
  "Deck",
  "Patio",
  "Garden Beds",
  "Fire Feature",
  "Pergola",
  "Pool",
  "Full Redesign",
] as const;
export type FeatureCategory = (typeof FEATURE_CATEGORIES)[number];

export const STYLES = [
  "Modern",
  "Traditional",
  "Cottage",
  "Xeriscape",
  "Tropical",
  "Rustic",
] as const;
export type Style = (typeof STYLES)[number];

export const QUALITY_TIERS = ["Budget", "Mid-range", "Premium"] as const;
export type QualityTier = (typeof QUALITY_TIERS)[number];

export const MATERIALS_LLMS = [
  { value: "claude_sonnet", label: "Anthropic Claude" },
  { value: "gpt5", label: "OpenAI GPT" },
  { value: "gemini_pro", label: "Google Gemini" },
] as const;
export const DEFAULT_MATERIALS_LLM: string = MATERIALS_LLMS[0].value;

// TypeScript interfaces matching backend schemas
export interface RenderOut {
  id: number;
  design_request_id: number;
  image_path: string;
  image_url: string | null;
  is_chosen: boolean;
  created_at: string;
}

export interface DesignRequestOut {
  id: number;
  project_id: number;
  parent_render_id: number | null;
  image_provider: string;
  /** Vendor model id that produced the renders; absent on rows from older versions. */
  image_model?: string | null;
  feature_categories: string[];
  style: string;
  quality_tier: string;
  composed_prompt: string;
  created_at: string;
  renders: RenderOut[];
}

export interface MaterialItem {
  name: string;
  quantity: number;
  unit: string;
  unit_cost_range: string;
  total_cost_range: string;
  vendor: string;
  product_url: string;
  notes?: string;
}

export interface BuildStep {
  step_number: number;
  description: string;
  estimated_time: string;
  skill_notes: string;
}

export interface BuildSheetOut {
  id: number;
  render_id: number;
  materials_llm: string;
  materials_model?: string | null;
  grounding_model?: string | null;
  material_items: MaterialItem[];
  tool_list: string[];
  build_steps: BuildStep[];
  total_cost_range: string;
  skill_level: string;
  assumptions: string[];
  created_at: string;
}

// Dimension field definition: key matches the backend default dict key
export interface DimensionField {
  key: string;
  label: string;
}

const CATEGORY_DIMENSION_FIELDS: Record<string, DimensionField[]> = {
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
};

/** Returns the dimension input fields relevant to the given feature categories. */
export function getDimensionFieldsForCategories(categories: string[]): DimensionField[] {
  const seen = new Set<string>();
  const fields: DimensionField[] = [];
  for (const cat of categories) {
    for (const f of CATEGORY_DIMENSION_FIELDS[cat] ?? []) {
      if (!seen.has(f.key)) {
        seen.add(f.key);
        fields.push(f);
      }
    }
  }
  return fields;
}

/** Pre-fills a Composed Prompt from the picker selections. */
export function seedComposedPrompt(
  featureCategories: string[],
  style: string,
  qualityTier: string,
): string {
  const catPart =
    featureCategories.length > 0 ? ` featuring ${featureCategories.join(", ")}` : "";
  return (
    `Design a ${qualityTier.toLowerCase()} ${style.toLowerCase()} outdoor space${catPart}. ` +
    "Preserve the existing home, camera angle, and yard boundaries. Show a photorealistic, " +
    "buildable finished design with realistic materials, natural daylight, clean geometry, " +
    "and no labels or text."
  );
}

// API helpers ---------------------------------------------------------------

export async function createDesignRequest(
  projectId: number,
  data: {
    image_provider: string;
    image_model?: string | null;
    feature_categories: string[];
    style: string;
    quality_tier: string;
    composed_prompt: string;
    parent_render_id: number | null;
  },
): Promise<DesignRequestOut> {
  const res = await fetch(`/api/projects/${projectId}/design-requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new ApiError(await parseApiError(res), res.status);
  }
  return res.json() as Promise<DesignRequestOut>;
}

export async function chooseRender(renderId: number): Promise<RenderOut> {
  const res = await fetch(`/api/renders/${renderId}/choose`, { method: "PATCH" });
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to choose render: ${res.status}`));
  }
  return res.json() as Promise<RenderOut>;
}

export async function getDimensionDefaults(
  renderId: number,
): Promise<Record<string, string | number>> {
  const res = await fetch(`/api/renders/${renderId}/dimension-defaults`, { method: "POST" });
  if (!res.ok) {
    throw new Error(
      await parseApiError(res, `Failed to get dimension defaults: ${res.status}`),
    );
  }
  return res.json() as Promise<Record<string, string | number>>;
}

export async function getBuildSheet(renderId: number): Promise<BuildSheetOut> {
  const res = await fetch(`/api/renders/${renderId}/build-sheet`);
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to get build sheet: ${res.status}`));
  }
  return res.json() as Promise<BuildSheetOut>;
}

export interface BuildSheetModelChoices {
  materialsModel?: string | null;
  groundingModel?: string | null;
}

export async function createBuildSheet(
  renderId: number,
  materialsLlm: string,
  dimensions: Record<string, string>,
  models: BuildSheetModelChoices = {},
): Promise<BuildSheetOut> {
  const body: Record<string, unknown> = { materials_llm: materialsLlm, dimensions };
  if (models.materialsModel) body.materials_model = models.materialsModel;
  if (models.groundingModel) body.grounding_model = models.groundingModel;
  const res = await fetch(`/api/renders/${renderId}/build-sheet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  return res.json() as Promise<BuildSheetOut>;
}
