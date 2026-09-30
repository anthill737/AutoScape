import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import NewProjectPage from "../pages/NewProjectPage";
import ProjectDetailPage from "../pages/ProjectDetailPage";
import { ThemeProvider } from "../theme/ThemeProvider";
import { INTERIOR_SPACE, dimensionFieldsFor, seedPromptFor, spaceLabelFor } from "../api/spaces";

function renderAt(path: string) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/projects/new" element={<NewProjectPage />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/projects/:id/renders/:renderId" element={<ProjectDetailPage />} />
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

describe("space config helpers", () => {
  it("seeds an interior prompt with the room and lower-cased choices", () => {
    const text = seedPromptFor(INTERIOR_SPACE, "Kitchen", ["Cabinets", "Flooring"], "Japandi", "Premium");
    expect(text).toMatch(/^Redesign this kitchen as a premium japandi interior featuring Cabinets, Flooring\./);
    expect(text).toMatch(/no labels or text/);
  });

  it("maps interior categories to their measurement fields", () => {
    expect(dimensionFieldsFor(INTERIOR_SPACE, ["Cabinets", "Flooring", "Furniture Layout"]).map((f) => f.key)).toEqual([
      "cabinet_linear_ft",
      "upper_cabinet_linear_ft",
      "floor_sqft",
    ]);
    expect(spaceLabelFor(INTERIOR_SPACE, "Bathroom")).toBe("Bathroom");
    expect(spaceLabelFor(INTERIOR_SPACE, null)).toBe("Interior");
  });
});

describe("NewProjectPage — interior", () => {
  it("switches the form to room fields and posts space_type, room_type and space_details", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 9, address: "12 Elm St · Kitchen", created_at: "2026-01-01T00:00:00Z" }),
    });
    renderAt("/projects/new");

    await userEvent.click(screen.getByRole("radio", { name: /Interior/i }));
    expect(screen.getByLabelText(/^Room$/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Room length/i)).toBeInTheDocument();
    expect(screen.queryByText(/Lot size/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Stand in a doorway or corner/i)).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/Address or project name/i), "12 Elm St · Kitchen");
    await userEvent.selectOptions(screen.getByLabelText(/^Room$/), "Kitchen");
    await userEvent.type(screen.getByLabelText(/Room length/i), "14");
    await userEvent.type(screen.getByLabelText(/Room width/i), "12");
    await userEvent.type(screen.getByLabelText(/Ceiling height/i), "9");
    const file = new File(["(fake jpeg)"], "kitchen.jpg", { type: "image/jpeg" });
    await userEvent.upload(screen.getByLabelText(/Room photo/i), file);
    await userEvent.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/projects", expect.anything()));
    const body = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body as FormData;
    expect(body.get("space_type")).toBe("interior");
    expect(body.get("room_type")).toBe("Kitchen");
    expect(JSON.parse(body.get("space_details") as string)).toEqual({
      room_length_ft: 14,
      room_width_ft: 12,
      ceiling_height_ft: 9,
    });
    expect(body.get("site_photo")).toBe(file);
  });

  it("requires a room and the room size for interiors", async () => {
    renderAt("/projects/new");
    await userEvent.click(screen.getByRole("radio", { name: /Interior/i }));
    const file = new File(["(fake jpeg)"], "kitchen.jpg", { type: "image/jpeg" });
    await userEvent.upload(screen.getByLabelText(/Room photo/i), file);
    await userEvent.type(screen.getByLabelText(/Address or project name/i), "12 Elm St");
    await userEvent.click(screen.getByRole("button", { name: /^Save$/ }));
    expect(screen.getByText(/Pick which room this is/i)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/^Room$/), "Bathroom");
    await userEvent.click(screen.getByRole("button", { name: /^Save$/ }));
    expect(screen.getByText(/Room length \(ft\) must be a positive number/i)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("ProjectDetailPage — interior project", () => {
  const interiorProject = {
    id: 9,
    address: "12 Elm St · Kitchen",
    space_type: "interior",
    room_type: "Kitchen",
    space_label: "Kitchen",
    space_details: { room_length_ft: 14, room_width_ft: 12, ceiling_height_ft: 9 },
    lot_size_sqft: null,
    house_sqft: null,
    site_photo_url: "/images/9/site_photo.jpg",
    created_at: "2026-01-01T00:00:00Z",
    design_requests: [] as unknown[],
  };

  it("offers interior categories and styles and seeds a room-aware prompt", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => interiorProject,
    });
    renderAt("/projects/9");

    const summary = await screen.findByRole("region", { name: /Project summary/i });
    expect(within(summary).getByText("Kitchen")).toBeInTheDocument();
    expect(within(summary).getByText(/Room length 14 ft/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /New Design Request/i }));
    const form = screen.getByRole("form", { name: /New design request/i });
    expect(within(form).getByRole("checkbox", { name: "Cabinets" })).toBeInTheDocument();
    expect(within(form).getByRole("checkbox", { name: "Flooring" })).toBeInTheDocument();
    expect(within(form).queryByRole("checkbox", { name: "Deck" })).not.toBeInTheDocument();
    expect(within(form).getByRole("radio", { name: "Japandi" })).toBeInTheDocument();
    expect(within(form).getByRole("radio", { name: "Modern" })).toBeChecked();
    expect(within(form).getByText(/The room photo/)).toBeInTheDocument();

    const textarea = within(form).getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.value).toMatch(/^Redesign this kitchen as a budget modern interior\./);

    await userEvent.click(within(form).getByRole("checkbox", { name: "Cabinets" }));
    expect(textarea.value).toContain("featuring Cabinets");
  });

  it("shows interior measurement fields for a chosen render", async () => {
    const project = {
      ...interiorProject,
      design_requests: [
        {
          id: 20,
          project_id: 9,
          parent_render_id: null,
          image_provider: "gpt_image",
          image_model: "gpt-image-2.5-flare",
          feature_categories: ["Cabinets", "Countertops"],
          style: "Scandinavian",
          quality_tier: "Mid-range",
          composed_prompt: "x",
          created_at: "2026-01-02T00:00:00Z",
          renders: [
            {
              id: 30,
              design_request_id: 20,
              image_path: "/30.png",
              image_url: "/renders/30",
              is_chosen: true,
              created_at: "2026-01-02T00:00:00Z",
            },
          ],
        },
      ],
    };
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(async (url: string) => {
      if (url === "/api/projects/9") return { ok: true, json: async () => project };
      if (url === "/api/renders/30/dimension-defaults") {
        return { ok: true, json: async () => ({ cabinet_linear_ft: "18", countertop_sqft: "40" }) };
      }
      return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
    });
    renderAt("/projects/9");

    await waitFor(() => {
      expect(
        (screen.getByRole("spinbutton", { name: /^Cabinet run/i }) as HTMLInputElement).value,
      ).toBe("18");
    });
    expect(screen.getByRole("spinbutton", { name: /Countertop area/i })).toBeInTheDocument();
    expect(screen.queryByRole("spinbutton", { name: /Deck Width/i })).not.toBeInTheDocument();
  });
});
