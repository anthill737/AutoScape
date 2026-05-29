import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
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

const baseProject = {
  id: 1,
  address: "123 Main St",
  lot_size_sqft: 5000,
  house_sqft: 2000,
  site_photo_url: null,
  created_at: "2024-06-01T00:00:00Z",
  design_requests: [],
};

// 404 stub for getBuildSheet when no build sheet exists yet
const noBuiltSheet404 = { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// New Design Request button
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — New Design Request button", () => {
  it("shows 'New Design Request' button after project loads", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => baseProject,
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /New Design Request/i }),
      ).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Design Request form controls
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — Design Request form controls", () => {
  async function openForm() {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => baseProject,
    });
    renderAt("/projects/1");
    await waitFor(() =>
      screen.getByRole("button", { name: /New Design Request/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /New Design Request/i }),
    );
  }

  it("shows Image Provider radio buttons", async () => {
    await openForm();
    expect(
      screen.getByRole("radio", { name: /Gemini 3 Pro Image/i }),
    ).toBeInTheDocument();
    const gptImage = screen.getByRole("radio", { name: /GptImage/i });
    expect(gptImage).toBeInTheDocument();
    expect(gptImage).toBeChecked();
  });

  it("shows all 7 Feature Category checkboxes", async () => {
    await openForm();
    const cats = [
      "Deck",
      "Patio",
      "Garden Beds",
      "Fire Feature",
      "Pergola",
      "Pool",
      "Full Redesign",
    ];
    for (const cat of cats) {
      expect(
        screen.getByRole("checkbox", { name: new RegExp(cat, "i") }),
      ).toBeInTheDocument();
    }
  });

  it("shows all 6 Style radio buttons", async () => {
    await openForm();
    const styles = [
      "Modern",
      "Traditional",
      "Cottage",
      "Xeriscape",
      "Tropical",
      "Rustic",
    ];
    for (const s of styles) {
      expect(
        screen.getByRole("radio", { name: new RegExp(s, "i") }),
      ).toBeInTheDocument();
    }
  });

  it("shows Quality Tier radio buttons for Budget, Mid-range, Premium", async () => {
    await openForm();
    expect(
      screen.getByRole("radio", { name: /Budget/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /Mid-range/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /Premium/i }),
    ).toBeInTheDocument();
  });

  it("shows an editable Composed Prompt textarea seeded from selections", async () => {
    await openForm();

    const textarea = screen.getByRole("textbox");
    expect(textarea).toBeInTheDocument();
    // Default seed: Budget + Modern
    expect((textarea as HTMLTextAreaElement).value).toMatch(/budget/i);
    expect((textarea as HTMLTextAreaElement).value).toMatch(/modern/i);
    expect((textarea as HTMLTextAreaElement).value).toMatch(/photorealistic/i);
    expect((textarea as HTMLTextAreaElement).value).toMatch(/no labels or text/i);
  });

  it("re-seeds Composed Prompt when a Feature Category is checked", async () => {
    await openForm();

    await userEvent.click(screen.getByRole("checkbox", { name: /Deck/i }));

    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).value).toContain("Deck");
  });
});

// ---------------------------------------------------------------------------
// Submitting the form
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — submitting Design Request form", () => {
  const mockRenders = [
    {
      id: 1,
      design_request_id: 10,
      image_path: "/a.png",
      image_url: "/renders/1",
      is_chosen: false,
      created_at: "2024-06-01T00:00:00Z",
    },
    {
      id: 2,
      design_request_id: 10,
      image_path: "/b.png",
      image_url: "/renders/2",
      is_chosen: false,
      created_at: "2024-06-01T00:00:00Z",
    },
    {
      id: 3,
      design_request_id: 10,
      image_path: "/c.png",
      image_url: "/renders/3",
      is_chosen: false,
      created_at: "2024-06-01T00:00:00Z",
    },
  ];

  it("shows loading state while submitting then renders 3 images", async () => {
    let resolveDr!: (v: unknown) => void;
    const drPromise = new Promise((res) => {
      resolveDr = res;
    });

    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => baseProject,
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => drPromise,
      } as unknown as Promise<Response>);

    renderAt("/projects/1");

    await waitFor(() =>
      screen.getByRole("button", { name: /New Design Request/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /New Design Request/i }),
    );

    await userEvent.click(screen.getByRole("button", { name: /Generate Renders/i }));

    // Loading state visible
    expect(screen.getByRole("button", { name: /Generating/i })).toBeInTheDocument();

    // Resolve the design request response
    resolveDr({
      id: 10,
      project_id: 1,
      parent_render_id: null,
      image_provider: "GeminiFlashImage",
      feature_categories: [],
      style: "Modern",
      quality_tier: "Budget",
      composed_prompt: "Design a budget modern outdoor space featuring landscaping.",
      created_at: "2024-06-01T00:00:00Z",
      renders: mockRenders,
    });

    // After response: 3 render images appear
    await waitFor(() => {
      expect(screen.getAllByRole("img", { name: /Render \d+/i })).toHaveLength(3);
    });

    // Form is closed
    expect(
      screen.queryByRole("button", { name: /Generate Renders/i }),
    ).not.toBeInTheDocument();
  });

  it("surfaces API key missing detail message on 400 error", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => baseProject,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({
          detail: "GEMINI_API_KEY is not configured. Set it in .env.local.",
        }),
      });

    renderAt("/projects/1");

    await waitFor(() =>
      screen.getByRole("button", { name: /New Design Request/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /New Design Request/i }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Generate Renders/i }),
    );

    await waitFor(() => {
      expect(
        screen.getByText(/GEMINI_API_KEY is not configured/i),
      ).toBeInTheDocument();
    });
  });

  it("shows a danger warning banner with the exact detail message on 429", async () => {
    const detail =
      "Gemini quota exceeded for model gemini-3-pro-image-preview. Enable billing at " +
      "https://aistudio.google.com/app/apikey or switch the Image Provider dropdown " +
      "to GptImage for this request.";
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => baseProject,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => ({ detail }),
      });

    renderAt("/projects/1");

    await waitFor(() =>
      screen.getByRole("button", { name: /New Design Request/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /New Design Request/i }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Generate Renders/i }),
    );

    await waitFor(() => {
      const warning = screen.getByText(detail);
      expect(warning).toBeInTheDocument();
      expect(warning).toHaveClass("border-danger", "bg-surface-elevated", "text-danger");
    });
  });

  it("shows a red inline auth detail message on 401", async () => {
    const detail = "Authentication failed: missing Authorization header.";
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => baseProject,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail }),
      });

    renderAt("/projects/1");

    await waitFor(() =>
      screen.getByRole("button", { name: /New Design Request/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /New Design Request/i }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Generate Renders/i }),
    );

    await waitFor(() => {
      const error = screen.getByText(detail);
      expect(error).toBeInTheDocument();
      expect(error).toHaveClass("text-danger");
    });
  });

  it("shows the API detail string when design request generation fails with 500", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => baseProject,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({
          detail: "ValueError: some cause",
          trace_id: "abc123",
        }),
      });

    renderAt("/projects/1");

    await waitFor(() =>
      screen.getByRole("button", { name: /New Design Request/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /New Design Request/i }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Generate Renders/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/ValueError: some cause/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Unexpected error.*check server logs/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Request failed: 500/i)).not.toBeInTheDocument();
  });

  it("shows a non-opaque fallback when design request error has no detail field", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => baseProject,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ trace_id: "abc123" }),
      });

    renderAt("/projects/1");

    await waitFor(() =>
      screen.getByRole("button", { name: /New Design Request/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /New Design Request/i }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Generate Renders/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/Request failed \(HTTP 500\)/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Unexpected error.*check server logs/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Render gallery — Choose button
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — Render gallery Choose button", () => {
  const projectWithRenders = {
    ...baseProject,
    design_requests: [
      {
        id: 10,
        project_id: 1,
        parent_render_id: null,
        image_provider: "GeminiFlashImage",
        feature_categories: ["Patio"],
        style: "Modern",
        quality_tier: "Budget",
        composed_prompt: "...",
        created_at: "2024-06-01T00:00:00Z",
        renders: [
          {
            id: 1,
            design_request_id: 10,
            image_path: "/a.png",
            image_url: "/renders/1",
            is_chosen: false,
            created_at: "2024-06-01T00:00:00Z",
          },
          {
            id: 2,
            design_request_id: 10,
            image_path: "/b.png",
            image_url: "/renders/2",
            is_chosen: false,
            created_at: "2024-06-01T00:00:00Z",
          },
          {
            id: 3,
            design_request_id: 10,
            image_path: "/c.png",
            image_url: "/renders/3",
            is_chosen: false,
            created_at: "2024-06-01T00:00:00Z",
          },
        ],
      },
    ],
  };

  it("shows 3 render links and an enabled hero Choose action when no render is chosen", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithRenders,
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getAllByRole("link", { name: /Open Render \d+/i })).toHaveLength(3);
    });
    expect(screen.getByRole("button", { name: "Choose this Render" })).not.toBeDisabled();
  });

  it("clicking the hero Choose action calls PATCH endpoint and marks render as chosen", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(async (url: string, init?: RequestInit) => {
      const urlText = String(url);
      if (urlText === "/api/projects/1") {
        return {
          ok: true,
          json: async () => projectWithRenders,
        };
      }
      if (urlText.endsWith("/dimension-defaults")) {
        return { ok: true, json: async () => ({}) };
      }
      if (urlText.endsWith("/build-sheet")) {
        return noBuiltSheet404;
      }
      if (urlText === "/api/renders/1/choose" && init?.method === "PATCH") {
        return {
          ok: true,
          json: async () => ({
            id: 1,
            design_request_id: 10,
            image_path: "/a.png",
            image_url: "/renders/1",
            is_chosen: true,
            created_at: "2024-06-01T00:00:00Z",
          }),
        };
      }
      return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
    });

    renderAt("/projects/1");

    const chooseButton = await screen.findByRole("button", { name: "Choose this Render" });
    await userEvent.click(chooseButton);

    await waitFor(() => {
      const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
      const patchCall = calls.find(
        (c: unknown[]) =>
          typeof c[0] === "string" &&
          c[0].includes("/renders/1/choose") &&
          (c[1] as RequestInit)?.method === "PATCH",
      );
      expect(patchCall).toBeDefined();
    });

    await waitFor(() => {
      expect(screen.getByText("Chosen")).toBeInTheDocument();
      expect(chooseButton).toBeDisabled();
    });
  });

  it("chosen render card has a distinct chosen border (is_chosen=true from initial load)", async () => {
    const projectChosen = {
      ...baseProject,
      design_requests: [
        {
          ...projectWithRenders.design_requests[0],
          renders: [
            { ...projectWithRenders.design_requests[0].renders[0], is_chosen: true },
            { ...projectWithRenders.design_requests[0].renders[1] },
            { ...projectWithRenders.design_requests[0].renders[2] },
          ],
        },
      ],
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectChosen,
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getByText("Chosen")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Choose this Render" })).toBeDisabled();
    expect(screen.getByRole("link", { name: /Open Render 1/i }).closest("div")).toHaveClass(
      "border-accent",
    );
  });
});

// ---------------------------------------------------------------------------
// Iteration flow
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — iteration flow", () => {
  const chosenRender = {
    id: 1,
    design_request_id: 10,
    image_path: "/a.png",
    image_url: "/renders/1",
    is_chosen: true,
    created_at: "2024-06-01T00:00:00Z",
  };

  const parentDr = {
    id: 10,
    project_id: 1,
    parent_render_id: null,
    image_provider: "GeminiFlashImage",
    feature_categories: ["Patio", "Deck"],
    style: "Modern",
    quality_tier: "Mid-range",
    composed_prompt:
      "Design a mid-range modern outdoor space featuring Patio, Deck.",
    created_at: "2024-06-01T00:00:00Z",
    renders: [
      chosenRender,
      {
        id: 2,
        design_request_id: 10,
        image_path: "/b.png",
        image_url: "/renders/2",
        is_chosen: false,
        created_at: "2024-06-01T00:00:00Z",
      },
      {
        id: 3,
        design_request_id: 10,
        image_path: "/c.png",
        image_url: "/renders/3",
        is_chosen: false,
        created_at: "2024-06-01T00:00:00Z",
      },
    ],
  };

  const projectWithChosenRender = {
    ...baseProject,
    design_requests: [parentDr],
  };

  it("shows Iterate button on the chosen render", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithChosenRender,
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /^Iterate from this Render$/i }),
      ).toBeInTheDocument();
    });
  });

  it("clicking Iterate opens form with prior composed prompt pre-filled", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithChosenRender,
    });

    renderAt("/projects/1");

    await waitFor(() =>
      screen.getByRole("button", { name: /^Iterate from this Render$/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /^Iterate from this Render$/i }),
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Generate Renders/i }),
      ).toBeInTheDocument();
    });

    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).value).toContain("mid-range");
    expect((textarea as HTMLTextAreaElement).value).toContain("Patio");
  });

  it("clicking Iterate shows the form title referencing the parent render", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithChosenRender,
    });

    renderAt("/projects/1");

    await waitFor(() =>
      screen.getByRole("button", { name: /^Iterate from this Render$/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /^Iterate from this Render$/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/Iterate on Render #1/i)).toBeInTheDocument();
    });
  });

  it("submitting iteration form sends parent_render_id in POST body", async () => {
    let capturedBody: Record<string, unknown> | null = null;

    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => projectWithChosenRender,
      })
      // dimension-defaults is called for the pre-existing chosen render on mount
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      })
      // build-sheet GET returns 404 (no existing build sheet)
      .mockResolvedValueOnce(noBuiltSheet404)
      .mockImplementationOnce(async (_url: string, init?: RequestInit) => {
        capturedBody = JSON.parse(init?.body as string) as Record<
          string,
          unknown
        >;
        return {
          ok: true,
          json: async () => ({
            id: 20,
            project_id: 1,
            parent_render_id: 1,
            image_provider: "GeminiFlashImage",
            feature_categories: ["Patio", "Deck"],
            style: "Modern",
            quality_tier: "Mid-range",
            composed_prompt: parentDr.composed_prompt,
            created_at: "2024-06-02T00:00:00Z",
            renders: [],
          }),
        };
      });

    renderAt("/projects/1");

    await waitFor(() =>
      screen.getByRole("button", { name: /^Iterate from this Render$/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /^Iterate from this Render$/i }),
    );

    await waitFor(() =>
      screen.getByRole("button", { name: /Generate Renders/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Generate Renders/i }),
    );

    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
      expect(capturedBody!.parent_render_id).toBe(1);
    });
  });
});

// ---------------------------------------------------------------------------
// Design Tree display
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — Design Tree", () => {
  const render1 = {
    id: 1,
    design_request_id: 10,
    image_path: "/a.png",
    image_url: "/renders/1",
    is_chosen: true,
    created_at: "2024-06-01T00:00:00Z",
  };

  const dr1 = {
    id: 10,
    project_id: 1,
    parent_render_id: null,
    image_provider: "GeminiFlashImage",
    feature_categories: ["Patio"],
    style: "Modern",
    quality_tier: "Budget",
    composed_prompt: "Design a budget modern outdoor space featuring Patio.",
    created_at: "2024-06-01T00:00:00Z",
    renders: [
      render1,
      {
        id: 2,
        design_request_id: 10,
        image_path: "/b.png",
        image_url: "/renders/2",
        is_chosen: false,
        created_at: "2024-06-01T00:00:00Z",
      },
      {
        id: 3,
        design_request_id: 10,
        image_path: "/c.png",
        image_url: "/renders/3",
        is_chosen: false,
        created_at: "2024-06-01T00:00:00Z",
      },
    ],
  };

  const dr2 = {
    id: 20,
    project_id: 1,
    parent_render_id: 1, // child of dr1 via render1
    image_provider: "GeminiFlashImage",
    feature_categories: ["Deck"],
    style: "Rustic",
    quality_tier: "Mid-range",
    composed_prompt: "Iterate: add a cedar deck.",
    created_at: "2024-06-02T00:00:00Z",
    renders: [
      {
        id: 4,
        design_request_id: 20,
        image_path: "/d.png",
        image_url: "/renders/4",
        is_chosen: false,
        created_at: "2024-06-02T00:00:00Z",
      },
      {
        id: 5,
        design_request_id: 20,
        image_path: "/e.png",
        image_url: "/renders/5",
        is_chosen: false,
        created_at: "2024-06-02T00:00:00Z",
      },
      {
        id: 6,
        design_request_id: 20,
        image_path: "/f.png",
        image_url: "/renders/6",
        is_chosen: false,
        created_at: "2024-06-02T00:00:00Z",
      },
    ],
  };

  it("renders the active request thumbnails and collapsed sibling previews", async () => {
    // dr2 is listed before dr1 because it is newer.
    const projectWithTree = {
      ...baseProject,
      design_requests: [dr2, dr1],
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithTree,
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(
        screen.getAllByRole("img", { name: /Render \d+|Design Request \d+ preview/i }),
      ).toHaveLength(4);
    });
  });

  it("lists Design Request cards newest first while keeping chronological request numbers", async () => {
    const projectWithTree = {
      ...baseProject,
      design_requests: [dr1, dr2],
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithTree,
    });

    renderAt("/projects/1");

    const newestHeading = await screen.findByRole("heading", {
      name: "Design Request #2",
    });
    const olderHeading = screen.getByRole("heading", {
      name: "Design Request #1",
    });

    expect(
      newestHeading.compareDocumentPosition(olderHeading) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getByText("Submitted 2024-06-02 00:00 UTC")).toBeInTheDocument();
  });

  it("shows iteration indicator for child Design Request", async () => {
    const projectWithTree = {
      ...baseProject,
      design_requests: [dr1, dr2],
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithTree,
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /parent: Render 1\.1/i }),
      ).toBeInTheDocument();
    });
  });

  it("clicking an iteration parent link makes the parent Render active in the hero", async () => {
    const projectWithTree = {
      ...baseProject,
      design_requests: [dr1, dr2],
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithTree,
    });

    renderAt("/projects/1");

    await userEvent.click(
      await screen.findByRole("button", { name: /parent: Render 1\.1/i }),
    );

    await waitFor(() => {
      expect(
        screen.getByRole("region", { name: /Active render hero/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Design Request #1 · Render 1 of 3/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /Open Render 1/i }).closest("div")).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  it("shows labeled metadata for each Design Request node", async () => {
    const projectWithTree = {
      ...baseProject,
      design_requests: [dr1],
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithTree,
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getByText("Style")).toBeInTheDocument();
      expect(screen.getByText("Feature Categories")).toBeInTheDocument();
      expect(screen.getByText("Quality Tier")).toBeInTheDocument();
      expect(screen.getByText("Image Provider")).toBeInTheDocument();
    });
    expect(screen.getByText("Modern")).toBeInTheDocument();
    expect(screen.getByText("Patio")).toBeInTheDocument();
    expect(screen.getByText("Budget")).toBeInTheDocument();
    expect(screen.getByText("GeminiFlashImage")).toBeInTheDocument();
  });

  it("links non-chosen Render thumbnails to their Render views", async () => {
    const projectWithTree = {
      ...baseProject,
      design_requests: [dr1],
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithTree,
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /Open Render 2/i })).toHaveAttribute(
        "href",
        "/projects/1/renders/2",
      );
    });
  });

  it("shows exactly one active-state ring across Design Tree thumbnails", async () => {
    const projectWithTree = {
      ...baseProject,
      design_requests: [dr1, dr2],
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithTree,
    });

    renderAt("/projects/1");

    const designTree = await screen.findByRole("region", { name: /Design Tree/i });

    await waitFor(() => {
      expect(designTree.getElementsByClassName("ring-4")).toHaveLength(1);
    });

    await userEvent.click(screen.getByRole("button", { name: /Design Request #1/i }));
    await userEvent.click(screen.getByRole("link", { name: /Open Render 2/i }));

    await waitFor(() => {
      expect(designTree.getElementsByClassName("ring-4")).toHaveLength(1);
      expect(screen.getByRole("link", { name: /Open Render 2/i }).closest("div")).toHaveAttribute(
        "aria-current",
        "true",
      );
    });
  });

  it("does not show a Build Sheet indicator on the chosen thumbnail when none exists", async () => {
    const projectWithTree = {
      ...baseProject,
      design_requests: [dr1],
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => projectWithTree,
    });

    renderAt("/projects/1");

    await screen.findByRole("link", { name: /Open Render 1/i });
    expect(screen.queryByTitle("Build Sheet exists for Render 1.1")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Active Render route state
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — activeRenderId route state", () => {
  const olderDr = {
    id: 10,
    project_id: 1,
    parent_render_id: null,
    image_provider: "GeminiFlashImage",
    feature_categories: ["Patio"],
    style: "Modern",
    quality_tier: "Budget",
    composed_prompt: "...",
    created_at: "2024-06-01T00:00:00Z",
    renders: [
      {
        id: 1,
        design_request_id: 10,
        image_path: "/a.png",
        image_url: "/renders/1",
        is_chosen: false,
        created_at: "2024-06-01T00:00:00Z",
      },
      {
        id: 2,
        design_request_id: 10,
        image_path: "/b.png",
        image_url: "/renders/2",
        is_chosen: true,
        created_at: "2024-06-01T00:00:00Z",
      },
      {
        id: 3,
        design_request_id: 10,
        image_path: "/c.png",
        image_url: "/renders/3",
        is_chosen: false,
        created_at: "2024-06-01T00:00:00Z",
      },
    ],
  };

  const newerDr = {
    id: 20,
    project_id: 1,
    parent_render_id: null,
    image_provider: "GeminiFlashImage",
    feature_categories: ["Deck"],
    style: "Rustic",
    quality_tier: "Mid-range",
    composed_prompt: "...",
    created_at: "2024-06-02T00:00:00Z",
    renders: [
      {
        id: 4,
        design_request_id: 20,
        image_path: "/d.png",
        image_url: "/renders/4",
        is_chosen: false,
        created_at: "2024-06-02T00:00:00Z",
      },
      {
        id: 5,
        design_request_id: 20,
        image_path: "/e.png",
        image_url: "/renders/5",
        is_chosen: true,
        created_at: "2024-06-02T00:00:00Z",
      },
      {
        id: 6,
        design_request_id: 20,
        image_path: "/f.png",
        image_url: "/renders/6",
        is_chosen: false,
        created_at: "2024-06-02T00:00:00Z",
      },
    ],
  };

  function expectRenderActive(renderId: number) {
    const link = screen.getByRole("link", { name: new RegExp(`Open Render ${renderId}`, "i") });
    expect(link.closest("div")).toHaveAttribute("aria-current", "true");
  }

  it("defaults to the Chosen Render of the most recent Design Request", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...baseProject,
        design_requests: [olderDr, newerDr],
      }),
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expectRenderActive(5);
    });
  });

  it("defaults to the first Render of the most recent Design Request when none is chosen", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...baseProject,
        design_requests: [
          olderDr,
          {
            ...newerDr,
            renders: newerDr.renders.map((render) => ({ ...render, is_chosen: false })),
          },
        ],
      }),
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expectRenderActive(4);
    });
  });

  it("uses the :renderId route param on mount instead of the default", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...baseProject,
        design_requests: [olderDr, newerDr],
      }),
    });

    renderAt("/projects/1/r/2");

    await waitFor(() => {
      expectRenderActive(2);
    });
  });

  it("activates a different Render thumbnail", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...baseProject,
        design_requests: [olderDr, newerDr],
      }),
    });

    renderAt("/projects/1");

    const render4Link = await screen.findByRole("link", { name: /Open Render 4/i });
    await userEvent.click(render4Link);

    await waitFor(() => {
      expectRenderActive(4);
    });
  });
});

// ---------------------------------------------------------------------------
// Hero section
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — Hero section", () => {
  const olderDr = {
    id: 10,
    project_id: 1,
    parent_render_id: null,
    image_provider: "gpt_image",
    feature_categories: ["Patio"],
    style: "Modern",
    quality_tier: "Budget",
    composed_prompt: "...",
    created_at: "2024-06-01T00:00:00Z",
    renders: [
      {
        id: 1,
        design_request_id: 10,
        image_path: "/a.png",
        image_url: "/renders/1",
        is_chosen: false,
        created_at: "2024-06-01T00:00:00Z",
      },
      {
        id: 2,
        design_request_id: 10,
        image_path: "/b.png",
        image_url: "/renders/2",
        is_chosen: true,
        created_at: "2024-06-01T00:00:00Z",
      },
      {
        id: 3,
        design_request_id: 10,
        image_path: "/c.png",
        image_url: "/renders/3",
        is_chosen: false,
        created_at: "2024-06-01T00:00:00Z",
      },
    ],
  };

  const newerDr = {
    id: 20,
    project_id: 1,
    parent_render_id: null,
    image_provider: "gemini_flash_image",
    feature_categories: ["Deck"],
    style: "Rustic",
    quality_tier: "Mid-range",
    composed_prompt: "...",
    created_at: "2024-06-02T00:00:00Z",
    renders: [
      {
        id: 4,
        design_request_id: 20,
        image_path: "/d.png",
        image_url: "/renders/4",
        is_chosen: false,
        created_at: "2024-06-02T00:00:00Z",
      },
      {
        id: 5,
        design_request_id: 20,
        image_path: "/e.png",
        image_url: "/renders/5",
        is_chosen: true,
        created_at: "2024-06-02T00:00:00Z",
      },
      {
        id: 6,
        design_request_id: 20,
        image_path: "/f.png",
        image_url: "/renders/6",
        is_chosen: false,
        created_at: "2024-06-02T00:00:00Z",
      },
    ],
  };

  function mockHeroProject() {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...baseProject,
        design_requests: [olderDr, newerDr],
      }),
    });
  }

  function mockHeroProjectApi(options?: {
    chooseRenderId?: number;
    buildSheetForRenderId?: number;
  }) {
    const project = {
      ...baseProject,
      design_requests: [olderDr, newerDr],
    };

    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      async (url: string, init?: RequestInit) => {
        const urlText = String(url);
        if (urlText === "/api/projects/1") {
          return { ok: true, json: async () => project };
        }
        if (urlText.endsWith("/dimension-defaults")) {
          return { ok: true, json: async () => ({}) };
        }
        if (urlText.endsWith("/build-sheet")) {
          const renderId = Number(urlText.match(/\/renders\/(\d+)\/build-sheet/)?.[1]);
          if (renderId === options?.buildSheetForRenderId) {
            return {
              ok: true,
              json: async () => ({
                id: 900,
                render_id: renderId,
                materials_llm: "claude_sonnet",
                material_items: [],
                tool_list: [],
                build_steps: [],
                total_cost_range: "$0",
                skill_level: "Beginner",
                assumptions: [],
                created_at: "2024-06-03T00:00:00Z",
              }),
            };
          }
          return noBuiltSheet404;
        }
        if (
          init?.method === "PATCH" &&
          options?.chooseRenderId != null &&
          urlText === `/api/renders/${options.chooseRenderId}/choose`
        ) {
          const render = [...olderDr.renders, ...newerDr.renders].find(
            (candidate) => candidate.id === options.chooseRenderId,
          );
          return {
            ok: true,
            json: async () => ({ ...render, is_chosen: true }),
          };
        }
        return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
      },
    );
  }

  it("renders the active render at hero scale with identity label and Chosen pill", async () => {
    mockHeroProject();

    renderAt("/projects/1");

    expect(
      await screen.findByRole("region", { name: /Active render hero/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Design Request #2 · Render 2 of 3 · Rustic · Mid-range · Deck · Gemini 3 Pro Image",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Chosen")).toBeInTheDocument();

    const heroImage = screen.getByRole("img", { name: /Active render preview/i });
    expect(heroImage).toHaveAttribute("src", "/renders/5");
    expect(heroImage).toHaveClass("object-contain");
  });

  it("clicking a sibling thumbnail swaps the hero, active thumbnail, and Chosen pill", async () => {
    mockHeroProject();

    renderAt("/projects/1");

    const render6Link = await screen.findByRole("link", { name: /Open Render 6/i });
    await userEvent.click(render6Link);

    expect(
      screen.getByText(
        "Design Request #2 · Render 3 of 3 · Rustic · Mid-range · Deck · Gemini 3 Pro Image",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Chosen")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Active render preview/i })).toHaveAttribute(
      "src",
      "/renders/6",
    );
    expect(render6Link.closest("div")).toHaveAttribute("aria-current", "true");
  });

  it("shows and clears the hero loading skeleton without changing the image box", async () => {
    mockHeroProject();

    renderAt("/projects/1");

    expect(await screen.findByLabelText("Loading active render")).toBeInTheDocument();
    const heroImage = screen.getByRole("img", { name: /Active render preview/i });
    expect(heroImage.closest(".h-\\[62vh\\]")).toBeTruthy();

    fireEvent.load(heroImage);

    await waitFor(() => {
      expect(screen.queryByLabelText("Loading active render")).not.toBeInTheDocument();
    });
    expect(heroImage.closest(".h-\\[62vh\\]")).toBeTruthy();
  });

  it("renders reachable hero actions with chosen-state availability", async () => {
    mockHeroProjectApi();

    renderAt("/projects/1");

    const hero = await screen.findByRole("region", { name: /Active render hero/i });
    expect(
      within(hero).getByRole("button", { name: "Choose this Render" }),
    ).toBeDisabled();
    expect(
      within(hero).getByRole("button", { name: "Iterate from this Render" }),
    ).toBeInTheDocument();
    expect(within(hero).getByRole("link", { name: "Build Sheet" })).toHaveAttribute(
      "href",
      "#dimensions-render-5",
    );
    expect(within(hero).getByRole("link", { name: "Download image" })).toHaveAttribute(
      "download",
    );
  });

  it("chooses the active non-chosen render from the hero and disables the action", async () => {
    mockHeroProjectApi({ chooseRenderId: 6 });

    renderAt("/projects/1/r/6");

    const hero = await screen.findByRole("region", { name: /Active render hero/i });
    const chooseButton = within(hero).getByRole("button", { name: "Choose this Render" });
    expect(chooseButton).not.toBeDisabled();
    expect(within(hero).queryByRole("link", { name: "Build Sheet" })).not.toBeInTheDocument();

    await userEvent.click(chooseButton);

    await waitFor(() => {
      expect(chooseButton).toBeDisabled();
      expect(within(hero).getByText("Chosen")).toBeInTheDocument();
      expect(
        within(hero).getByRole("link", { name: "Build Sheet" }),
      ).toHaveAttribute("href", "#dimensions-render-6");
    });
  });

  it("deep-links the hero Build Sheet action to an existing Build Sheet", async () => {
    mockHeroProjectApi({ buildSheetForRenderId: 5 });

    renderAt("/projects/1");

    const hero = await screen.findByRole("region", { name: /Active render hero/i });
    await waitFor(() => {
      expect(
        within(hero).getByRole("link", { name: "Build Sheet" }),
      ).toHaveAttribute("href", "#build-sheet-render-5");
    });
  });

  it("opens the design request form from the hero with parent_render_id populated", async () => {
    mockHeroProjectApi();

    renderAt("/projects/1");

    await userEvent.click(
      await screen.findByRole("button", { name: "Iterate from this Render" }),
    );

    expect(await screen.findByText("Iterate on Render #5")).toBeInTheDocument();
    expect(document.querySelector('input[name="parent_render_id"]')).toHaveAttribute(
      "value",
      "5",
    );
  });
});

// ---------------------------------------------------------------------------
// Project Dimensions section
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — Project Dimensions section", () => {
  const deckRender = {
    id: 1,
    design_request_id: 10,
    image_path: "/a.png",
    image_url: "/renders/1",
    is_chosen: true,
    created_at: "2024-06-01T00:00:00Z",
  };

  const projectWithDeckChosen = {
    ...baseProject,
    design_requests: [
      {
        id: 10,
        project_id: 1,
        parent_render_id: null,
        image_provider: "GeminiFlashImage",
        feature_categories: ["Deck"],
        style: "Modern",
        quality_tier: "Budget",
        composed_prompt: "...",
        created_at: "2024-06-01T00:00:00Z",
        renders: [
          deckRender,
          {
            id: 2,
            design_request_id: 10,
            image_path: "/b.png",
            image_url: "/renders/2",
            is_chosen: false,
            created_at: "2024-06-01T00:00:00Z",
          },
          {
            id: 3,
            design_request_id: 10,
            image_path: "/c.png",
            image_url: "/renders/3",
            is_chosen: false,
            created_at: "2024-06-01T00:00:00Z",
          },
        ],
      },
    ],
  };

  const deckDefaults = { deck_width_ft: "12", deck_length_ft: "16", deck_height_ft: "3" };

  it("shows 'Project Dimensions' heading when a render is chosen on load", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getByText("Project Dimensions")).toBeInTheDocument();
    });
  });

  it("pre-fills dimension fields with values from dimension-defaults endpoint", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(
        screen.getByRole("spinbutton", { name: /Deck Width/i }),
      ).toHaveValue(12);
      expect(
        screen.getByRole("spinbutton", { name: /Deck Length/i }),
      ).toHaveValue(16);
      expect(
        screen.getByRole("spinbutton", { name: /Deck Height/i }),
      ).toHaveValue(3);
    });
  });

  it("dimension fields are editable after pre-fill", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults });

    renderAt("/projects/1");

    const widthInput = await screen.findByRole("spinbutton", { name: /Deck Width/i });
    await userEvent.clear(widthInput);
    await userEvent.type(widthInput, "20");

    expect(widthInput).toHaveValue(20);
  });

  it("shows Materials LLM picker with Claude Sonnet 4.6 selected by default", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getByText("Project Dimensions")).toBeInTheDocument();
    });

    expect(screen.getByRole("radio", { name: /Claude Sonnet 4\.6/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /GPT-5/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Gemini 2\.5 Pro/i })).toBeInTheDocument();
  });

  it("Generate Build Sheet button is disabled when dimension fields are empty", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) }); // empty defaults

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getByText("Project Dimensions")).toBeInTheDocument();
    });

    expect(
      screen.getByRole("button", { name: /Generate Build Sheet/i }),
    ).toBeDisabled();
  });

  it("Generate Build Sheet button is enabled when all fields have values", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Generate Build Sheet/i }),
      ).not.toBeDisabled();
    });
  });

  it("shows loading state while generating and calls POST build-sheet", async () => {
    let resolveBS!: (v: unknown) => void;
    const bsPromise = new Promise((res) => {
      resolveBS = res;
    });

    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults })
      // build-sheet GET: 404 (no existing build sheet)
      .mockResolvedValueOnce(noBuiltSheet404)
      .mockReturnValueOnce({
        ok: true,
        json: () => bsPromise,
      } as unknown as Promise<Response>);

    renderAt("/projects/1");

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Generate Build Sheet/i }),
      ).not.toBeDisabled();
    });

    await userEvent.click(
      screen.getByRole("button", { name: /Generate Build Sheet/i }),
    );

    // Loading state
    expect(
      screen.getByRole("button", { name: /Generating Build Sheet/i }),
    ).toBeDisabled();

    // Verify build-sheet POST was called
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
    const postCall = calls.find(
      (c: unknown[]) =>
        typeof c[0] === "string" && c[0].includes("/renders/1/build-sheet"),
    );
    expect(postCall).toBeDefined();

    // Resolve
    resolveBS({
      id: 1,
      render_id: 1,
      materials_llm: "ClaudeSonnet",
      material_items: [],
      tool_list: [],
      build_steps: [],
      total_cost_range: "$0",
      skill_level: "Beginner",
      assumptions: [],
      created_at: "2024-06-01T00:00:00Z",
    });

    // Transitions to Build Sheet display showing header values
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Build Sheet" })).toBeInTheDocument();
      expect(screen.getByText("$0")).toBeInTheDocument();
      expect(screen.getByText("Beginner")).toBeInTheDocument();
    });
  });

  it("surfaces 400 detail message on failed build sheet generation", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults })
      // build-sheet GET: 404 (no existing build sheet)
      .mockResolvedValueOnce(noBuiltSheet404)
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: "ANTHROPIC_API_KEY is not configured." }),
      });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Generate Build Sheet/i }),
      ).not.toBeDisabled();
    });

    await userEvent.click(
      screen.getByRole("button", { name: /Generate Build Sheet/i }),
    );

    await waitFor(() => {
      expect(
        screen.getByText(/ANTHROPIC_API_KEY is not configured/i),
      ).toBeInTheDocument();
    });
  });

  it("shows Project Dimensions after clicking Choose on a render", async () => {
    const projectNoChosen = {
      ...baseProject,
      design_requests: [
        {
          id: 10,
          project_id: 1,
          parent_render_id: null,
          image_provider: "GeminiFlashImage",
          feature_categories: ["Deck"],
          style: "Modern",
          quality_tier: "Budget",
          composed_prompt: "...",
          created_at: "2024-06-01T00:00:00Z",
          renders: [
            {
              id: 1,
              design_request_id: 10,
              image_path: "/a.png",
              image_url: "/renders/1",
              is_chosen: false,
              created_at: "2024-06-01T00:00:00Z",
            },
            {
              id: 2,
              design_request_id: 10,
              image_path: "/b.png",
              image_url: "/renders/2",
              is_chosen: false,
              created_at: "2024-06-01T00:00:00Z",
            },
            {
              id: 3,
              design_request_id: 10,
              image_path: "/c.png",
              image_url: "/renders/3",
              is_chosen: false,
              created_at: "2024-06-01T00:00:00Z",
            },
          ],
        },
      ],
    };

    (fetch as ReturnType<typeof vi.fn>).mockImplementation(async (url: string, init?: RequestInit) => {
      const urlText = String(url);
      if (urlText === "/api/projects/1") {
        return { ok: true, json: async () => projectNoChosen };
      }
      if (urlText.endsWith("/dimension-defaults")) {
        return { ok: true, json: async () => deckDefaults };
      }
      if (urlText.endsWith("/build-sheet")) {
        return noBuiltSheet404;
      }
      if (urlText === "/api/renders/1/choose" && init?.method === "PATCH") {
        return {
          ok: true,
          json: async () => ({
            id: 1,
            design_request_id: 10,
            image_path: "/a.png",
            image_url: "/renders/1",
            is_chosen: true,
            created_at: "2024-06-01T00:00:00Z",
          }),
        };
      }
      return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
    });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /^Choose$/i })).toHaveLength(3);
    });

    await userEvent.click(screen.getAllByRole("button", { name: /^Choose$/i })[0]);

    await waitFor(() => {
      expect(screen.getByText("Project Dimensions")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Build Sheet display
// ---------------------------------------------------------------------------

describe("ProjectDetailPage — Build Sheet display", () => {
  const deckRender = {
    id: 1,
    design_request_id: 10,
    image_path: "/a.png",
    image_url: "/renders/1",
    is_chosen: true,
    created_at: "2024-06-01T00:00:00Z",
  };

  const projectWithDeckChosen = {
    ...baseProject,
    design_requests: [
      {
        id: 10,
        project_id: 1,
        parent_render_id: null,
        image_provider: "GeminiFlashImage",
        feature_categories: ["Deck"],
        style: "Modern",
        quality_tier: "Budget",
        composed_prompt: "...",
        created_at: "2024-06-01T00:00:00Z",
        renders: [
          deckRender,
          {
            id: 2,
            design_request_id: 10,
            image_path: "/b.png",
            image_url: "/renders/2",
            is_chosen: false,
            created_at: "2024-06-01T00:00:00Z",
          },
          {
            id: 3,
            design_request_id: 10,
            image_path: "/c.png",
            image_url: "/renders/3",
            is_chosen: false,
            created_at: "2024-06-01T00:00:00Z",
          },
        ],
      },
    ],
  };

  const deckDefaults = { deck_width_ft: "12", deck_length_ft: "16", deck_height_ft: "3" };

  const richBuildSheet = {
    id: 1,
    render_id: 1,
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

  async function setupAndGenerateBuildSheet() {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults })
      .mockResolvedValueOnce(noBuiltSheet404)
      .mockResolvedValueOnce({ ok: true, json: async () => richBuildSheet });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Generate Build Sheet/i }),
      ).not.toBeDisabled();
    });

    await userEvent.click(
      screen.getByRole("button", { name: /Generate Build Sheet/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Build Sheet" })).toBeInTheDocument();
    });
  }

  it("posts selected Materials LLM, shows generation loading state, and renders completed Build Sheet sections", async () => {
    let resolveBuildSheet!: (v: unknown) => void;
    const buildSheetPromise = new Promise((resolve) => {
      resolveBuildSheet = resolve;
    });

    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults })
      .mockResolvedValueOnce(noBuiltSheet404)
      .mockReturnValueOnce({
        ok: true,
        json: () => buildSheetPromise,
      } as unknown as Promise<Response>);

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Generate Build Sheet/i })).not.toBeDisabled();
    });

    await userEvent.click(screen.getByRole("radio", { name: /GPT-5/i }));
    await userEvent.click(screen.getByRole("button", { name: /Generate Build Sheet/i }));

    expect(screen.getByRole("button", { name: /Generating Build Sheet/i })).toBeDisabled();

    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls).toContainEqual(["/api/renders/1/build-sheet"]);

    const postCall = calls.find(
      ([url, init]) =>
        url === "/api/renders/1/build-sheet" &&
        (init as RequestInit | undefined)?.method === "POST",
    );
    expect(postCall).toBeDefined();
    expect(postCall?.[1]).toMatchObject({
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    expect(JSON.parse((postCall?.[1] as RequestInit).body as string)).toEqual({
      materials_llm: "gpt5",
      dimensions: deckDefaults,
    });

    resolveBuildSheet(richBuildSheet);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Build Sheet" })).toBeInTheDocument();
    });

    expect(screen.getByText("$3,500 - $5,200")).toBeInTheDocument();
    expect(screen.getAllByText("Intermediate").length).toBeGreaterThan(0);
    expect(screen.getByText("Pressure-treated 2x6")).toBeInTheDocument();
    expect(screen.getByText("$160 - $200")).toBeInTheDocument();
    expect(screen.getByText("Tools needed")).toBeInTheDocument();
    expect(screen.getByText("Circular saw")).toBeInTheDocument();
    expect(screen.getByText("Build instructions")).toBeInTheDocument();
    expect(screen.getByText("Mark the deck perimeter with stakes and string")).toBeInTheDocument();
    expect(screen.getByText("Assumptions")).toBeInTheDocument();
    expect(screen.getByText("Deck area calculated as 12ft x 16ft = 192 sqft")).toBeInTheDocument();
  });

  it("shows header with total cost range and skill level", async () => {
    await setupAndGenerateBuildSheet();

    expect(screen.getByText("$3,500 - $5,200")).toBeInTheDocument();
    expect(screen.getAllByText("Intermediate").length).toBeGreaterThan(0);
    expect(screen.getByText(/Total Estimated Cost/i)).toBeInTheDocument();
    expect(screen.getByText(/Skill Level/i)).toBeInTheDocument();
  });

  it("shows materials table with all required columns", async () => {
    await setupAndGenerateBuildSheet();

    // Table headers
    expect(screen.getByText("Material")).toBeInTheDocument();
    expect(screen.getByText("Qty")).toBeInTheDocument();
    expect(screen.getByText("Unit")).toBeInTheDocument();
    expect(screen.getByText("Unit cost")).toBeInTheDocument();
    expect(screen.getByText("Total")).toBeInTheDocument();
    expect(screen.getByText("Vendor")).toBeInTheDocument();
    expect(screen.getByText("Link")).toBeInTheDocument();

    // Material row data
    expect(screen.getByText("Pressure-treated 2x6")).toBeInTheDocument();
    expect(screen.getByText("boards")).toBeInTheDocument();
    expect(screen.getByText("$8 - $10")).toBeInTheDocument();
    expect(screen.getByText("$160 - $200")).toBeInTheDocument();
    expect(screen.getByText("Home Depot")).toBeInTheDocument();
  });

  it("product URL is a clickable link when present", async () => {
    await setupAndGenerateBuildSheet();

    const link = screen.getByRole("link", { name: /View/i });
    expect(link).toHaveAttribute("href", "https://www.homedepot.com/p/123");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("shows a Build Sheet indicator on the chosen Render thumbnail when one exists", async () => {
    await setupAndGenerateBuildSheet();

    expect(
      screen.getByRole("link", { name: /Open Render 1/i }),
    ).toHaveAttribute("href", "/projects/1/renders/1");
    expect(
      screen.getByTitle("Build Sheet exists for Render 1.1"),
    ).toBeInTheDocument();
    expect(document.getElementById("build-sheet-render-1")).toBeInTheDocument();
  });

  it("shows em dash for missing product URL", async () => {
    await setupAndGenerateBuildSheet();

    // Concrete mix has empty product_url → should show "—"
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("shows Tool List section with all tools", async () => {
    await setupAndGenerateBuildSheet();

    expect(screen.getByText("Tools needed")).toBeInTheDocument();
    expect(screen.getByText("Circular saw")).toBeInTheDocument();
    expect(screen.getByText("Drill")).toBeInTheDocument();
    expect(screen.getByText("Level")).toBeInTheDocument();
  });

  it("shows ordered Build Steps with description and estimated time", async () => {
    await setupAndGenerateBuildSheet();

    expect(screen.getByText("Build instructions")).toBeInTheDocument();
    expect(
      screen.getByText("Mark the deck perimeter with stakes and string"),
    ).toBeInTheDocument();
    expect(screen.getByText(/2 hours/i)).toBeInTheDocument();
    expect(
      screen.getByText("Dig post holes to frost depth"),
    ).toBeInTheDocument();
    expect(screen.getByText(/4 hours/i)).toBeInTheDocument();
  });

  it("shows Assumptions section with every assumption string", async () => {
    await setupAndGenerateBuildSheet();

    expect(screen.getByText("Assumptions")).toBeInTheDocument();
    expect(
      screen.getByText("Deck area calculated as 12ft x 16ft = 192 sqft"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Local lumber prices may vary"),
    ).toBeInTheDocument();
  });

  it("loads existing Build Sheet via GET on page revisit (no AI call)", async () => {
    // Simulate revisiting a project that already has a Build Sheet persisted
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults })
      // GET build-sheet returns the persisted build sheet immediately
      .mockResolvedValueOnce({ ok: true, json: async () => richBuildSheet });

    renderAt("/projects/1");

    // Build Sheet should appear without any user interaction
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Build Sheet" })).toBeInTheDocument();
      expect(screen.getByText("$3,500 - $5,200")).toBeInTheDocument();
      expect(screen.getAllByText("Intermediate").length).toBeGreaterThan(0);
    });

    // Confirm no POST was made (no createBuildSheet call)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
    const postBsCall = calls.find(
      (c: unknown[]) =>
        typeof c[0] === "string" &&
        c[0].includes("/renders/1/build-sheet") &&
        (c[1] as RequestInit | undefined)?.method === "POST",
    );
    expect(postBsCall).toBeUndefined();
  });

  it("dimensions form is hidden once a Build Sheet is loaded from GET", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: async () => projectWithDeckChosen })
      .mockResolvedValueOnce({ ok: true, json: async () => deckDefaults })
      .mockResolvedValueOnce({ ok: true, json: async () => richBuildSheet });

    renderAt("/projects/1");

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Build Sheet" })).toBeInTheDocument();
    });

    // The dimensions form and generate button should not be shown
    expect(
      screen.queryByText("Project Dimensions"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Generate Build Sheet/i }),
    ).not.toBeInTheDocument();
  });
});
