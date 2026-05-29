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
          <button
            onClick={() => navigate("/projects/new")}
            className="rounded bg-accent px-4 py-2 text-accent-foreground transition hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface"
          >
            New Project
          </button>
        }
      />

      <main className="max-w-5xl mx-auto px-4 py-8">
        {loading && <p className="text-muted">Loading…</p>}

        {!loading && error && (
          <p className="text-danger">Error loading projects: {error}</p>
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
