import { Link } from "react-router-dom";
import type { ProjectListItem } from "../api/projects";

interface HistoryViewProps {
  projects: ProjectListItem[];
  onCreateProject: () => void;
}

function activeAt(project: ProjectListItem) {
  return project.latest_design_request_at ?? project.created_at;
}

function formatDate(value: string | null) {
  if (!value) return "No date";
  return new Date(value).toLocaleDateString();
}

function qualityPillClass(quality: string) {
  const normalized = quality.toLowerCase();
  if (normalized.includes("premium")) {
    return "border-accent text-accent";
  }
  if (normalized.includes("budget")) {
    return "border-default text-muted";
  }
  return "border-default text-foreground";
}

function sortedProjects(projects: ProjectListItem[]) {
  return [...projects].sort((a, b) => {
    const bTime = new Date(activeAt(b)).getTime();
    const aTime = new Date(activeAt(a)).getTime();
    return bTime - aTime;
  });
}

export default function HistoryView({ projects, onCreateProject }: HistoryViewProps) {
  if (projects.length === 0) {
    return (
      <div className="mx-auto max-w-xl py-20 text-center">
        <p className="text-xl font-semibold text-foreground">
          No projects yet - create one to get started.
        </p>
        <button
          type="button"
          onClick={onCreateProject}
          className="mt-6 rounded bg-accent px-5 py-3 text-base font-medium text-accent-foreground transition hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface"
        >
          New Project
        </button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {sortedProjects(projects).map((project) => {
        const thumbnailUrl = project.site_photo_thumb_url ?? project.site_photo_url;
        const qualityTier = project.latest_quality_tier;
        const countLine = `${project.design_request_count} Design Requests · ${project.render_count} Renders · ${project.iteration_count} Iterations`;

        return (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            aria-label={`Open project ${project.address}`}
            className="group flex h-full flex-col overflow-hidden rounded-lg border border-default bg-surface-elevated shadow-sm transition hover:-translate-y-0.5 hover:border-accent hover:shadow-md focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface"
          >
            <div className="aspect-video w-full overflow-hidden bg-surface">
              {thumbnailUrl ? (
                <img
                  src={thumbnailUrl}
                  alt={project.address}
                  loading="lazy"
                  className="h-full w-full object-contain"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-sm text-muted">
                  No photo
                </div>
              )}
            </div>

            <div className="flex flex-1 flex-col p-4">
              <div className="min-w-0">
                <h2 className="truncate text-base font-semibold text-foreground">
                  {project.address}
                </h2>
                <p className="mt-1 text-sm text-muted">
                  Created {formatDate(project.created_at)}
                </p>
                <p className="mt-3 text-sm text-foreground">{countLine}</p>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {project.has_chosen_render && (
                  <span className="rounded-full border border-accent bg-surface px-2.5 py-1 text-xs font-medium text-accent">
                    Chosen
                  </span>
                )}
                {project.has_build_sheet && (
                  <span className="rounded-full border border-default bg-surface px-2.5 py-1 text-xs font-medium text-foreground">
                    Build Sheet
                  </span>
                )}
                {qualityTier && (
                  <span
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium ${qualityPillClass(
                      qualityTier,
                    )}`}
                  >
                    {qualityTier}
                  </span>
                )}
              </div>

              <div className="mt-auto pt-5 text-sm font-medium text-accent">
                Open
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
