import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Read the backend port that the launcher recorded in backend/.runtime-port.
 *
 * IMPORTANT: this is called on EVERY proxied request (see vite.config.ts), not
 * just once at startup. That is deliberate. The launcher probes for a free port
 * at run time (so AutoScape never collides with your other local servers) and
 * writes the chosen port to .runtime-port. Because the backend may start a
 * fraction of a second after vite, and because the chosen port can differ run
 * to run, the proxy must re-read this file live rather than freezing whatever
 * value happened to be present when vite first booted.
 */
export function readBackendPort(runtimePortFile?: string): number {
  const filePath =
    runtimePortFile ?? path.resolve(__dirname, "../backend/.runtime-port");
  try {
    const raw = fs.readFileSync(filePath, "utf8").trim();
    const port = parseInt(raw, 10);
    if (Number.isInteger(port) && port > 0 && port < 65536) {
      return port;
    }
    return 8000;
  } catch {
    // File not yet written (backend still starting) — fall back to 8000.
    // The per-request re-read means the very next request will pick up the
    // real port as soon as the launcher writes it, so this fallback is only
    // ever hit during the brief startup window.
    return 8000;
  }
}
