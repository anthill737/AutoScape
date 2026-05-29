import type { DesignRequestOut } from "./designRequests";
import { parseApiError } from "./errors";

export interface ProjectListItem {
  id: number;
  address: string;
  site_photo_url: string | null;
  site_photo_thumb_url?: string | null;
  created_at: string;
  latest_design_request_at?: string | null;
  design_request_count: number;
  render_count: number;
  iteration_count: number;
  has_chosen_render: boolean;
  has_build_sheet: boolean;
  latest_quality_tier?: string | null;
}

export interface ProjectDetail {
  id: number;
  address: string;
  lot_size_sqft: number | null;
  house_sqft: number | null;
  site_photo_url: string | null;
  created_at: string;
  design_requests: DesignRequestOut[];
}

export async function listProjects(): Promise<ProjectListItem[]> {
  const res = await fetch("/api/projects");
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to fetch projects: ${res.status}`));
  }
  return res.json();
}

export async function getProject(id: number): Promise<ProjectDetail> {
  const res = await fetch(`/api/projects/${id}`);
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to fetch project: ${res.status}`));
  }
  return res.json();
}

export async function createProject(
  data: FormData,
): Promise<{ id: number; address: string; created_at: string }> {
  const res = await fetch("/api/projects", { method: "POST", body: data });
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  return res.json();
}
