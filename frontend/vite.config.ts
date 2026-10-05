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
    // P18-T2 root cause: default host "localhost" bound IPv6 [::1]:5173 only (no IPv4 listener); pin 127.0.0.1.
    // Bind IPv4 loopback explicitly. Vite's default `localhost` host resolves to
    // whichever address the OS returns first, which on Windows was binding only
    // IPv6 [::1]:5173 with no 127.0.0.1 listener. The launcher opens/probes
    // http://localhost:5173 and the backend binds 127.0.0.1, so on machines where
    // localhost resolves to IPv4 (IPv6 loopback disabled) the app served nothing.
    // 127.0.0.1 always exists, matches the backend and the proxy target, and stays
    // reachable via http://localhost:5173 and http://127.0.0.1:5173.
    host: "127.0.0.1",
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
