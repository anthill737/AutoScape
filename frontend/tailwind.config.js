/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--color-surface)",
        "surface-elevated": "var(--color-surface-elevated)",
        foreground: "var(--color-foreground)",
        muted: "var(--color-muted)",
        // Legacy accent shades remain until follow-up P16 tasks replace existing color classes.
        accent: {
          DEFAULT: "var(--color-accent)",
          foreground: "var(--color-accent-foreground)",
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
        },
        danger: "var(--color-danger)",
        success: "var(--color-success)",
        border: "var(--color-border)",
        // Legacy chosen shades remain until follow-up P16 tasks replace existing color classes.
        chosen: {
          50: "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          300: "#fcd34d",
          500: "#f59e0b",
          700: "#b45309",
          800: "#92400e",
        },
      },
      borderColor: {
        default: "var(--color-border)",
      },
      textColor: {
        "accent-foreground": "var(--color-accent-foreground)",
      },
      backgroundColor: {
        accent: "var(--color-accent)",
      },
      ringColor: {
        accent: "var(--color-accent)",
      },
      outlineColor: {
        accent: "var(--color-accent)",
      },
      divideColor: {
        default: "var(--color-border)",
      },
      placeholderColor: {
        muted: "var(--color-muted)",
      },
    },
  },
  plugins: [],
};
