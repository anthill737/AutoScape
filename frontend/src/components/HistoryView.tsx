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
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function sortedProjects(projects: ProjectListItem[]) {
  return [...projects].sort((a, b) => {
    const bTime = new Date(activeAt(b)).getTime();
    const aTime = new Date(activeAt(a)).getTime();
    return bTime - aTime;
  });
}

/** Where the project is in the photo → renders → chosen → build sheet flow. */
function stageOf(project: ProjectListItem): { label: string; tone: string; step: number } {
  if (project.has_build_sheet) return { label: "Build Sheet ready", tone: "pill-success", step: 4 };
  if (project.has_chosen_render) return { label: "Render chosen", tone: "pill-accent", step: 3 };
  if (project.render_count > 0) return { label: "Renders ready", tone: "pill-accent", step: 2 };
  return { label: "Needs renders", tone: "pill-muted", step: 1 };
}

function spaceBadge(project: ProjectListItem): string {
  if (project.space_label) return project.space_label;
  return project.space_type === "interior" ? "Interior" : "Outdoor";
}

export default function HistoryView({ projects, onCreateProject }: HistoryViewProps) {
  if (projects.length === 0) {
    return (
      <div className="as-card mx-auto max-w-xl px-8 py-16 text-center">
        <div
          aria-hidden="true"
          className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-2xl"
        >
          ✦
        </div>
        <p className="text-xl font-semibold tracking-tight text-foreground">
          No projects yet - create one to get started.
        </p>
        <p className="as-help mt-2">
          Upload a photo of a yard or a room, generate three design renders, then turn your
          favourite into a priced build sheet.
        </p>
        <button type="button" onClick={onCreateProject} className="btn-primary btn-lg mt-6">
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
        const stage = stageOf(project);
        const countLine = `${project.design_request_count} Design Requests · ${project.render_count} Renders · ${project.iteration_count} Iterations`;

        return (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            aria-label={`Open project ${project.address}`}
            className="as-card group flex h-full flex-col overflow-hidden transition hover:-translate-y-0.5 hover:border-strong hover:shadow-pop focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
          >
            <div className="relative aspect-[4/3] w-full overflow-hidden bg-surface-sunken">
              {thumbnailUrl ? (
                <img
                  src={thumbnailUrl}
                  alt={project.address}
                  loading="lazy"
                  className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-sm text-muted">
                  No photo
                </div>
              )}
              <span className="absolute left-3 top-3 rounded-full bg-surface-elevated/90 px-2.5 py-1 text-[11px] font-semibold text-foreground shadow-sm backdrop-blur">
                {spaceBadge(project)}
              </span>
            </div>

            <div className="flex flex-1 flex-col p-4">
              <div className="min-w-0">
                <h2 className="truncate text-base font-semibold tracking-tight text-foreground">
                  {project.address}
                </h2>
                <p className="mt-1 text-xs text-muted">
                  Updated {formatDate(activeAt(project))}
                </p>
                <p className="mt-3 text-sm text-muted">{countLine}</p>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className={stage.tone}>{stage.label}</span>
                {project.has_chosen_render && <span className="pill-muted">Chosen</span>}
                {project.has_build_sheet && <span className="pill-muted">Build Sheet</span>}
                {qualityTier && <span className="pill-muted">{qualityTier}</span>}
              </div>

              <div className="mt-auto flex items-center justify-between pt-5">
                <div className="flex gap-1" aria-label={`Step ${stage.step} of 4`}>
                  {[1, 2, 3, 4].map((n) => (
                    <span
                      key={n}
                      className={`h-1.5 w-6 rounded-full ${n <= stage.step ? "bg-accent" : "bg-border"}`}
                    />
                  ))}
                </div>
                <span className="text-sm font-medium text-accent">Open</span>
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
