import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export const THEME_STORAGE_KEY = "autoscape.theme";
export const LIGHT_DEFAULT_THEME = "light-default";
export const DARK_DEFAULT_THEME = "dark-default";

export const THEME_OPTIONS = [
  {
    name: LIGHT_DEFAULT_THEME,
    label: "Light — Default",
    accent: "#2563eb",
  },
  {
    name: DARK_DEFAULT_THEME,
    label: "Dark — Default",
    accent: "#60a5fa",
  },
  {
    name: "dark-forest",
    label: "Dark — Forest",
    accent: "#34d399",
  },
  {
    name: "light-warm",
    label: "Light — Warm",
    accent: "#9f3f22",
  },
] as const;

export type ThemeName = (typeof THEME_OPTIONS)[number]["name"];

type ThemeContextValue = {
  theme: ThemeName;
  setTheme: (name: ThemeName) => void;
};

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function isThemeName(value: string | null): value is ThemeName {
  return THEME_OPTIONS.some((theme) => theme.name === value);
}

function safeStoredTheme() {
  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeName(storedTheme) ? storedTheme : null;
  } catch {
    return null;
  }
}

function prefersDarkTheme() {
  try {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  } catch {
    return false;
  }
}

export function getInitialTheme() {
  return safeStoredTheme() || (prefersDarkTheme() ? DARK_DEFAULT_THEME : LIGHT_DEFAULT_THEME);
}

function applyTheme(name: ThemeName) {
  document.documentElement.dataset.theme = name;
}

function persistTheme(name: ThemeName) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, name);
  } catch {
    // The visible theme should still change if storage is unavailable.
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState(getInitialTheme);

  useLayoutEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = useCallback((name: ThemeName) => {
    applyTheme(name);
    persistTheme(name);
    setThemeState(name);
  }, []);

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}
