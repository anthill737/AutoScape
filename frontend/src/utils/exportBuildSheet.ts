import { BuildSheetOut, MaterialItem, BuildStep } from "../api/designRequests";

function escapeHtml(s: string | number | undefined | null): string {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function imageUrlToDataUri(url: string): Promise<string> {
  const res = await fetch(url);
  const blob = await res.blob();
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

const INLINE_CSS = `
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:14px;line-height:1.5;color:#111827;background:#f3f4f6;padding:32px 16px}
.container{max-width:900px;margin:0 auto;background:#fff;border-radius:8px;padding:32px;box-shadow:0 1px 3px rgba(0,0,0,.12),0 1px 2px rgba(0,0,0,.08)}
h1{font-size:24px;font-weight:700;color:#111827;margin-bottom:24px}
h2{font-size:18px;font-weight:600;color:#1f2937;margin-bottom:12px}
.render-img{display:block;width:100%;max-height:420px;object-fit:contain;background:#e5e5e5;border-radius:6px;margin-bottom:24px;border:1px solid #e5e7eb}
.summary{display:flex;flex-wrap:wrap;gap:32px;padding:16px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;margin-bottom:24px}
.summary-label{font-size:11px;text-transform:uppercase;letter-spacing:.05em;font-weight:500;color:#6b7280;margin-bottom:4px}
.summary-value{font-size:22px;font-weight:700;color:#111827}
.summary-skill{font-size:17px;font-weight:600;color:#1f2937}
.section{margin-bottom:28px}
.table-wrapper{overflow-x:auto}
table{width:100%;border-collapse:collapse;border:1px solid #e5e7eb;font-size:13px}
thead{background:#f9fafb}
th{padding:8px 12px;text-align:left;font-size:11px;font-weight:500;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;border-bottom:1px solid #e5e7eb}
td{padding:8px 12px;color:#374151;border-top:1px solid #f3f4f6}
a{color:#2563eb;word-break:break-all}
ul{list-style-type:disc;padding-left:20px}
ul li{padding:3px 0;color:#374151;font-size:14px}
ol{list-style:none;padding:0}
.step{display:flex;gap:12px;margin-bottom:12px;align-items:flex-start}
.step-num{flex-shrink:0;width:24px;height:24px;border-radius:50%;background:#dbeafe;color:#1d4ed8;font-size:11px;font-weight:700;display:inline-flex;align-items:center;justify-content:center}
.step-content{flex:1}
.step-desc{color:#1f2937;font-size:14px}
.step-time{color:#6b7280;font-size:12px;margin-top:2px}
.assumptions{background:#fefce8;border:1px solid #fde047;border-radius:6px;padding:12px 16px}
.assumptions ul li{color:#854d0e;font-size:13px}
`.trim();

export function buildSheetToHtml(
  buildSheet: BuildSheetOut,
  imageDataUri: string | null,
): string {
  const imageHtml = imageDataUri
    ? `<img class="render-img" src="${imageDataUri}" alt="Chosen Render" />`
    : "";

  const materialsHtml =
    buildSheet.material_items.length > 0
      ? `<div class="section">
  <h2>Materials</h2>
  <div class="table-wrapper">
    <table>
      <thead><tr>${["Name", "Qty", "Unit", "Unit Cost", "Total Cost", "Vendor", "Product"]
        .map((h) => `<th>${h}</th>`)
        .join("")}</tr></thead>
      <tbody>${buildSheet.material_items
        .map(
          (item: MaterialItem) =>
            `<tr>
          <td>${escapeHtml(item.name)}</td>
          <td>${escapeHtml(item.quantity)}</td>
          <td>${escapeHtml(item.unit)}</td>
          <td>${escapeHtml(item.unit_cost_range)}</td>
          <td>${escapeHtml(item.total_cost_range)}</td>
          <td>${escapeHtml(item.vendor)}</td>
          <td>${
            item.product_url
              ? `<a href="${escapeHtml(item.product_url)}">${escapeHtml(item.product_url)}</a>`
              : "—"
          }</td>
        </tr>`,
        )
        .join("")}</tbody>
    </table>
  </div>
</div>`
      : "";

  const toolListHtml =
    buildSheet.tool_list.length > 0
      ? `<div class="section">
  <h2>Tools Needed</h2>
  <ul>${buildSheet.tool_list.map((t: string) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>
</div>`
      : "";

  const buildStepsHtml =
    buildSheet.build_steps.length > 0
      ? `<div class="section">
  <h2>Build Steps</h2>
  <ol>${buildSheet.build_steps
    .map(
      (step: BuildStep, i: number) =>
        `<li class="step">
      <span class="step-num">${step.step_number ?? i + 1}</span>
      <div class="step-content">
        <div class="step-desc">${escapeHtml(step.description)}</div>
        ${step.estimated_time ? `<div class="step-time">⏱ ${escapeHtml(step.estimated_time)}</div>` : ""}
      </div>
    </li>`,
    )
    .join("")}</ol>
</div>`
      : "";

  const assumptionsHtml =
    buildSheet.assumptions.length > 0
      ? `<div class="section">
  <h2>Assumptions</h2>
  <div class="assumptions">
    <ul>${buildSheet.assumptions.map((a: string) => `<li>${escapeHtml(a)}</li>`).join("")}</ul>
  </div>
</div>`
      : "";

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AutoScape Build Sheet</title>
  <style>${INLINE_CSS}</style>
</head>
<body>
  <div class="container">
    <h1>AutoScape Build Sheet</h1>
    ${imageHtml}
    <div class="summary">
      <div>
        <div class="summary-label">Total Estimated Cost</div>
        <div class="summary-value">${escapeHtml(buildSheet.total_cost_range)}</div>
      </div>
      <div>
        <div class="summary-label">Skill Level</div>
        <div class="summary-skill">${escapeHtml(buildSheet.skill_level)}</div>
      </div>
    </div>
    ${materialsHtml}
    ${toolListHtml}
    ${buildStepsHtml}
    ${assumptionsHtml}
  </div>
</body>
</html>`;
}

export async function exportBuildSheet(
  buildSheet: BuildSheetOut,
  renderImageUrl: string | null,
): Promise<void> {
  let imageDataUri: string | null = null;
  if (renderImageUrl) {
    try {
      imageDataUri = await imageUrlToDataUri(renderImageUrl);
    } catch {
      // proceed without image rather than blocking the export
    }
  }

  const html = buildSheetToHtml(buildSheet, imageDataUri);
  const blob = new Blob([html], { type: "text/html" });
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = `autoscape-build-sheet-${buildSheet.id}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(objectUrl);
}
