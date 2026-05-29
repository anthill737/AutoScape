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
          <Route path="/projects/:id/r/:renderId" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

const phaseFixtureProject = {
  id: 42,
  address: "742 Evergreen Terrace",
  lot_size_sqft: 7200,
  house_sqft: 2100,
  site_photo_url: "/images/project-42-site.jpg",
  created_at: "2026-01-01T00:00:00Z",
  design_requests: [
    {
      id: 101,
      project_id: 42,
      parent_render_id: null,
      image_provider: "gpt_image",
      feature_categories: ["Patio"],
      style: "Modern",
      quality_tier: "Budget",
      composed_prompt: "Original patio concept.",
      created_at: "2026-01-02T00:00:00Z",
      renders: [
        {
          id: 1011,
          design_request_id: 101,
          image_path: "/renders/1011.png",
          image_url: "/renders/1011.png",
          is_chosen: false,
          created_at: "2026-01-02T00:00:00Z",
        },
        {
          id: 1012,
          design_request_id: 101,
          image_path: "/renders/1012.png",
          image_url: "/renders/1012.png",
          is_chosen: false,
          created_at: "2026-01-02T00:00:00Z",
        },
        {
          id: 1013,
          design_request_id: 101,
          image_path: "/renders/1013.png",
          image_url: "/renders/1013.png",
          is_chosen: false,
          created_at: "2026-01-02T00:00:00Z",
        },
      ],
    },
    {
      id: 202,
      project_id: 42,
      parent_render_id: 1013,
      image_provider: "gemini_flash_image",
      feature_categories: ["Deck"],
      style: "Rustic",
      quality_tier: "Mid-range",
      composed_prompt: "Iteration adding a cedar deck.",
      created_at: "2026-02-02T00:00:00Z",
      renders: [
        {
          id: 2021,
          design_request_id: 202,
          image_path: "/renders/2021.png",
          image_url: "/renders/2021.png",
          is_chosen: false,
          created_at: "2026-02-02T00:00:00Z",
        },
        {
          id: 2022,
          design_request_id: 202,
          image_path: "/renders/2022.png",
          image_url: "/renders/2022.png",
          is_chosen: true,
          created_at: "2026-02-02T00:00:00Z",
        },
        {
          id: 2023,
          design_request_id: 202,
          image_path: "/renders/2023.png",
          image_url: "/renders/2023.png",
          is_chosen: false,
          created_at: "2026-02-02T00:00:00Z",
        },
      ],
    },
  ],
};

const buildSheetForChosenRender = {
  id: 9001,
  render_id: 2022,
  materials_llm: "claude_sonnet",
  material_items: [],
  tool_list: [],
  build_steps: [],
  total_cost_range: "$1,000-$2,000",
  skill_level: "Intermediate",
  assumptions: [],
  created_at: "2026-02-03T00:00:00Z",
};

function mockPhaseFixtureApi() {
  (fetch as ReturnType<typeof vi.fn>).mockImplementation(async (url: string, init?: RequestInit) => {
    const urlText = String(url);

    if (urlText === "/api/projects/42") {
      return { ok: true, json: async () => phaseFixtureProject };
    }

    if (urlText === "/api/renders/2022/dimension-defaults" && init?.method === "POST") {
      return { ok: true, json: async () => ({}) };
    }

    if (urlText === "/api/renders/2022/build-sheet") {
      return { ok: true, json: async () => buildSheetForChosenRender };
    }

    return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
  });
}

function heroImage() {
  return screen.getByRole("img", { name: /Active render preview/i });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ProjectDetailPage P12 active-state behavior", () => {
  it("renders the project header strip, hero section, and Design Tree from the phase fixture", async () => {
    mockPhaseFixtureApi();

    renderAt("/projects/42");

    const headerStrip = await screen.findByRole("region", {
      name: /Project summary and settings/i,
    });
    expect(headerStrip).toBeInTheDocument();
    expect(within(headerStrip).getByText("742 Evergreen Terrace")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Active render hero/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Design Tree/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /parent: Render 1\.3/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTitle("Build Sheet exists for Render 2.2")).toBeInTheDocument();
    });
  });

  it("clicking a non-active sibling thumbnail moves the active ring and swaps the hero image", async () => {
    mockPhaseFixtureApi();
    renderAt("/projects/42");

    const render2022Link = await screen.findByRole("link", {
      name: /Open Render 2022/i,
    });
    const render2023Link = screen.getByRole("link", {
      name: /Open Render 2023/i,
    });

    expect(heroImage()).toHaveAttribute("src", "/renders/2022.png");
    expect(render2022Link.closest("div")).toHaveAttribute("aria-current", "true");
    expect(render2022Link.closest("div")).toHaveClass("ring-4");

    await userEvent.click(render2023Link);

    expect(heroImage()).toHaveAttribute("src", "/renders/2023.png");
    expect(render2022Link.closest("div")).not.toHaveAttribute("aria-current");
    expect(render2022Link.closest("div")).not.toHaveClass("ring-4");
    expect(render2023Link.closest("div")).toHaveAttribute("aria-current", "true");
    expect(render2023Link.closest("div")).toHaveClass("ring-4");
  });

  it("defaults to the Chosen Render of the most recent Design Request when no renderId is routed", async () => {
    mockPhaseFixtureApi();

    renderAt("/projects/42");

    await waitFor(() => {
      expect(heroImage()).toHaveAttribute("src", "/renders/2022.png");
    });
    expect(
      screen.getByText(
        "Design Request #2 · Render 2 of 3 · iteration of Render #1013",
      ),
    ).toBeInTheDocument();
  });

  it("uses a routed renderId on mount even when that render is older and not chosen", async () => {
    mockPhaseFixtureApi();

    renderAt("/projects/42/r/1012");

    await waitFor(() => {
      expect(heroImage()).toHaveAttribute("src", "/renders/1012.png");
    });
    expect(
      screen.getByText("Design Request #1 · Render 2 of 3"),
    ).toBeInTheDocument();
  });

  it("opens the New Design Request form with parent_render_id set to the active render", async () => {
    mockPhaseFixtureApi();

    renderAt("/projects/42/r/1012");

    const hero = await screen.findByRole("region", { name: /Active render hero/i });
    await userEvent.click(
      within(hero).getByRole("button", { name: "Iterate from this Render" }),
    );

    expect(await screen.findByText("Iterate on Render #1012")).toBeInTheDocument();
    expect(document.querySelector('input[name="parent_render_id"]')).toHaveAttribute(
      "value",
      "1012",
    );
  });
});
