import type { ProviderModels } from "../api/models";

/** Persisted per-browser model choices so a user is not re-picking on every visit. */
export interface SavedModelSelection {
  imageProvider?: string;
  /** model id keyed by provider slug, e.g. { gpt_image: "gpt-image-2.5-flare" } */
  imageModels?: Record<string, string>;
  materialsProvider?: string;
  materialsModels?: Record<string, string>;
  groundingModel?: string;
}

export const MODEL_SELECTION_STORAGE_KEY = "autoscape.models.v1";

export function loadModelSelection(): SavedModelSelection {
  try {
    const raw = window.localStorage.getItem(MODEL_SELECTION_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === "object" ? (parsed as SavedModelSelection) : {};
  } catch {
    return {};
  }
}

export function saveModelSelection(patch: SavedModelSelection): void {
  try {
    const current = loadModelSelection();
    const next: SavedModelSelection = {
      ...current,
      ...patch,
      imageModels: { ...(current.imageModels ?? {}), ...(patch.imageModels ?? {}) },
      materialsModels: {
        ...(current.materialsModels ?? {}),
        ...(patch.materialsModels ?? {}),
      },
    };
    window.localStorage.setItem(MODEL_SELECTION_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage may be unavailable (private mode); selection just won't persist.
  }
}

/**
 * Pick the model to show as selected for a provider: the caller's explicit choice if
 * set, otherwise the provider's default. A saved choice that is no longer in the
 * vendor's list is kept (it may simply be missing from a fallback list).
 */
export function resolveSelectedModel(
  provider: ProviderModels | undefined,
  explicit: string | undefined,
): string {
  if (explicit && explicit.trim()) return explicit;
  return provider?.default_model ?? "";
}

/** Options for a select: the vendor's list, plus the current value if it is not listed. */
export function modelOptions(
  provider: ProviderModels | undefined,
  selected: string,
): { id: string; display_name: string }[] {
  const options = [...(provider?.models ?? [])];
  if (selected && !options.some((m) => m.id === selected)) {
    options.unshift({ id: selected, display_name: `${selected} (saved)` });
  }
  return options;
}
