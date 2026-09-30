import { parseApiError } from "./errors";

/** One model a vendor currently offers for a role. */
export interface ModelInfo {
  id: string;
  display_name: string;
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
