import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createProject } from "../api/projects";
import TopNav from "../components/TopNav";

export default function NewProjectPage() {
  const navigate = useNavigate();
  const [address, setAddress] = useState("");
  const [lotSize, setLotSize] = useState("");
  const [houseSqft, setHouseSqft] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!photo) {
      setError("Please select a Site Photo.");
      return;
    }
    if (!address.trim()) {
      setError("Address is required.");
      return;
    }
    if (!lotSize || Number(lotSize) <= 0) {
      setError("Lot size must be a positive number.");
      return;
    }
    if (!houseSqft || Number(houseSqft) <= 0) {
      setError("House sqft must be a positive number.");
      return;
    }

    const fd = new FormData();
    fd.append("address", address);
    fd.append("lot_size", lotSize);
    fd.append("house_sqft", houseSqft);
    fd.append("site_photo", photo);

    setSaving(true);
    setError(null);
    try {
      const project = await createProject(fd);
      navigate(`/projects/${project.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface text-foreground">
      <TopNav title="New Project" maxWidthClass="max-w-2xl" />

      <main className="max-w-2xl mx-auto px-4 py-8">
        {/* noValidate: custom validation in handleSubmit instead of native browser popups */}
        <form
          onSubmit={handleSubmit}
          noValidate
          className="space-y-4 rounded border border-default bg-surface-elevated p-6 shadow"
        >
          {error && <p className="text-danger">{error}</p>}

          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              Site Photo
            </label>
            <input
              type="file"
              accept="image/jpeg,image/png"
              onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-muted file:mr-4 file:rounded file:border-0 file:bg-accent file:px-3 file:py-2 file:text-sm file:font-medium file:text-accent-foreground hover:file:opacity-90"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              Address
            </label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full rounded border border-default bg-surface-elevated px-3 py-2 text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent"
              placeholder="123 Main St, Springfield, IL"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              Lot Size (sqft)
            </label>
            <input
              type="number"
              value={lotSize}
              onChange={(e) => setLotSize(e.target.value)}
              className="w-full rounded border border-default bg-surface-elevated px-3 py-2 text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent"
              min="0"
              step="1"
              placeholder="5000"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              House Sqft
            </label>
            <input
              type="number"
              value={houseSqft}
              onChange={(e) => setHouseSqft(e.target.value)}
              className="w-full rounded border border-default bg-surface-elevated px-3 py-2 text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent"
              min="0"
              step="1"
              placeholder="2000"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded bg-accent px-6 py-2 text-accent-foreground transition hover:opacity-90 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={() => navigate("/")}
              className="rounded border border-default bg-surface px-6 py-2 text-foreground transition hover:bg-surface-elevated"
            >
              Cancel
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
