/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      colors: {
        surface: "var(--color-surface)",
        "surface-sunken": "var(--color-surface-sunken)",
        "surface-elevated": "var(--color-surface-elevated)",
        foreground: "var(--color-foreground)",
        muted: "var(--color-muted)",
        accent: {
          DEFAULT: "var(--color-accent)",
          strong: "var(--color-accent-strong)",
          foreground: "var(--color-accent-foreground)",
          soft: "var(--color-accent-soft)",
        },
        danger: {
          DEFAULT: "var(--color-danger)",
          soft: "var(--color-danger-soft)",
        },
        success: {
          DEFAULT: "var(--color-success)",
          soft: "var(--color-success-soft)",
        },
        warning: {
          DEFAULT: "var(--color-warning)",
          soft: "var(--color-warning-soft)",
        },
        border: {
          DEFAULT: "var(--color-border)",
          strong: "var(--color-border-strong)",
        },
      },
      borderColor: {
        default: "var(--color-border)",
        strong: "var(--color-border-strong)",
      },
      // bg-accent, text-accent-foreground, ring-accent, outline-accent, divide-* and
      // placeholder colours all derive from `colors` above; per-plugin overrides here
      // would shadow the nested tokens (bg-accent-soft etc.).
      divideColor: {
        default: "var(--color-border)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        pop: "var(--shadow-pop)",
      },
      borderRadius: {
        xl2: "1rem",
      },
    },
  },
  plugins: [],
};
