import { useEffect, useState } from "react";
import { FALLBACK_SPACES, fetchSpaces, type SpaceConfig } from "../api/spaces";

let cached: SpaceConfig[] | null = null;
let inflight: Promise<SpaceConfig[]> | null = null;

function load(): Promise<SpaceConfig[]> {
  if (cached) return Promise.resolve(cached);
  if (inflight) return inflight;
  inflight = fetchSpaces()
    .then((spaces) => {
      cached = spaces;
      return spaces;
    })
    .catch(() => FALLBACK_SPACES)
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

/** Test hook: forget any cached space list. */
export function resetSpacesCache(): void {
  cached = null;
  inflight = null;
}

/**
 * Space-type configs (outdoor / interior). Falls back to the built-in list when the
 * backend does not serve /api/spaces, so pages never block on it.
 */
export function useSpaces(): { spaces: SpaceConfig[]; loading: boolean } {
  const [spaces, setSpaces] = useState<SpaceConfig[]>(cached ?? FALLBACK_SPACES);
  const [loading, setLoading] = useState(cached == null);

  useEffect(() => {
    let active = true;
    load().then((result) => {
      if (active) {
        setSpaces(result);
        setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  return { spaces, loading };
}
