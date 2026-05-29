import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  DARK_DEFAULT_THEME,
  LIGHT_DEFAULT_THEME,
  THEME_STORAGE_KEY,
  ThemeProvider,
  getInitialTheme,
  useTheme,
} from "../theme/ThemeProvider";

function ThemeConsumer() {
  const { theme, setTheme } = useTheme();

  return (
    <div>
      <output aria-label="active theme">{theme}</output>
      <button type="button" onClick={() => setTheme("dark-forest")}>
        Set forest
      </button>
    </div>
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

describe("ThemeProvider", () => {
  it("uses stored theme before OS preference fallbacks", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light-warm");
    stubMatchMedia(true);

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    expect(screen.getByLabelText("active theme")).toHaveTextContent("light-warm");
    expect(document.documentElement.dataset.theme).toBe("light-warm");
  });

  it("falls back to light-default with no storage entry and no dark OS preference", () => {
    expect(getInitialTheme()).toBe(LIGHT_DEFAULT_THEME);
  });

  it("falls back to dark-default with no storage entry and dark OS preference", () => {
    stubMatchMedia(true);

    expect(getInitialTheme()).toBe(DARK_DEFAULT_THEME);
  });

  it("setTheme updates html data-theme, localStorage, and consumers", async () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    expect(screen.getByLabelText("active theme")).toHaveTextContent("light-default");

    await userEvent.click(screen.getByRole("button", { name: "Set forest" }));

    expect(document.documentElement.dataset.theme).toBe("dark-forest");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark-forest");
    expect(screen.getByLabelText("active theme")).toHaveTextContent("dark-forest");
  });
});
