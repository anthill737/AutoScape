import { useEffect, useMemo, useState } from "react";
import TopNav from "../components/TopNav";
import type { ProviderModels } from "../api/models";
import { useModelCatalog } from "../hooks/useModelCatalog";
import {
  SETTINGS_KEYS,
  SettingsKeyName,
  SettingsKeyStatus,
  clearSettingsKey,
  listSettingsKeys,
  saveSettingsKey,
  testSettingsKey,
} from "../api/settings";

type TestState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok" }
  | { status: "error"; error: string };

const EMPTY_TEST_STATES = Object.fromEntries(
  SETTINGS_KEYS.map((key) => [key.name, { status: "idle" }]),
) as Record<SettingsKeyName, TestState>;

export default function SettingsPage() {
  const [keys, setKeys] = useState<SettingsKeyStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<SettingsKeyName | null>(null);
  const [draftValue, setDraftValue] = useState("");
  const [saving, setSaving] = useState<SettingsKeyName | null>(null);
  const [clearing, setClearing] = useState<SettingsKeyName | null>(null);
  const [testStates, setTestStates] =
    useState<Record<SettingsKeyName, TestState>>(EMPTY_TEST_STATES);
  const models = useModelCatalog();

  useEffect(() => {
    listSettingsKeys()
      .then(setKeys)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const keyByName = useMemo(() => {
    return new Map(keys.map((key) => [key.name, key]));
  }, [keys]);

  function updateKey(updated: SettingsKeyStatus) {
    setKeys((current) => {
      const next = current.filter((key) => key.name !== updated.name);
      return [...next, updated];
    });
  }

  function startEditing(name: SettingsKeyName) {
    setEditing(name);
    setDraftValue("");
    setError(null);
  }

  async function handleSave(name: SettingsKeyName) {
    setSaving(name);
    setError(null);
    try {
      const updated = await saveSettingsKey(name, draftValue);
      updateKey(updated);
      setEditing(null);
      setDraftValue("");
      void models.refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(null);
    }
  }

  async function handleClear(name: SettingsKeyName) {
    if (!window.confirm(`Clear ${name}?`)) return;

    setClearing(name);
    setError(null);
    try {
      const updated = await clearSettingsKey(name);
      updateKey(updated);
      setTestStates((current) => ({
        ...current,
        [name]: { status: "idle" },
      }));
      void models.refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setClearing(null);
    }
  }

  async function handleTest(name: SettingsKeyName) {
    setTestStates((current) => ({
      ...current,
      [name]: { status: "loading" },
    }));
    try {
      const result = await testSettingsKey(name);
      setTestStates((current) => ({
        ...current,
        [name]: result.ok
          ? { status: "ok" }
          : { status: "error", error: result.error ?? "Unknown error" },
      }));
    } catch (e: unknown) {
      setTestStates((current) => ({
        ...current,
        [name]: {
          status: "error",
          error: e instanceof Error ? e.message : "Unknown error",
        },
      }));
    }
  }

  return (
    <div className="min-h-screen bg-surface text-foreground">
      <TopNav title="Settings" crumb={{ label: "Projects", to: "/" }} maxWidthClass="max-w-5xl" />

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="mb-6">
          <p className="as-eyebrow">Settings</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground">API keys</h2>
          <p className="as-help mt-1">
            Keys are stored in the project's secrets folder on this machine and never leave it.
            Each vendor bills your own account per request.
          </p>
        </div>
        {loading && <p className="text-muted">Loading settings...</p>}
        {error && <p className="alert-danger mb-4">{error}</p>}

        {!loading && (
          <div className="as-card overflow-hidden">
            <div className="divide-y divide-default">
              {SETTINGS_KEYS.map((settingsKey) => {
                const keyStatus = keyByName.get(settingsKey.name) ?? {
                  name: settingsKey.name,
                  set: false,
                  masked_value: null,
                };
                const isEditing = editing === settingsKey.name;
                const testState = testStates[settingsKey.name];

                return (
                  <section
                    key={settingsKey.name}
                    aria-label={settingsKey.name}
                    className="p-4 sm:p-5"
                  >
                    <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_auto] gap-4 lg:items-center">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-3">
                          <h2 className="font-semibold text-foreground">
                            {settingsKey.name}
                          </h2>
                          <span className={keyStatus.set ? "pill-success" : "pill-muted"}>
                            {keyStatus.set ? "Set" : "Not set"}
                          </span>
                        </div>
                        <a
                          href={settingsKey.signupUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-1 inline-block text-sm text-accent hover:underline break-all"
                        >
                          {settingsKey.signupUrl}
                        </a>
                        <p className="mt-2 text-sm text-muted">
                          {keyStatus.masked_value ?? "Not set"}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => startEditing(settingsKey.name)}
                          className="btn-secondary btn-sm"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleClear(settingsKey.name)}
                          disabled={clearing === settingsKey.name}
                          className="btn-secondary btn-sm"
                        >
                          {clearing === settingsKey.name ? "Clearing..." : "Clear"}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleTest(settingsKey.name)}
                          disabled={testState.status === "loading"}
                          className="btn-primary btn-sm min-w-20"
                        >
                          {testState.status === "loading" && (
                            <span
                              aria-hidden="true"
                              className="h-4 w-4 rounded-full border-2 border-surface-elevated border-t-accent-foreground animate-spin"
                            />
                          )}
                          {testState.status === "loading" ? "Testing" : "Test"}
                        </button>
                      </div>
                    </div>

                    {isEditing && (
                      <div className="mt-4 flex flex-col sm:flex-row gap-2">
                        <label className="sr-only" htmlFor={`${settingsKey.name}-value`}>
                          {settingsKey.name} value
                        </label>
                        <input
                          id={`${settingsKey.name}-value`}
                          type="password"
                          value={draftValue}
                          onChange={(e) => setDraftValue(e.target.value)}
                          className="field min-w-0 flex-1"
                          autoFocus
                        />
                        <button
                          type="button"
                          onClick={() => handleSave(settingsKey.name)}
                          disabled={saving === settingsKey.name}
                          className="btn-primary"
                        >
                          {saving === settingsKey.name ? "Saving..." : "Save"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(null);
                            setDraftValue("");
                          }}
                          className="btn-secondary"
                        >
                          Cancel
                        </button>
                      </div>
                    )}

                    {testState.status === "ok" && (
                      <p className="mt-3 text-sm font-medium text-success">OK</p>
                    )}
                    {testState.status === "error" && (
                      <p className="alert-danger mt-3 font-medium">{testState.error}</p>
                    )}
                  </section>
                );
              })}
            </div>
          </div>
        )}

        {!loading && (
          <AvailableModelsPanel
            providers={[
              ...models.catalog.image,
              ...models.catalog.materials,
              ...models.catalog.grounding,
            ]}
            loading={models.loading}
            error={models.error}
            onRefresh={() => void models.refresh()}
          />
        )}
      </main>
    </div>
  );
}

const ROLE_LABELS: Record<ProviderModels["role"], string> = {
  image: "Renders",
  materials: "Build Sheet",
  grounding: "Product research",
};

function AvailableModelsPanel({
  providers,
  loading,
  error,
  onRefresh,
}: {
  providers: ProviderModels[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  return (
    <section aria-label="Available models" className="mt-8">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Available models</h2>
          <p className="text-sm text-muted">
            Fetched live from each vendor with your keys. Pick a model per request on the
            project page; these lists show what is currently offered.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="btn-secondary btn-sm"
        >
          {loading ? "Refreshing..." : "Refresh models"}
        </button>
      </div>
      {error && (
        <p className="alert-danger mb-3">{error}</p>
      )}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {providers.map((provider) => (
          <article
            key={provider.slug}
            aria-label={`${provider.label} models`}
            className="as-card p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-foreground">{provider.label}</h3>
              <span className="pill-muted">{ROLE_LABELS[provider.role]}</span>
            </div>
            <p className="mt-1 text-xs text-muted">
              {provider.key_set
                ? provider.source === "live"
                  ? `${provider.models.length} models from ${provider.vendor}`
                  : "Built-in list (vendor list unavailable)"
                : `${provider.key_env} not set — built-in list`}
              {provider.error && provider.key_set ? ` · ${provider.error}` : ""}
            </p>
            <ul className="mt-2 max-h-56 space-y-1 overflow-y-auto text-sm text-foreground">
              {provider.models
                .filter((m) => m.current)
                .map((m) => (
                  <li key={m.id} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5">
                    <span className="flex flex-wrap items-baseline gap-2">
                      <span>{m.display_name}</span>
                      <code className="text-xs text-muted">{m.id}</code>
                      {m.recommended && (
                        <span className="text-[11px] uppercase text-accent">recommended</span>
                      )}
                    </span>
                    <span className="text-xs text-muted" aria-label="quality">
                      {m.quality != null ? "●".repeat(m.quality) + "○".repeat(5 - m.quality) : ""}
                    </span>
                    <span className="col-span-2 text-xs text-muted">
                      {[m.cost, m.note].filter(Boolean).join(" · ")}
                    </span>
                  </li>
                ))}
              {provider.models.some((m) => !m.current) && (
                <li className="text-xs text-muted">
                  + {provider.models.filter((m) => !m.current).length} older or snapshot ids
                  (available under "Show older" on the project page)
                </li>
              )}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}
