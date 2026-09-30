import { parseApiError } from "./errors";

/** One model a vendor currently offers for a role, plus curated comparison data. */
export interface ModelInfo {
  id: string;
  display_name: string;
  /** best | balanced | fast | legacy | unknown */
  tier: string;
  /** 1 (weakest) .. 5 (strongest) within its role; null when unknown. */
  quality: number | null;
  /** Human-readable price, e.g. "~$0.01 / image". */
  cost: string | null;
  /** 1 (cheapest) .. 5 (priciest) within its role; null when unknown. */
  cost_rank: number | null;
  recommended: boolean;
  /** Short caveat, e.g. "Retired 2026-06-25". */
  note: string | null;
  /** False for dated snapshots and retired ids; hidden unless the user asks. */
  current: boolean;
}

/** A provider (vendor + adapter) and the models it currently offers. */
export interface ProviderModels {
  /** Stable slug used by the API and database, e.g. "gpt_image". */
  slug: string;
  role: "image" | "materials" | "grounding";
  vendor: string;
  label: string;
  key_env: string;
  key_set: boolean;
  default_model: string;
  models: ModelInfo[];
  /** "live" when fetched from the vendor, "fallback" when a static list was used. */
  source: "live" | "fallback";
  error: string | null;
}

export interface ModelCatalog {
  image: ProviderModels[];
  materials: ProviderModels[];
  grounding: ProviderModels[];
}

export const EMPTY_CATALOG: ModelCatalog = { image: [], materials: [], grounding: [] };

export async function fetchModelCatalog(refresh = false): Promise<ModelCatalog> {
  const res = await fetch(refresh ? "/api/models?refresh=true" : "/api/models");
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to load models: ${res.status}`));
  }
  return res.json() as Promise<ModelCatalog>;
}

/** Find a provider entry by slug in any role. */
export function findProvider(
  catalog: ModelCatalog,
  slug: string,
): ProviderModels | undefined {
  return [...catalog.image, ...catalog.materials, ...catalog.grounding].find(
    (p) => p.slug === slug,
  );
}

/** Human label for a model id, falling back to the id itself. */
export function modelDisplayName(provider: ProviderModels | undefined, modelId: string): string {
  return provider?.models.find((m) => m.id === modelId)?.display_name ?? modelId;
}

/** Badges derived from a provider's current models: which is best, which is cheapest. */
export interface ModelBadges {
  bestQualityId: string | null;
  cheapestId: string | null;
}

export function computeModelBadges(models: ModelInfo[]): ModelBadges {
  const current = models.filter((m) => m.current);
  const withQuality = current.filter((m) => m.quality != null);
  const withCost = current.filter((m) => m.cost_rank != null);
  const maxQuality = Math.max(...withQuality.map((m) => m.quality as number));
  const minCost = Math.min(...withCost.map((m) => m.cost_rank as number));
  const best = withQuality.filter((m) => m.quality === maxQuality);
  const cheap = withCost.filter((m) => m.cost_rank === minCost);
  return {
    // Only award a badge when it singles something out.
    bestQualityId: best.length === 1 && withQuality.length > 1 ? best[0].id : null,
    cheapestId: cheap.length === 1 && withCost.length > 1 ? cheap[0].id : null,
  };
}
