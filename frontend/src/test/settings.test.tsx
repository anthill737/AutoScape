import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import ProjectListPage from "../pages/ProjectListPage";
import SettingsPage from "../pages/SettingsPage";
import { ThemeProvider } from "../theme/ThemeProvider";

const settingsRows = [
  {
    name: "GOOGLE_API_KEY",
    set: true,
    masked_value: "AIza...wxyz",
  },
  {
    name: "OPENAI_API_KEY",
    set: false,
    masked_value: null,
  },
  {
    name: "ANTHROPIC_API_KEY",
    set: true,
    masked_value: "sk-a...1234",
  },
  {
    name: "PERPLEXITY_API_KEY",
    set: false,
    masked_value: null,
  },
];

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

function renderSettings(path = "/settings") {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<ProjectListPage />} />
          <Route path="/settings" element={<SettingsPage />} />
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

describe("SettingsPage", () => {
  it("renders the Settings nav link and all four rows from GET", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => settingsRows,
      });

    renderSettings("/");

    await userEvent.click(screen.getByRole("link", { name: "Settings" }));

    await waitFor(() => {
      expect(screen.getByLabelText("GOOGLE_API_KEY")).toBeInTheDocument();
    });

    for (const row of settingsRows) {
      const section = screen.getByLabelText(row.name);
      expect(within(section).getByText(row.name)).toBeInTheDocument();
      expect(within(section).getByRole("link")).toHaveAttribute("href");
      expect(within(section).getByRole("button", { name: "Edit" })).toBeInTheDocument();
      expect(within(section).getByRole("button", { name: "Clear" })).toBeInTheDocument();
      expect(within(section).getByRole("button", { name: "Test" })).toBeInTheDocument();
    }
    expect(within(screen.getByLabelText("GOOGLE_API_KEY")).getByText("Set")).toBeInTheDocument();
    expect(
      within(screen.getByLabelText("OPENAI_API_KEY")).getAllByText("Not set").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("AIza...wxyz")).toBeInTheDocument();
  });

  it("saves an edited value with PUT and updates the masked value", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => settingsRows,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          name: "OPENAI_API_KEY",
          set: true,
          masked_value: "sk-n...7890",
        }),
      });

    renderSettings();

    const row = await screen.findByLabelText("OPENAI_API_KEY");
    await userEvent.click(within(row).getByRole("button", { name: "Edit" }));
    await userEvent.type(
      within(row).getByLabelText("OPENAI_API_KEY value"),
      "sk-new-value-7890",
    );
    await userEvent.click(within(row).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(screen.getByText("sk-n...7890")).toBeInTheDocument();
    });

    expect(fetch).toHaveBeenNthCalledWith(2, "/api/settings/keys/OPENAI_API_KEY", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: "sk-new-value-7890" }),
    });
  });

  it("clears a key with DELETE after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => settingsRows,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          name: "GOOGLE_API_KEY",
          set: false,
          masked_value: null,
        }),
      });

    renderSettings();

    const row = await screen.findByLabelText("GOOGLE_API_KEY");
    await userEvent.click(within(row).getByRole("button", { name: "Clear" }));

    await waitFor(() => {
      expect(within(row).getAllByText("Not set").length).toBeGreaterThan(0);
    });

    expect(window.confirm).toHaveBeenCalledWith("Clear GOOGLE_API_KEY?");
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/settings/keys/GOOGLE_API_KEY", {
      method: "DELETE",
    });
  });

  it("shows OK and verbatim error states from Test", async () => {
    const googleResult = deferred<{ ok: true }>();
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => settingsRows,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => googleResult.promise,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: false, error: "provider said no" }),
      });

    renderSettings();

    const googleRow = await screen.findByLabelText("GOOGLE_API_KEY");
    await userEvent.click(within(googleRow).getByRole("button", { name: "Test" }));
    expect(
      await within(googleRow).findByRole("button", { name: "Testing" }),
    ).toBeDisabled();
    googleResult.resolve({ ok: true });
    await waitFor(() => {
      expect(within(googleRow).getByText("OK")).toBeInTheDocument();
    });

    const anthropicRow = screen.getByLabelText("ANTHROPIC_API_KEY");
    await userEvent.click(within(anthropicRow).getByRole("button", { name: "Test" }));
    await waitFor(() => {
      expect(within(anthropicRow).getByText("X provider said no")).toBeInTheDocument();
    });

    expect(fetch).toHaveBeenNthCalledWith(2, "/api/settings/keys/GOOGLE_API_KEY/test", {
      method: "POST",
    });
    expect(fetch).toHaveBeenNthCalledWith(3, "/api/settings/keys/ANTHROPIC_API_KEY/test", {
      method: "POST",
    });
  });
});
