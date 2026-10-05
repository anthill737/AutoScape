// @vitest-environment node
// Tests for the proxy-port resolution logic defined in readBackendPort.ts,
// which vite.config.ts uses to wire the dev-proxy to the running backend.

import { describe, it, expect } from "vitest";
import * as nodefs from "fs";
import * as nodeos from "os";
import * as nodepath from "path";
import * as nodeurl from "url";

// Dynamic import avoids the TypeScript compiler resolving Node.js types
// through tsconfig.json (which targets the browser and lacks @types/node).
// Vitest uses esbuild for transpilation so the runtime import works fine.
const { readBackendPort } = await import("../../readBackendPort");

describe("readBackendPort (vite.config proxy-port resolution)", () => {
  it("returns the port from .runtime-port when the file is present", () => {
    const tmpDir = nodefs.mkdtempSync(nodepath.join(nodeos.tmpdir(), "ascape-test-"));
    const tmpFile = nodepath.join(tmpDir, ".runtime-port");
    try {
      nodefs.writeFileSync(tmpFile, "8005\n");
      const port = readBackendPort(tmpFile);
      expect(port).toBe(8005);
    } finally {
      nodefs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("falls back to 8000 when .runtime-port cannot be read", () => {
    const port = readBackendPort("/nonexistent/path/.runtime-port");
    expect(port).toBe(8000);
  });

  it("resolved proxy target URL uses the port from .runtime-port", () => {
    const tmpDir = nodefs.mkdtempSync(nodepath.join(nodeos.tmpdir(), "ascape-test-"));
    const tmpFile = nodepath.join(tmpDir, ".runtime-port");
    try {
      nodefs.writeFileSync(tmpFile, "8007");
      const port = readBackendPort(tmpFile);
      const proxyTarget = `http://127.0.0.1:${port}`;
      expect(proxyTarget).toBe("http://127.0.0.1:8007");
    } finally {
      nodefs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("resolved proxy target falls back to http://127.0.0.1:8000 when file is absent", () => {
    const port = readBackendPort("/nonexistent/.runtime-port");
    const proxyTarget = `http://127.0.0.1:${port}`;
    expect(proxyTarget).toBe("http://127.0.0.1:8000");
  });

  it("vite dev and preview proxies include generated image URLs", () => {
    // Resolve from this file, not process.cwd(): the suite must pass whether it
    // is launched from frontend/ or from the repo root with --root frontend.
    const frontendDir = nodepath.resolve(
      nodepath.dirname(nodeurl.fileURLToPath(import.meta.url)),
      "../..",
    );
    const configPath = nodepath.join(frontendDir, "vite.config.ts");
    const configSource = nodefs.readFileSync(configPath, "utf8");

    expect(configSource).toContain("const backendProxy");
    expect(configSource).toContain('"/images"');
    expect(configSource).toContain('"/thumbnails"');
    expect(configSource).toContain('"/renders"');
    // Every proxied prefix uses the shared entry builder, whose router()
    // re-reads .runtime-port per request so the target follows the backend.
    for (const prefix of ["/api", "/images", "/thumbnails", "/renders"]) {
      expect(configSource).toMatch(
        new RegExp(`"${prefix.replace("/", "\\/")}"\\s*:\\s*makeProxyEntry\\(\\)`),
      );
    }
    expect(configSource).toMatch(
      /router:\s*\(\)\s*=>\s*`http:\/\/127\.0\.0\.1:\$\{readBackendPort\(\)\}`/,
    );
    expect(configSource).toMatch(/changeOrigin:\s*true/);
    expect(configSource).toMatch(/server:\s*\{[^}]*proxy:\s*backendProxy/s);
    expect(configSource).toMatch(/preview:\s*\{[^}]*proxy:\s*backendProxy/s);
  });
});
