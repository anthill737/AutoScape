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
        { id: "gpt-image-2.5-flare", display_name: "GPT Image 2.5 Flare", tier: "balanced", quality: 4, cost: "~few cents / image", cost_rank: 2, recommended: true, note: "Fast everyday model", current: true },
        { id: "gpt-image-2.5-sunburst", display_name: "GPT Image 2.5 Sunburst", tier: "best", quality: 5, cost: "~few cents / image", cost_rank: 3, recommended: false, note: "Most capable for edits", current: true },
        { id: "gpt-image-2.5-flare-2026-09-08", display_name: "GPT Image 2.5 Flare 2026 09 08", tier: "balanced", quality: 4, cost: "~few cents / image", cost_rank: 2, recommended: false, note: "Dated snapshot of gpt-image-2.5-flare; same model, pinned version", current: false },
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
        { id: "gemini-3.1-flash-image", display_name: "Nano Banana 2", tier: "balanced", quality: 4, cost: "$0.067 / image at 1K", cost_rank: 3, recommended: true, note: "Nano Banana 2", current: true },
        { id: "gemini-3-pro-image", display_name: "Nano Banana Pro", tier: "best", quality: 5, cost: "$0.134 / image", cost_rank: 5, recommended: false, note: "Nano Banana Pro", current: true },
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
        { id: "claude-opus-5-5", display_name: "Claude Opus 5.5", tier: "best", quality: 5, cost: "$4 in \u00b7 $20 out per 1M tokens", cost_rank: 3, recommended: true, note: "Current Opus", current: true },
        { id: "claude-sonnet-5-5", display_name: "Claude Sonnet 5.5", tier: "balanced", quality: 4, cost: "$2 in \u00b7 $10 out per 1M tokens", cost_rank: 2, recommended: false, note: "Best value", current: true },
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
        { id: "gpt-5.6-terra", display_name: "GPT 5.6 Terra", tier: "balanced", quality: 4, cost: "$2 in \u00b7 $12 out per 1M tokens", cost_rank: 3, recommended: true, note: "Balances intelligence and cost", current: true },
        { id: "gpt-6-luna", display_name: "GPT 6 Luna", tier: "fast", quality: 3, cost: "$0.1 in \u00b7 $0.5 out per 1M tokens", cost_rank: 1, recommended: false, note: "Very cheap", current: true },
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
      models: [{ id: "gemini-3.8-flash", display_name: "Gemini 3.8 Flash", tier: "balanced", quality: 4, cost: "$0.75 in \u00b7 $3.75 out per 1M tokens; free tier", cost_rank: 2, recommended: true, note: "Free tier available", current: true }],
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
        { id: "perplexity/sonar", display_name: "Sonar", tier: "balanced", quality: 3, cost: "$0.25 in \u00b7 $2.5 out per 1M tokens + $0.0025 per web search", cost_rank: 1, recommended: true, note: "Cheapest", current: true },
        { id: "openai/gpt-5.6-luna", display_name: "GPT 5.6 Luna", tier: "fast", quality: 3, cost: "$0.2 in \u00b7 $1.2 out per 1M tokens + $0.0025 per web search", cost_rank: 1, recommended: false, note: null, current: true },
      ],
      source: "live",
      error: null,
    },
  ],
};

// Space-type configs are fetched on every page too; serve the built-in list.
vi.mock("../api/spaces", async () => {
  const actual = await vi.importActual<typeof import("../api/spaces")>("../api/spaces");
  return {
    ...actual,
    fetchSpaces: vi.fn(async () => actual.FALLBACK_SPACES),
  };
});

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
  const { resetSpacesCache } = await import("../hooks/useSpaces");
  resetSpacesCache();
  try {
    window.localStorage.clear();
  } catch {
    // jsdom without storage
  }
});
