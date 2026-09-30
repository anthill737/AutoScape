import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readBackendPort } from "./readBackendPort";

/**
 * Build a proxy entry whose target is resolved LIVE on every request.
 *
 * Vite reads this config exactly once, at startup. If we computed a fixed
 * target string here (the old behaviour), the proxy would be frozen to
 * whatever port .runtime-port held the instant vite booted — and if the
 * backend hadn't written its port yet, or had picked a different free port
 * (common when you run several local servers at once), every /api call would
 * be forwarded to the wrong port and 500.
 *
 * http-proxy supports a `router` function that is consulted per request and
 * overrides `target`. We use it to re-read .runtime-port each time, so the
 * proxy always follows the backend's actual port and self-heals if it changes.
 */
function makeProxyEntry() {
  return {
    changeOrigin: true,
    // Initial target (required by the types); router() below takes precedence.
    target: `http://127.0.0.1:${readBackendPort()}`,
    // Re-resolved on every proxied request.
    router: () => `http://127.0.0.1:${readBackendPort()}`,
  };
}

const backendProxy = {
  "/api": makeProxyEntry(),
  "/images": makeProxyEntry(),
  "/thumbnails": makeProxyEntry(),
  "/renders": makeProxyEntry(),
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: backendProxy,
  },
  preview: {
    proxy: backendProxy,
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
  },
});
