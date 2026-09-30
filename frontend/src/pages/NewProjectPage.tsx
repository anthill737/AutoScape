import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createProject } from "../api/projects";
import { findSpace, type SpaceConfig } from "../api/spaces";
import TopNav from "../components/TopNav";
import { useSpaces } from "../hooks/useSpaces";

const SPACE_ICON: Record<string, string> = { exterior: "🌿", interior: "🛋️" };

export default function NewProjectPage() {
  const navigate = useNavigate();
  const { spaces } = useSpaces();

  const [spaceId, setSpaceId] = useState<string>("exterior");
  const [roomType, setRoomType] = useState<string>("");
  const [address, setAddress] = useState("");
  const [sizes, setSizes] = useState<Record<string, string>>({});
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const space: SpaceConfig = useMemo(() => findSpace(spaces, spaceId), [spaces, spaceId]);
  const isInterior = space.id === "interior";

  useEffect(() => {
    if (!photo || typeof URL.createObjectURL !== "function") {
      setPhotoUrl(null);
      return;
    }
    const url = URL.createObjectURL(photo);
    setPhotoUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  function chooseSpace(id: string) {
    setSpaceId(id);
    setRoomType("");
    setSizes({});
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!photo) {
      setError(isInterior ? "Please select a photo of the room." : "Please select a Site Photo.");
      return;
    }
    if (!address.trim()) {
      setError(isInterior ? "Address or a name for this project is required." : "Address is required.");
      return;
    }
    if (isInterior && space.room_types.length > 0 && !roomType) {
      setError("Pick which room this is.");
      return;
    }
    for (const field of space.size_fields) {
      const raw = sizes[field.key] ?? "";
      if (field.required && (!raw || Number(raw) <= 0)) {
        setError(`${field.label} must be a positive number.`);
        return;
      }
      if (!field.required && raw && Number(raw) <= 0) {
        setError(`${field.label} must be a positive number.`);
        return;
      }
    }

    const fd = new FormData();
    fd.append("address", address);
    fd.append("space_type", space.id);
    if (isInterior && roomType) fd.append("room_type", roomType);
    const details: Record<string, number> = {};
    for (const field of space.size_fields) {
      const raw = sizes[field.key];
      if (raw && Number(raw) > 0) details[field.key] = Number(raw);
    }
    fd.append("space_details", JSON.stringify(details));
    // Outdoor projects also send the two classic fields the API has always accepted.
    if (!isInterior) {
      fd.append("lot_size", sizes.lot_size_sqft ?? "");
      fd.append("house_sqft", sizes.house_sqft ?? "");
    }
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
      <TopNav title="New Project" crumb={{ label: "Projects", to: "/" }} maxWidthClass="max-w-3xl" />

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <div className="mb-6">
          <p className="as-eyebrow">New project</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground">
            What are we designing?
          </h2>
          <p className="as-help mt-1">
            Pick the kind of space, add a photo and a few sizes. You will generate renders on the
            next screen.
          </p>
        </div>

        {/* noValidate: custom validation in handleSubmit instead of native browser popups */}
        <form onSubmit={handleSubmit} noValidate className="space-y-6">
          {error && <p className="alert-danger">{error}</p>}

          {/* 1 · Space type */}
          <section className="as-card p-5 sm:p-6">
            <p className="as-eyebrow mb-3">1 · Space</p>
            <div role="radiogroup" aria-label="Space type" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {spaces.map((s) => {
                const on = s.id === space.id;
                return (
                  <button
                    key={s.id}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    onClick={() => chooseSpace(s.id)}
                    className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${
                      on
                        ? "border-accent bg-accent-soft shadow-sm"
                        : "border-default bg-surface-elevated hover:border-strong"
                    }`}
                  >
                    <span aria-hidden="true" className="text-2xl leading-none">
                      {SPACE_ICON[s.id] ?? "◇"}
                    </span>
                    <span className="min-w-0">
                      <span className="block font-semibold text-foreground">{s.label}</span>
                      <span className="mt-0.5 block text-xs text-muted">{s.description}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* 2 · Photo */}
          <section className="as-card p-5 sm:p-6">
            <p className="as-eyebrow mb-3">2 · Photo</p>
            <label
              htmlFor="site-photo"
              className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition ${
                photoUrl ? "border-accent bg-accent-soft" : "border-default bg-surface-sunken hover:border-strong"
              }`}
            >
              {photoUrl ? (
                <img
                  src={photoUrl}
                  alt="Selected photo preview"
                  className="max-h-64 w-auto rounded-lg object-contain shadow-sm"
                />
              ) : (
                <span aria-hidden="true" className="text-3xl">
                  📷
                </span>
              )}
              <span className="text-sm font-medium text-foreground">
                {photo ? photo.name : isInterior ? "Choose a photo of the room" : "Choose a Site Photo"}
              </span>
              <span className="text-xs text-muted">{space.photo_hint} JPEG or PNG.</span>
            </label>
            <input
              id="site-photo"
              type="file"
              accept="image/jpeg,image/png"
              aria-label={isInterior ? "Room photo" : "Site Photo"}
              onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
              className="sr-only"
            />
          </section>

          {/* 3 · Details */}
          <section className="as-card p-5 sm:p-6">
            <p className="as-eyebrow mb-3">3 · Details</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label htmlFor="address" className="field-label">
                  {isInterior ? "Address or project name" : "Address"}
                </label>
                <input
                  id="address"
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="field"
                  placeholder={isInterior ? "123 Main St · Kitchen" : "123 Main St, Springfield, IL"}
                />
              </div>

              {isInterior && space.room_types.length > 0 && (
                <div className="sm:col-span-2">
                  <label htmlFor="room-type" className="field-label">
                    Room
                  </label>
                  <select
                    id="room-type"
                    value={roomType}
                    onChange={(e) => setRoomType(e.target.value)}
                    className="field"
                  >
                    <option value="">Choose a room…</option>
                    {space.room_types.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {space.size_fields.map((field) => (
                <div key={field.key}>
                  <label htmlFor={`size-${field.key}`} className="field-label">
                    {field.label}
                    {!field.required && <span className="ml-1 font-normal text-muted">(optional)</span>}
                  </label>
                  <input
                    id={`size-${field.key}`}
                    type="number"
                    min="0"
                    step={field.key.endsWith("_sqft") ? "1" : "0.5"}
                    value={sizes[field.key] ?? ""}
                    onChange={(e) => setSizes((prev) => ({ ...prev, [field.key]: e.target.value }))}
                    className="field"
                    placeholder={field.key === "lot_size_sqft" ? "5000" : field.key === "house_sqft" ? "2000" : ""}
                  />
                </div>
              ))}
            </div>
          </section>

          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={saving} className="btn-primary btn-lg">
              {saving ? "Saving…" : "Save"}
            </button>
            <button type="button" onClick={() => navigate("/")} className="btn-secondary btn-lg">
              Cancel
            </button>
            <span className="as-help">Next: generate three design renders.</span>
          </div>
        </form>
      </main>
    </div>
  );
}
