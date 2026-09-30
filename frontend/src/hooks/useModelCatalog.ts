import { useCallback, useEffect, useState } from "react";
import { EMPTY_CATALOG, fetchModelCatalog, ModelCatalog } from "../api/models";

interface CatalogState {
  catalog: ModelCatalog;
  loading: boolean;
  error: string | null;
}

// One in-flight request shared by every component that mounts the hook, so the
// header strip and the build-sheet panel do not each hit the vendors' list endpoints.
let cached: ModelCatalog | null = null;
let inflight: Promise<ModelCatalog> | null = null;

function load(refresh: boolean): Promise<ModelCatalog> {
  if (!refresh && cached) return Promise.resolve(cached);
  if (!refresh && inflight) return inflight;
  inflight = fetchModelCatalog(refresh)
    .then((catalog) => {
      cached = catalog;
      return catalog;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

/** Test hook: forget any cached catalog. */
export function resetModelCatalogCache(): void {
  cached = null;
  inflight = null;
}

/**
 * Loads the model catalog once and exposes it plus a `refresh()` that bypasses the
 * backend cache (used by the Settings page after a key changes).
 */
export function useModelCatalog(): CatalogState & { refresh: () => Promise<void> } {
  const [state, setState] = useState<CatalogState>({
    catalog: cached ?? EMPTY_CATALOG,
    loading: cached == null,
    error: null,
  });

  const run = useCallback(async (refresh: boolean) => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const catalog = await load(refresh);
      setState({ catalog, loading: false, error: null });
    } catch (e: unknown) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load models",
      }));
    }
  }, []);

  useEffect(() => {
    let active = true;
    load(false)
      .then((catalog) => {
        if (active) setState({ catalog, loading: false, error: null });
      })
      .catch((e: unknown) => {
        if (active) {
          setState((prev) => ({
            ...prev,
            loading: false,
            error: e instanceof Error ? e.message : "Failed to load models",
          }));
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return { ...state, refresh: () => run(true) };
}
