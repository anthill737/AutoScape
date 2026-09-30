import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { THEME_OPTIONS, useTheme, type ThemeName } from "../theme/ThemeProvider";

interface TopNavProps {
  /** Page title shown after the brand, e.g. the project address. */
  title?: string;
  /** Optional crumb shown before the title, e.g. "Projects". */
  crumb?: { label: string; to: string };
  maxWidthClass?: string;
  actions?: ReactNode;
}

function navLinkClass({ isActive }: { isActive: boolean }) {
  return [
    "rounded-lg px-3 py-1.5 text-sm font-medium transition",
    isActive ? "bg-accent-soft text-accent" : "text-muted hover:bg-surface-sunken hover:text-foreground",
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
        className="btn-secondary btn-sm"
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
          className="absolute right-0 z-50 mt-2 w-56 rounded-xl border border-default bg-surface-elevated p-1 shadow-pop"
          role="menu"
          aria-label="Theme"
        >
          {THEME_OPTIONS.map((option) => {
            const isActive = option.name === theme;

            return (
              <button
                key={option.name}
                type="button"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-foreground transition hover:bg-surface-sunken focus:bg-surface-sunken focus:outline-none"
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

function BrandMark() {
  return (
    <span
      aria-hidden="true"
      className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-extrabold text-accent-foreground shadow-sm"
    >
      A
    </span>
  );
}

export default function TopNav({
  title,
  crumb,
  maxWidthClass = "max-w-7xl",
  actions,
}: TopNavProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-default bg-surface-elevated/85 backdrop-blur supports-[backdrop-filter]:bg-surface-elevated/70">
      <div className={`${maxWidthClass} mx-auto flex items-center justify-between gap-4 px-4 py-3 sm:px-6`}>
        <div className="flex min-w-0 items-center gap-3">
          <Link
            to="/"
            className="flex shrink-0 items-center gap-2 text-lg font-bold tracking-tight text-foreground"
          >
            <BrandMark />
            <span>AutoScape</span>
          </Link>
          {(crumb || title) && (
            <span className="hidden text-border-strong sm:inline" aria-hidden="true">
              /
            </span>
          )}
          {crumb && (
            <Link to={crumb.to} className="hidden text-sm text-muted hover:text-foreground sm:inline">
              {crumb.label}
            </Link>
          )}
          {crumb && title && (
            <span className="hidden text-border-strong sm:inline" aria-hidden="true">
              /
            </span>
          )}
          {title && (
            <h1 className="truncate text-sm font-semibold text-foreground sm:text-base">{title}</h1>
          )}
        </div>

        <nav className="flex shrink-0 items-center gap-1 sm:gap-2">
          <NavLink to="/" className={navLinkClass} end>
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
