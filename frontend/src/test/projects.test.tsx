import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import ProjectListPage from "../pages/ProjectListPage";
import NewProjectPage from "../pages/NewProjectPage";
import ProjectDetailPage from "../pages/ProjectDetailPage";
import { ThemeProvider } from "../theme/ThemeProvider";

function renderAt(path: string) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<ProjectListPage />} />
          <Route path="/projects/new" element={<NewProjectPage />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/projects/:id/renders/:renderId" element={<ProjectDetailPage />} />
          <Route path="/projects/:id/r/:renderId" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// ProjectListPage — empty state
// ---------------------------------------------------------------------------

describe("ProjectListPage — empty state", () => {
  it("shows empty-state message and New Project button when no projects", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    renderAt("/");

    await waitFor(() => {
      expect(
        screen.getByText(/No projects yet - create one to get started/i),
      ).toBeInTheDocument();
    });

    const newProjectButtons = screen.getAllByRole("button", { name: /New Project/i });
    expect(newProjectButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("shows the API detail string when loading projects fails", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        detail: "FileNotFoundError: [Errno 2] No such file or directory",
      }),
    });

    renderAt("/");

    await waitFor(() => {
      expect(
        screen.getByText(/FileNotFoundError: \[Errno 2\] No such file or directory/i),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/Failed to fetch projects: 500/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ProjectListPage — with projects
// ---------------------------------------------------------------------------

describe("ProjectListPage — with projects", () => {
  it("renders project cards with all history metadata from the API", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          id: 1,
          address: "123 Main St",
          site_photo_url: null,
          site_photo_thumb_url: null,
          created_at: "2024-06-01T00:00:00Z",
          latest_design_request_at: null,
          design_request_count: 0,
          render_count: 0,
          iteration_count: 0,
          has_chosen_render: false,
          has_build_sheet: false,
          latest_quality_tier: null,
        },
        {
          id: 2,
          address: "456 Oak Ave",
          site_photo_url: "/images/2/site_photo.jpg",
          site_photo_thumb_url: "/images/2/thumb.jpg",
          created_at: "2024-06-02T00:00:00Z",
          latest_design_request_at: "2024-06-04T00:00:00Z",
          design_request_count: 3,
          render_count: 9,
          iteration_count: 2,
          has_chosen_render: true,
          has_build_sheet: true,
          latest_quality_tier: "Premium",
        },
      ],
    });

    renderAt("/");

    await waitFor(() => {
      expect(screen.getByText("123 Main St")).toBeInTheDocument();
    });
    expect(screen.getByText("456 Oak Ave")).toBeInTheDocument();
    expect(
      screen.getByText("3 Design Requests · 9 Renders · 2 Iterations"),
    ).toBeInTheDocument();
    expect(screen.getByText("Chosen")).toBeInTheDocument();
    expect(screen.getByText("Build Sheet")).toBeInTheDocument();
    expect(screen.getByText("Premium")).toBeInTheDocument();
    expect(screen.getAllByText("Open")).toHaveLength(2);

    const img = screen.getByRole("img", { name: "456 Oak Ave" });
    expect(img).toHaveAttribute("src", "/images/2/thumb.jpg");
    expect(img).toHaveAttribute("loading", "lazy");
  });

  it("sorts cards by latest design request date, then created date", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          id: 1,
          address: "Created Newer",
          site_photo_url: null,
          site_photo_thumb_url: null,
          created_at: "2024-06-03T00:00:00Z",
          latest_design_request_at: null,
          design_request_count: 0,
          render_count: 0,
          iteration_count: 0,
          has_chosen_render: false,
          has_build_sheet: false,
          latest_quality_tier: null,
        },
        {
          id: 2,
          address: "Recently Active",
          site_photo_url: null,
          site_photo_thumb_url: null,
          created_at: "2024-06-01T00:00:00Z",
          latest_design_request_at: "2024-06-05T00:00:00Z",
          design_request_count: 1,
          render_count: 3,
          iteration_count: 0,
          has_chosen_render: false,
          has_build_sheet: false,
          latest_quality_tier: "Mid-range",
        },
        {
          id: 3,
          address: "Oldest",
          site_photo_url: null,
          site_photo_thumb_url: null,
          created_at: "2024-06-01T00:00:00Z",
          latest_design_request_at: null,
          design_request_count: 0,
          render_count: 0,
          iteration_count: 0,
          has_chosen_render: false,
          has_build_sheet: false,
          latest_quality_tier: null,
        },
      ],
    });

    renderAt("/");

    await waitFor(() => {
      expect(screen.getByText("Recently Active")).toBeInTheDocument();
    });

    const cards = screen.getAllByRole("link", { name: /Open project/i });
    expect(cards.map((card) => card.getAttribute("aria-label"))).toEqual([
      "Open project Recently Active",
      "Open project Created Newer",
      "Open project Oldest",
    ]);
  });

  it("navigates to project detail when a project card is clicked", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            id: 7,
            address: "7 Lucky Lane",
            site_photo_url: null,
            site_photo_thumb_url: null,
            created_at: "2024-06-01T00:00:00Z",
            latest_design_request_at: null,
            design_request_count: 0,
            render_count: 0,
            iteration_count: 0,
            has_chosen_render: false,
            has_build_sheet: false,
            latest_quality_tier: null,
          },
        ],
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 7,
          address: "7 Lucky Lane",
          lot_size_sqft: 4000,
          house_sqft: 1800,
          site_photo_url: null,
          created_at: "2024-06-01T00:00:00Z",
          design_requests: [],
        }),
      });

    renderAt("/");

    await waitFor(() => screen.getByText("7 Lucky Lane"));
    await userEvent.click(screen.getByText("7 Lucky Lane"));

    await waitFor(() => {
      expect(screen.getByText("4,000 sqft")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// NewProjectPage
// ---------------------------------------------------------------------------

describe("NewProjectPage", () => {
  it("renders all required form fields and Save button", () => {
    renderAt("/projects/new");

    expect(screen.getByText(/Site Photo/i)).toBeInTheDocument();
    expect(screen.getByText(/Address/i)).toBeInTheDocument();
    expect(screen.getByText(/Lot Size/i)).toBeInTheDocument();
    expect(screen.getByText(/House Sqft/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Save/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument();
  });

  it("shows error when Save is clicked without selecting a photo", async () => {
    renderAt("/projects/new");

    await userEvent.type(screen.getByPlaceholderText(/123 Main St/i), "999 Test Blvd");
    await userEvent.type(screen.getByPlaceholderText("5000"), "3000");
    await userEvent.type(screen.getByPlaceholderText("2000"), "1500");

    await userEvent.click(screen.getByRole("button", { name: /Save/i }));

    expect(screen.getByText(/Please select a Site Photo/i)).toBeInTheDocument();
  });

  it("calls createProject and navigates to the new project on success", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 42,
          address: "999 Test Blvd",
          created_at: "2024-06-01T00:00:00Z",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 42,
          address: "999 Test Blvd",
          lot_size_sqft: 3000,
          house_sqft: 1500,
          site_photo_url: null,
          created_at: "2024-06-01T00:00:00Z",
          design_requests: [],
        }),
      });

    renderAt("/projects/new");

    const file = new File(["(fake jpeg)"], "yard.jpg", { type: "image/jpeg" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(fileInput, file);

    await userEvent.type(screen.getByPlaceholderText(/123 Main St/i), "999 Test Blvd");
    await userEvent.type(screen.getByPlaceholderText("5000"), "3000");
    await userEvent.type(screen.getByPlaceholderText("2000"), "1500");

    await userEvent.click(screen.getByRole("button", { name: /Save/i }));

    await waitFor(() => {
      expect(screen.getByText("3,000 sqft")).toBeInTheDocument();
    });

    const [, createInit] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const submitted = createInit.body as FormData;
    expect(submitted.get("address")).toBe("999 Test Blvd");
    expect(submitted.get("lot_size")).toBe("3000");
    expect(submitted.has("lot_size_sqft")).toBe(false);
    expect(submitted.get("house_sqft")).toBe("1500");
    expect(submitted.get("site_photo")).toBe(file);
  });

  it("displays the detail string from a structured API error response", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        detail: "ValueError: some cause",
        trace_id: "abc123",
      }),
    });

    renderAt("/projects/new");

    const file = new File(["(fake jpeg)"], "yard.jpg", { type: "image/jpeg" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(fileInput, file);

    await userEvent.type(screen.getByPlaceholderText(/123 Main St/i), "42 Error Ave");
    await userEvent.type(screen.getByPlaceholderText("5000"), "1000");
    await userEvent.type(screen.getByPlaceholderText("2000"), "500");

    await userEvent.click(screen.getByRole("button", { name: /Save/i }));

    await waitFor(() => {
      expect(screen.getByText("ValueError: some cause")).toBeInTheDocument();
    });
    expect(screen.queryByText(/Unexpected error.*check server logs/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Request failed: 500/i)).not.toBeInTheDocument();
  });

  it("displays a non-opaque fallback when project creation error has no JSON body", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => {
        throw new SyntaxError("Unexpected end of JSON input");
      },
    });

    renderAt("/projects/new");

    const file = new File(["(fake jpeg)"], "yard.jpg", { type: "image/jpeg" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(fileInput, file);

    await userEvent.type(screen.getByPlaceholderText(/123 Main St/i), "42 Error Ave");
    await userEvent.type(screen.getByPlaceholderText("5000"), "1000");
    await userEvent.type(screen.getByPlaceholderText("2000"), "500");

    await userEvent.click(screen.getByRole("button", { name: /Save/i }));

    await waitFor(() => {
      expect(screen.getByText(/Request failed \(HTTP 500\)/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Unexpected error.*check server logs/i)).not.toBeInTheDocument();
  });
});
