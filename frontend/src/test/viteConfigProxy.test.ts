// @vitest-environment node
// Tests for the proxy-port resolution logic defined in readBackendPort.ts,
// which vite.config.ts uses to wire the dev-proxy to the running backend.

import { describe, it, expect } from "vitest";
import * as nodefs from "fs";
import * as nodeos from "os";
import * as nodepath from "path";

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
    const configPath = nodepath.resolve("vite.config.ts");
    const configSource = nodefs.readFileSync(configPath, "utf8");

    expect(configSource).toContain("const backendProxy");
    expect(configSource).toContain('"/images"');
    expect(configSource).toContain('"/thumbnails"');
    expect(configSource).toContain('"/renders"');
    expect(configSource).toMatch(
      /"\/thumbnails"\s*:\s*\{\s*target:\s*`http:\/\/127\.0\.0\.1:\$\{backendPort\}`,\s*changeOrigin:\s*true,\s*\}/s,
    );
    expect(configSource).toMatch(
      /"\/renders"\s*:\s*\{\s*target:\s*`http:\/\/127\.0\.0\.1:\$\{backendPort\}`,\s*changeOrigin:\s*true,\s*\}/s,
    );
    expect(configSource).toMatch(/server:\s*\{[^}]*proxy:\s*backendProxy/s);
    expect(configSource).toMatch(/preview:\s*\{[^}]*proxy:\s*backendProxy/s);
  });
});
