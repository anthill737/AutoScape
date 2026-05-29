import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { THEME_OPTIONS, useTheme, type ThemeName } from "../theme/ThemeProvider";

interface TopNavProps {
  title?: string;
  maxWidthClass?: string;
  actions?: ReactNode;
}

function navLinkClass({ isActive }: { isActive: boolean }) {
  return [
    "text-sm font-medium transition",
    isActive ? "text-accent" : "text-muted hover:text-foreground",
  ].join(" ");
}

function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const activeTheme = THEME_OPTIONS.find((option) => option.name === theme) ?? THEME_OPTIONS[0];

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  function selectTheme(name: ThemeName) {
    setTheme(name);
    setIsOpen(false);
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        className="inline-flex items-center gap-2 rounded-md border border-default bg-surface-elevated px-3 py-2 text-sm font-medium text-foreground shadow-sm transition hover:border-accent focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span
          className="h-3 w-3 rounded-full border border-default"
          style={{ backgroundColor: activeTheme.accent }}
          aria-hidden="true"
        />
        <span>Theme</span>
      </button>

      {isOpen && (
        <div
          className="absolute right-0 z-50 mt-2 w-56 rounded-md border border-default bg-surface-elevated p-1 shadow-lg"
          role="menu"
          aria-label="Theme"
        >
          {THEME_OPTIONS.map((option) => {
            const isActive = option.name === theme;

            return (
              <button
                key={option.name}
                type="button"
                className="flex w-full items-center gap-3 rounded px-3 py-2 text-left text-sm text-foreground transition hover:bg-surface focus:bg-surface focus:outline-none"
                role="menuitemradio"
                aria-checked={isActive}
                onClick={() => selectTheme(option.name)}
              >
                <span
                  className="h-3 w-3 rounded-full border border-default"
                  style={{ backgroundColor: option.accent }}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">{option.label}</span>
                <span className="w-4 text-center text-accent" aria-hidden="true">
                  {isActive ? "✓" : ""}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function TopNav({
  title,
  maxWidthClass = "max-w-5xl",
  actions,
}: TopNavProps) {
  return (
    <header className="bg-surface-elevated shadow">
      <div
        className={`${maxWidthClass} mx-auto px-4 py-4 flex items-center justify-between gap-4`}
      >
        <div className="flex items-center gap-4 min-w-0">
          <Link to="/" className="text-2xl font-bold text-foreground shrink-0">
            AutoScape
          </Link>
          {title && (
            <h1 className="text-xl font-semibold text-foreground truncate">
              {title}
            </h1>
          )}
        </div>

        <nav className="flex items-center gap-4 shrink-0">
          <NavLink to="/" className={navLinkClass}>
            Projects
          </NavLink>
          <NavLink to="/settings" className={navLinkClass}>
            Settings
          </NavLink>
          <ThemeSwitcher />
          {actions}
        </nav>
      </div>
    </header>
  );
}
