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

    const flare = within(select).getByRole("option", { name: /GPT Image 2.5 Flare/i });
    expect(flare.textContent).toContain("●●●●○");
    expect(flare.textContent).toContain("$$");
    expect(flare.textContent).toContain("Recommended");

    expect(within(form).getByText("Fast everyday model")).toBeInTheDocument();
    expect(within(form).getByText("~few cents / image")).toBeInTheDocument();
    expect(within(form).getAllByText("Recommended").length).toBeGreaterThan(0);
  });

  it("hides dated snapshots until 'Show older' is ticked", async () => {
    const form = await openNewForm();
    const select = within(form).getByRole("combobox", { name: /Image model/i });
    expect(
      within(select).queryByRole("option", { name: /2026 09 08/ }),
    ).not.toBeInTheDocument();

    await userEvent.click(
      within(form).getByRole("checkbox", { name: /Show older & snapshot models \(1\)/i }),
    );
    expect(within(select).getByRole("option", { name: /2026 09 08/ })).toBeInTheDocument();
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
