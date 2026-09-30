import "@testing-library/jest-dom";
import { afterEach, vi } from "vitest";

/**
 * The model catalog is fetched by ProjectDetailPage and SettingsPage on mount. Most
 * page tests script `fetch` as an ordered list of responses, so that extra request
 * would shift every mock. Serve a static catalog from a mocked module instead; tests
 * for the real client opt out with `vi.unmock("../api/models")`.
 */
export const TEST_MODEL_CATALOG = {
  image: [
    {
      slug: "gpt_image",
      role: "image",
      vendor: "openai",
      label: "OpenAI Images",
      key_env: "OPENAI_API_KEY",
      key_set: true,
      default_model: "gpt-image-2.5-flare",
      models: [
        { id: "gpt-image-2.5-flare", display_name: "GPT Image 2.5 Flare" },
        { id: "gpt-image-2.5-sunburst", display_name: "GPT Image 2.5 Sunburst" },
      ],
      source: "live",
      error: null,
    },
    {
      slug: "gemini_flash_image",
      role: "image",
      vendor: "google",
      label: "Google Gemini Images",
      key_env: "GOOGLE_API_KEY",
      key_set: true,
      default_model: "gemini-3.1-flash-image",
      models: [
        { id: "gemini-3.1-flash-image", display_name: "Nano Banana 2" },
        { id: "gemini-3-pro-image", display_name: "Nano Banana Pro" },
      ],
      source: "live",
      error: null,
    },
  ],
  materials: [
    {
      slug: "claude_sonnet",
      role: "materials",
      vendor: "anthropic",
      label: "Anthropic Claude",
      key_env: "ANTHROPIC_API_KEY",
      key_set: false,
      default_model: "claude-opus-5-5",
      models: [
        { id: "claude-opus-5-5", display_name: "Claude Opus 5.5" },
        { id: "claude-sonnet-5-5", display_name: "Claude Sonnet 5.5" },
      ],
      source: "fallback",
      error: "ANTHROPIC_API_KEY is not set",
    },
    {
      slug: "gpt5",
      role: "materials",
      vendor: "openai",
      label: "OpenAI GPT",
      key_env: "OPENAI_API_KEY",
      key_set: true,
      default_model: "gpt-5.6-terra",
      models: [
        { id: "gpt-5.6-terra", display_name: "GPT 5.6 Terra" },
        { id: "gpt-6-luna", display_name: "GPT 6 Luna" },
      ],
      source: "live",
      error: null,
    },
    {
      slug: "gemini_pro",
      role: "materials",
      vendor: "google",
      label: "Google Gemini",
      key_env: "GOOGLE_API_KEY",
      key_set: true,
      default_model: "gemini-3.8-flash",
      models: [{ id: "gemini-3.8-flash", display_name: "Gemini 3.8 Flash" }],
      source: "live",
      error: null,
    },
  ],
  grounding: [
    {
      slug: "perplexity",
      role: "grounding",
      vendor: "perplexity",
      label: "Perplexity Agent API",
      key_env: "PERPLEXITY_API_KEY",
      key_set: true,
      default_model: "perplexity/sonar",
      models: [
        { id: "perplexity/sonar", display_name: "Sonar" },
        { id: "openai/gpt-5.6-luna", display_name: "GPT 5.6 Luna" },
      ],
      source: "live",
      error: null,
    },
  ],
};

vi.mock("../api/models", async () => {
  const actual = await vi.importActual<typeof import("../api/models")>("../api/models");
  return {
    ...actual,
    fetchModelCatalog: vi.fn(async () => TEST_MODEL_CATALOG),
  };
});

// The catalog hook memoises across mounts; model choices persist in localStorage.
// Reset both so tests do not leak into each other.
afterEach(async () => {
  const { resetModelCatalogCache } = await import("../hooks/useModelCatalog");
  resetModelCatalogCache();
  try {
    window.localStorage.clear();
  } catch {
    // jsdom without storage
  }
});
