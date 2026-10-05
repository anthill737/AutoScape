import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listProjects, ProjectListItem } from "../api/projects";
import HistoryView from "../components/HistoryView";
import TopNav from "../components/TopNav";

export default function ProjectListPage() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    // listProjects retries connection errors and 5xx while the backend is still
    // starting, so "Starting up…" stays up until it either answers or gives up.
    let active = true;
    setLoading(true);
    setError(null);
    listProjects()
      .then((loadedProjects) => {
        if (active) setProjects(loadedProjects);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [retryNonce]);

  return (
    <div className="min-h-screen bg-surface text-foreground">
      <TopNav
        actions={
          <button onClick={() => navigate("/projects/new")} className="btn-primary btn-sm">
            New Project
          </button>
        }
      />

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="as-eyebrow">Projects</p>
            <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground">
              Your spaces
            </h2>
            <p className="as-help mt-1">
              Each project is one photo of a yard or a room, its design renders, and its build sheet.
            </p>
          </div>
          {!loading && !error && projects.length > 0 && (
            <button onClick={() => navigate("/projects/new")} className="btn-secondary">
              + New Project
            </button>
          )}
        </div>

        {loading && (
          <div className="as-card p-6">
            <p className="text-base font-semibold text-foreground">Starting up…</p>
            <p className="as-help mt-2">
              AutoScape is waiting for the backend before loading Projects.
            </p>
          </div>
        )}

        {!loading && error && (
          <div className="alert-danger">
            <p className="font-semibold">Could not load Projects</p>
            <p className="mt-1">{error}</p>
            <button
              type="button"
              onClick={() => setRetryNonce((value) => value + 1)}
              className="btn-primary btn-sm mt-3"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && (
          <HistoryView
            projects={projects}
            onCreateProject={() => navigate("/projects/new")}
          />
        )}
      </main>
    </div>
  );
}
