import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export function readBackendPort(runtimePortFile?: string): number {
  const filePath =
    runtimePortFile ?? path.resolve(__dirname, "../backend/.runtime-port");
  try {
    const raw = fs.readFileSync(filePath, "utf8").trim();
    const port = parseInt(raw, 10);
    return isNaN(port) ? 8000 : port;
  } catch {
    return 8000;
  }
}
