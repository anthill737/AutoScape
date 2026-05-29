import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TopNav from "../components/TopNav";
import { THEME_OPTIONS, THEME_STORAGE_KEY, ThemeProvider } from "../theme/ThemeProvider";

function renderTopNav() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <TopNav />
      </MemoryRouter>
    </ThemeProvider>,
  );
}

function stubMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  stubMatchMedia(false);
});

describe("ThemeSwitcher", () => {
  it("lists every theme with a swatch and only checkmarks the active theme", async () => {
    renderTopNav();

    await userEvent.click(screen.getByRole("button", { name: "Theme" }));

    const menu = screen.getByRole("menu", { name: "Theme" });
    for (const option of THEME_OPTIONS) {
      const item = within(menu).getByRole("menuitemradio", { name: option.label });
      expect(item).toHaveAttribute("aria-checked", String(option.name === "light-default"));
      expect(item.querySelector('[style*="background-color"]')).toHaveStyle({
        backgroundColor: option.accent,
      });
    }

    const checkmarkedItems = within(menu)
      .getAllByRole("menuitemradio")
      .filter((item) => item.textContent?.includes("✓"));
    expect(checkmarkedItems).toHaveLength(1);
    expect(checkmarkedItems[0]).toHaveTextContent("Light — Default");
  });

  it("changes the active theme immediately without navigation", async () => {
    renderTopNav();

    await userEvent.click(screen.getByRole("button", { name: "Theme" }));
    await userEvent.click(screen.getByRole("menuitemradio", { name: "Dark — Forest" }));

    expect(document.documentElement.dataset.theme).toBe("dark-forest");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark-forest");

    await userEvent.click(screen.getByRole("button", { name: "Theme" }));
    expect(screen.getByRole("menuitemradio", { name: "Dark — Forest" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("menuitemradio", { name: "Light — Default" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });
});
