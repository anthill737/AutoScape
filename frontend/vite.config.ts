import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readBackendPort } from "./readBackendPort";

const backendPort = readBackendPort();
const backendProxy = {
  "/api": {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  },
  "/images": {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  },
  "/thumbnails": {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  },
  "/renders": {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
  },
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
