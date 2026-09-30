import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listProjects, ProjectListItem } from "../api/projects";
import HistoryView from "../components/HistoryView";
import TopNav from "../components/TopNav";

export default function ProjectListPage() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

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

        {loading && <p className="text-muted">Loading…</p>}

        {!loading && error && (
          <p className="alert-danger">Error loading projects: {error}</p>
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
