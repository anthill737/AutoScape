// The setup file mocks this module for page tests; here we exercise the real client.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.unmock("../api/models");

import { fetchModelCatalog, findProvider, modelDisplayName } from "../api/models";
import {
  loadModelSelection,
  modelOptions,
  resolveSelectedModel,
  saveModelSelection,
} from "../utils/modelSelection";
import { TEST_MODEL_CATALOG } from "./setup";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchModelCatalog", () => {
  it("GETs /api/models and returns the grouped catalog", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => TEST_MODEL_CATALOG,
    });
    const catalog = await fetchModelCatalog();
    expect(fetch).toHaveBeenCalledWith("/api/models");
    expect(catalog.image.map((p) => p.slug)).toEqual(["gpt_image", "gemini_flash_image"]);
  });

  it("passes refresh=true through to the backend", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => TEST_MODEL_CATALOG,
    });
    await fetchModelCatalog(true);
    expect(fetch).toHaveBeenCalledWith("/api/models?refresh=true");
  });

  it("surfaces the backend detail string on failure", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: "RuntimeError: vendor exploded" }),
    });
    await expect(fetchModelCatalog()).rejects.toThrow("RuntimeError: vendor exploded");
  });
});

describe("catalog helpers", () => {
  const catalog = TEST_MODEL_CATALOG as unknown as Parameters<typeof findProvider>[0];

  it("finds providers across roles and resolves display names", () => {
    expect(findProvider(catalog, "perplexity")?.role).toBe("grounding");
    expect(modelDisplayName(findProvider(catalog, "gpt5"), "gpt-6-luna")).toBe("GPT 6 Luna");
    expect(modelDisplayName(findProvider(catalog, "gpt5"), "gpt-unknown")).toBe("gpt-unknown");
  });

  it("resolves the default when nothing explicit is chosen", () => {
    const provider = findProvider(catalog, "gemini_flash_image");
    expect(resolveSelectedModel(provider, undefined)).toBe("gemini-3.1-flash-image");
    expect(resolveSelectedModel(provider, "gemini-3-pro-image")).toBe("gemini-3-pro-image");
    expect(resolveSelectedModel(undefined, undefined)).toBe("");
  });

  it("keeps a saved model that the vendor list no longer includes", () => {
    const provider = findProvider(catalog, "gpt_image");
    const options = modelOptions(provider, "gpt-image-2");
    expect(options[0]).toEqual({ id: "gpt-image-2", display_name: "gpt-image-2 (saved)" });
    expect(options).toHaveLength(3);
  });

  it("merges saved selections instead of overwriting them", () => {
    saveModelSelection({ imageModels: { gpt_image: "gpt-image-2.5-sunburst" } });
    saveModelSelection({
      materialsModels: { gpt5: "gpt-6-luna" },
      groundingModel: "perplexity/sonar",
    });
    expect(loadModelSelection()).toEqual({
      imageModels: { gpt_image: "gpt-image-2.5-sunburst" },
      materialsModels: { gpt5: "gpt-6-luna" },
      groundingModel: "perplexity/sonar",
    });
  });
});
