import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { buildSheetToHtml, exportBuildSheet } from "../utils/exportBuildSheet";
import type { BuildSheetOut } from "../api/designRequests";

const sampleBuildSheet: BuildSheetOut = {
  id: 42,
  render_id: 7,
  materials_llm: "ClaudeSonnet",
  material_items: [
    {
      name: "Pressure-treated 2x6",
      quantity: 20,
      unit: "boards",
      unit_cost_range: "$8 - $10",
      total_cost_range: "$160 - $200",
      vendor: "Home Depot",
      product_url: "https://www.homedepot.com/p/123",
      notes: "8ft lengths",
    },
    {
      name: "Concrete mix",
      quantity: 6,
      unit: "bags",
      unit_cost_range: "$7 - $9",
      total_cost_range: "$42 - $54",
      vendor: "Lowe's",
      product_url: "",
      notes: "",
    },
  ],
  tool_list: ["Circular saw", "Drill", "Level"],
  build_steps: [
    {
      step_number: 1,
      description: "Mark the deck perimeter with stakes and string",
      estimated_time: "2 hours",
      skill_notes: "Basic",
    },
    {
      step_number: 2,
      description: "Dig post holes to frost depth",
      estimated_time: "4 hours",
      skill_notes: "Intermediate",
    },
  ],
  total_cost_range: "$3,500 - $5,200",
  skill_level: "Intermediate",
  assumptions: [
    "Deck area calculated as 12ft x 16ft = 192 sqft",
    "Local lumber prices may vary",
  ],
  created_at: "2024-06-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// buildSheetToHtml — pure unit tests
// ---------------------------------------------------------------------------

describe("buildSheetToHtml", () => {
  it("returns a valid HTML document with DOCTYPE", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toMatch(/^<!DOCTYPE html>/i);
    expect(html).toContain("<html");
    expect(html).toContain("</html>");
  });

  it("has no external resource references (no http src/href in head)", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    // Extract the <head> section
    const headMatch = html.match(/<head[\s\S]*?<\/head>/i);
    expect(headMatch).not.toBeNull();
    const head = headMatch![0];
    // No http/https URLs inside the head
    expect(head).not.toMatch(/https?:\/\//);
  });

  it("includes inline <style> tag with CSS content", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toMatch(/<style>[\s\S]+<\/style>/);
  });

  it("does not include any <script> tags (no JS)", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).not.toContain("<script");
  });

  it("includes total cost range and skill level", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toContain("$3,500 - $5,200");
    expect(html).toContain("Intermediate");
    expect(html).toContain("Total Estimated Cost");
    expect(html).toContain("Skill Level");
  });

  it("includes materials table with all column headers", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toContain("Name");
    expect(html).toContain("Qty");
    expect(html).toContain("Unit");
    expect(html).toContain("Unit Cost");
    expect(html).toContain("Total Cost");
    expect(html).toContain("Vendor");
    expect(html).toContain("Product");
  });

  it("includes material item data", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toContain("Pressure-treated 2x6");
    expect(html).toContain("boards");
    expect(html).toContain("$8 - $10");
    expect(html).toContain("$160 - $200");
    expect(html).toContain("Home Depot");
  });

  it("includes product URL as anchor link", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toContain('href="https://www.homedepot.com/p/123"');
  });

  it("shows em dash for missing product URL", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toContain("—");
  });

  it("includes tool list", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toContain("Tools Needed");
    expect(html).toContain("Circular saw");
    expect(html).toContain("Drill");
    expect(html).toContain("Level");
  });

  it("includes build steps with descriptions and times", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toContain("Build Steps");
    expect(html).toContain("Mark the deck perimeter with stakes and string");
    expect(html).toContain("2 hours");
    expect(html).toContain("Dig post holes to frost depth");
    expect(html).toContain("4 hours");
  });

  it("includes assumptions", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).toContain("Assumptions");
    expect(html).toContain("Deck area calculated as 12ft x 16ft = 192 sqft");
    expect(html).toContain("Local lumber prices may vary");
  });

  it("embeds base64 image when imageDataUri is provided", () => {
    const fakeDataUri = "data:image/png;base64,iVBORw0KGgo=";
    const html = buildSheetToHtml(sampleBuildSheet, fakeDataUri);
    expect(html).toContain(fakeDataUri);
    expect(html).toContain('<img class="render-img"');
  });

  it("omits img tag when imageDataUri is null", () => {
    const html = buildSheetToHtml(sampleBuildSheet, null);
    expect(html).not.toContain('<img class="render-img"');
  });

  it("escapes HTML special characters in item names", () => {
    const sheet = {
      ...sampleBuildSheet,
      material_items: [
        {
          ...sampleBuildSheet.material_items[0],
          name: '<script>alert("xss")</script>',
        },
      ],
    };
    const html = buildSheetToHtml(sheet, null);
    expect(html).not.toContain("<script>alert");
    expect(html).toContain("&lt;script&gt;");
  });

  it("skips materials section when material_items is empty", () => {
    const sheet = { ...sampleBuildSheet, material_items: [] };
    const html = buildSheetToHtml(sheet, null);
    // No materials table headers
    expect(html).not.toContain("<table");
  });

  it("skips tool list section when tool_list is empty", () => {
    const sheet = { ...sampleBuildSheet, tool_list: [] };
    const html = buildSheetToHtml(sheet, null);
    expect(html).not.toContain("Tools Needed");
  });

  it("skips build steps section when build_steps is empty", () => {
    const sheet = { ...sampleBuildSheet, build_steps: [] };
    const html = buildSheetToHtml(sheet, null);
    expect(html).not.toContain("Build Steps");
  });

  it("skips assumptions section when assumptions is empty", () => {
    const sheet = { ...sampleBuildSheet, assumptions: [] };
    const html = buildSheetToHtml(sheet, null);
    expect(html).not.toContain("Assumptions");
  });
});

// ---------------------------------------------------------------------------
// exportBuildSheet — integration tests with DOM mocks
// ---------------------------------------------------------------------------

describe("exportBuildSheet", () => {
  let appendChildSpy: ReturnType<typeof vi.spyOn>;
  let removeChildSpy: ReturnType<typeof vi.spyOn>;
  let createObjectURLSpy: ReturnType<typeof vi.fn>;
  let revokeObjectURLSpy: ReturnType<typeof vi.fn>;
  let clickSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    clickSpy = vi.fn();
    createObjectURLSpy = vi.fn().mockReturnValue("blob:fake-url");
    revokeObjectURLSpy = vi.fn();

    vi.stubGlobal("URL", {
      createObjectURL: createObjectURLSpy,
      revokeObjectURL: revokeObjectURLSpy,
    });

    appendChildSpy = vi.spyOn(document.body, "appendChild").mockImplementation((node) => node);
    removeChildSpy = vi.spyOn(document.body, "removeChild").mockImplementation((node) => node);

    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      if (tag === "a") {
        const a = {
          href: "",
          download: "",
          click: clickSpy,
        } as unknown as HTMLAnchorElement;
        return a;
      }
      return document.createElement(tag);
    });

    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("FileReader", class {
      result: string | null = null;
      onloadend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      readAsDataURL(_blob: Blob) {
        this.result = "data:image/png;base64,abc123";
        this.onloadend?.();
      }
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates an <a> element with correct download filename and triggers click", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      blob: async () => new Blob(["fake"], { type: "image/png" }),
    });

    await exportBuildSheet(sampleBuildSheet, "/renders/7");

    expect(createObjectURLSpy).toHaveBeenCalledOnce();
    expect(clickSpy).toHaveBeenCalledOnce();
    expect(appendChildSpy).toHaveBeenCalledOnce();
    expect(removeChildSpy).toHaveBeenCalledOnce();
    expect(revokeObjectURLSpy).toHaveBeenCalledWith("blob:fake-url");
  });

  it("sets download filename based on build sheet id", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      blob: async () => new Blob(["fake"], { type: "image/png" }),
    });

    let capturedAnchor: { download?: string } = {};
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      if (tag === "a") {
        capturedAnchor = { href: "", download: "", click: clickSpy } as unknown as HTMLAnchorElement;
        return capturedAnchor as unknown as HTMLElement;
      }
      return document.createElement(tag);
    });

    await exportBuildSheet(sampleBuildSheet, null);

    expect(capturedAnchor.download).toBe("autoscape-build-sheet-42.html");
  });

  it("exports without image when renderImageUrl is null", async () => {
    await exportBuildSheet(sampleBuildSheet, null);

    expect(fetch as ReturnType<typeof vi.fn>).not.toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalledOnce();
  });

  it("exports without image when image fetch fails", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("network error"));

    await exportBuildSheet(sampleBuildSheet, "/renders/7");

    // Should still complete — graceful degradation
    expect(clickSpy).toHaveBeenCalledOnce();
  });

  it("passes a Blob of type text/html to createObjectURL", async () => {
    await exportBuildSheet(sampleBuildSheet, null);

    const blobArg = createObjectURLSpy.mock.calls[0][0] as Blob;
    expect(blobArg.type).toBe("text/html");
  });
});
