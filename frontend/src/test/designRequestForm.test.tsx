import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ProjectDetailPage from "../pages/ProjectDetailPage";
import { ThemeProvider } from "../theme/ThemeProvider";

function renderAt(path: string) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/projects/:id/renders/:renderId" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

const render1 = {
  id: 1,
  design_request_id: 10,
  image_path: "/a.png",
  image_url: "/renders/1",
  is_chosen: true,
  created_at: "2024-06-01T00:00:00Z",
};

const projectWithRender = {
  id: 1,
  address: "123 Main St",
  lot_size_sqft: 5000,
  house_sqft: 2000,
  site_photo_url: "/images/1/site_photo.jpg",
  created_at: "2024-06-01T00:00:00Z",
  design_requests: [
    {
      id: 10,
      project_id: 1,
      parent_render_id: null,
      image_provider: "gemini_flash_image",
      image_model: "gemini-3-pro-image",
      feature_categories: ["Patio"],
      style: "Rustic",
      quality_tier: "Mid-range",
      composed_prompt: "A rustic mid-range patio.",
      created_at: "2024-06-01T00:00:00Z",
      renders: [render1],
    },
  ],
};

const emptyProject = { ...projectWithRender, site_photo_url: null, design_requests: [] };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DesignRequestForm — all settings live in one panel", () => {
  async function openNewForm(project: unknown = emptyProject) {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Not found" }),
    });
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => project,
    });
    renderAt("/projects/1");
    await userEvent.click(
      await screen.findByRole("button", { name: /New Design Request/i }),
    );
    return screen.getByRole("form", { name: /New design request/i });
  }

  it("shows the starting image, plain chip labels, and the generate hint", async () => {
    const form = await openNewForm();

    expect(within(form).getByText(/Starting from/i)).toBeInTheDocument();
    expect(within(form).getByText(/The site photo/i)).toBeInTheDocument();
    // Labels are the bare option names, not "Fire Feature category" / "Modern style".
    expect(within(form).getByRole("checkbox", { name: "Fire Feature" })).toBeInTheDocument();
    expect(within(form).queryByText(/Fire Feature category/)).not.toBeInTheDocument();
    expect(within(form).queryByText(/Modern style/)).not.toBeInTheDocument();
    expect(within(form).getByText(/Nothing is sent until you click Generate/i)).toBeInTheDocument();
    expect(within(form).getByText(/Makes 3 variations with the settings in this panel/i)).toBeInTheDocument();
    // The old header-strip settings block is gone.
    expect(screen.queryByText(/Settings for this project/i)).not.toBeInTheDocument();
  });

  it("stops rewriting the prompt once edited and offers a reset", async () => {
    const form = await openNewForm();
    const textarea = within(form).getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.value).toMatch(/modern/i);

    await userEvent.clear(textarea);
    await userEvent.type(textarea, "My own prompt");
    await userEvent.click(within(form).getByRole("radio", { name: "Rustic" }));
    expect(textarea.value).toBe("My own prompt");

    await userEvent.click(within(form).getByRole("button", { name: /Reset to suggested prompt/i }));
    expect(textarea.value).toMatch(/rustic/i);
  });

  it("iterating shows the parent render as the starting image and can switch back to the site photo", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Not found" }),
    });
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithRender,
    });
    renderAt("/projects/1");

    await userEvent.click(
      await screen.findByRole("button", { name: "Iterate from this Render" }),
    );
    const form = screen.getByRole("form", { name: /Iterate on a render/i });
    expect(within(form).getByText("Iterate on Render #1")).toBeInTheDocument();
    expect(within(form).getByText(/Render 1\.1 \(Design Request #1\)/)).toBeInTheDocument();
    expect(within(form).getByText(/copied from Design Request #1/i)).toBeInTheDocument();
    expect(within(form).getByRole("img", { name: /Render 1\.1/i })).toHaveAttribute(
      "src",
      "/renders/1",
    );
    // Parent's provider and model are pre-selected.
    expect(within(form).getByRole("radio", { name: /Google Gemini Images/i })).toBeChecked();
    const model = within(form).getByRole("combobox", { name: /Image model/i }) as HTMLSelectElement;
    await waitFor(() => expect(model.value).toBe("gemini-3-pro-image"));

    await userEvent.click(
      within(form).getByRole("button", { name: /Start from the site photo instead/i }),
    );
    expect(screen.getByRole("form", { name: /New design request/i })).toBeInTheDocument();
    expect(screen.getByText(/The site photo/i)).toBeInTheDocument();
    expect(screen.queryByText(/Iterate on Render #1/)).not.toBeInTheDocument();
  });
});

describe("ModelPicker — comparison", () => {
  async function openNewForm() {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Not found" }),
    });
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => emptyProject,
    });
    renderAt("/projects/1");
    await userEvent.click(
      await screen.findByRole("button", { name: /New Design Request/i }),
    );
    return screen.getByRole("form", { name: /New design request/i });
  }

  it("shows quality, cost, and badges for the selected model and in the option text", async () => {
    const form = await openNewForm();
    const select = within(form).getByRole("combobox", { name: /Image model/i }) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe("gpt-image-2.5-flare"));

    const flare = within(select).getByRole("option", { name: /^GPT Image 2.5 Flare ·/i });
    expect(flare.textContent).toContain("●●●●○");
    expect(flare.textContent).toContain("$$");
    expect(flare.textContent).toContain("Recommended");

    expect(within(form).getByText("Fast everyday model")).toBeInTheDocument();
    expect(within(form).getByText("~few cents / image")).toBeInTheDocument();
    expect(within(form).getAllByText("Recommended").length).toBeGreaterThan(0);
  });

  it("lists every model, marks snapshots as older, and can hide them", async () => {
    const form = await openNewForm();
    const select = within(form).getByRole("combobox", { name: /Image model/i });
    const snapshot = within(select).getByRole("option", { name: /2026 09 08/ });
    expect(snapshot.textContent).toContain("older / snapshot");
    expect(within(form).getByText(/2 current \+ 1 older/)).toBeInTheDocument();

    await userEvent.click(
      within(form).getByRole("checkbox", { name: /Hide older & snapshot models \(1\)/i }),
    );
    expect(
      within(select).queryByRole("option", { name: /2026 09 08/ }),
    ).not.toBeInTheDocument();
  });

  it("opens a comparison table with Best quality and Cheapest badges and selects from it", async () => {
    const form = await openNewForm();
    await userEvent.click(within(form).getByRole("button", { name: /Compare image models/i }));

    const table = within(form).getByRole("table", { name: /Image model comparison/i });
    const sunburstRow = within(table).getByText("GPT Image 2.5 Sunburst").closest("tr")!;
    expect(within(sunburstRow).getByText("Best quality")).toBeInTheDocument();
    const flareRow = within(table).getByText("GPT Image 2.5 Flare").closest("tr")!;
    expect(within(flareRow).getByText("Cheapest")).toBeInTheDocument();
    expect(within(flareRow).getByRole("button", { name: /GPT Image 2.5 Flare selected/i })).toBeDisabled();

    await userEvent.click(within(sunburstRow).getByRole("button", { name: /Use GPT Image 2.5 Sunburst/i }));
    const select = within(form).getByRole("combobox", { name: /Image model/i }) as HTMLSelectElement;
    expect(select.value).toBe("gpt-image-2.5-sunburst");
  });
});

describe("Hero — new renders and dimension auto-fill", () => {
  const threeRenders = [1, 2, 3].map((n) => ({
    id: n,
    design_request_id: 10,
    image_path: `/${n}.png`,
    image_url: `/renders/${n}`,
    is_chosen: n === 2,
    created_at: "2024-06-01T00:00:00Z",
  }));
  const projectWithThree = {
    ...projectWithRender,
    design_requests: [{ ...projectWithRender.design_requests[0], renders: threeRenders }],
  };

  function mockByUrl(handlers: (url: string, init?: RequestInit) => unknown) {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(async (url: string, init?: RequestInit) => {
      const out = handlers(url, init);
      if (out !== undefined) return out;
      return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
    });
  }

  it("shows a filmstrip of sibling renders under the hero and switches between them", async () => {
    mockByUrl((url) => {
      if (url === "/api/projects/1") return { ok: true, json: async () => projectWithThree };
      return undefined;
    });
    renderAt("/projects/1");

    const strip = await screen.findByRole("navigation", { name: /Renders in this design request/i });
    const thumbs = within(strip).getAllByRole("button");
    expect(thumbs.map((b) => b.getAttribute("aria-label"))).toEqual([
      "View Render 1.1",
      "View Render 1.2 (chosen)",
      "View Render 1.3",
    ]);
    // Default active render is the chosen one.
    expect(thumbs[1]).toHaveAttribute("aria-current", "true");

    await userEvent.click(thumbs[2]);
    await waitFor(() => expect(thumbs[2]).toHaveAttribute("aria-current", "true"));
    expect(screen.getAllByText(/Design Request #1 · Render 3 of 3/).length).toBeGreaterThan(0);
  });

  it("announces freshly generated renders and scrolls to the hero", async () => {
    const created = {
      ...projectWithRender.design_requests[0],
      id: 11,
      renders: threeRenders.map((r) => ({ ...r, id: r.id + 10, design_request_id: 11, is_chosen: false })),
    };
    mockByUrl((url, init) => {
      if (url === "/api/projects/1") return { ok: true, json: async () => emptyProject };
      if (url === "/api/projects/1/design-requests" && init?.method === "POST") {
        return { ok: true, json: async () => created };
      }
      return undefined;
    });
    renderAt("/projects/1");
    await userEvent.click(await screen.findByRole("button", { name: /New Design Request/i }));
    await userEvent.click(screen.getByRole("button", { name: /Generate Renders/i }));

    const banner = await screen.findByRole("status");
    expect(banner).toHaveTextContent(/3 new renders from Design Request #1/);
    expect(banner).toHaveTextContent(/You are viewing 1\.1/);
    expect(screen.getByRole("navigation", { name: /Renders in this design request/i })).toBeInTheDocument();

    await userEvent.click(within(banner).getByRole("button", { name: /Dismiss/i }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("sends the materials preference when auto-filling dimensions and shows failures with a retry", async () => {
    let attempts = 0;
    mockByUrl((url, init) => {
      if (url === "/api/projects/1") return { ok: true, json: async () => projectWithThree };
      if (url === "/api/renders/2/dimension-defaults" && init?.method === "POST") {
        attempts += 1;
        if (attempts === 1) {
          return {
            ok: false,
            status: 400,
            json: async () => ({ detail: "No text-model API key is set (ANTHROPIC_API_KEY, ...)" }),
          };
        }
        return { ok: true, json: async () => ({ patio_width_ft: "14" }) };
      }
      return undefined;
    });
    renderAt("/projects/1");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Couldn't auto-fill dimensions: No text-model API key is set/);

    const firstCall = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      ([url, init]) => url === "/api/renders/2/dimension-defaults" && (init as RequestInit)?.method === "POST",
    );
    expect(JSON.parse((firstCall?.[1] as RequestInit).body as string)).toEqual({
      materials_llm: "claude_sonnet",
      materials_model: "claude-opus-5-5",
    });

    await userEvent.click(within(alert).getByRole("button", { name: /Try again/i }));
    await waitFor(() => {
      expect((screen.getByRole("spinbutton", { name: /Patio Width/i }) as HTMLInputElement).value).toBe("14");
    });
    expect(screen.getByText(/Auto-filled from the render/)).toBeInTheDocument();
    expect(attempts).toBe(2);
  });
});
