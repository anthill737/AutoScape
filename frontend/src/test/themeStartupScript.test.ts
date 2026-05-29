import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const indexHtml = readFileSync(resolve(__dirname, "../../index.html"), "utf8");

describe("theme startup script", () => {
  it("is inline and runs before the React module script", () => {
    const inlineScriptIndex = indexHtml.indexOf("<script>");
    const bundleScriptIndex = indexHtml.indexOf(
      '<script type="module" src="/src/main.tsx"></script>',
    );

    expect(inlineScriptIndex).toBeGreaterThan(-1);
    expect(bundleScriptIndex).toBeGreaterThan(-1);
    expect(inlineScriptIndex).toBeLessThan(bundleScriptIndex);

    const inlineScriptEnd = indexHtml.indexOf("</script>", inlineScriptIndex);
    const inlineScript = indexHtml.slice(inlineScriptIndex, inlineScriptEnd);
    expect(inlineScript).not.toContain("src=");
    expect(inlineScript).not.toContain("defer");
    expect(inlineScript).not.toContain("async");
  });

  it("reads storage, checks dark OS preference, and sets html data-theme", () => {
    expect(indexHtml).toContain('localStorage.getItem("autoscape.theme")');
    expect(indexHtml).toContain("(prefers-color-scheme: dark)");
    expect(indexHtml).toContain('theme = prefersDark ? "dark-default" : "light-default"');
    expect(indexHtml).toContain("document.documentElement.dataset.theme = theme");
  });
});
