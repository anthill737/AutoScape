import { useEffect, useMemo, useState } from "react";
import TopNav from "../components/TopNav";
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

function statusPill(isSet: boolean) {
  return isSet
    ? "bg-surface-elevated text-success border-success"
    : "bg-surface text-muted border-default";
}

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
      <TopNav title="Settings" />

      <main className="max-w-5xl mx-auto px-4 py-8">
        {loading && <p className="text-muted">Loading settings...</p>}
        {error && (
          <p className="mb-4 rounded border border-danger bg-surface-elevated px-3 py-2 text-danger">
            {error}
          </p>
        )}

        {!loading && (
          <div className="bg-surface-elevated rounded border border-default shadow overflow-hidden">
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
                          <span
                            className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${statusPill(keyStatus.set)}`}
                          >
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
                          className="px-3 py-2 rounded border border-default text-sm font-medium text-foreground hover:bg-surface"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleClear(settingsKey.name)}
                          disabled={clearing === settingsKey.name}
                          className="px-3 py-2 rounded border border-default text-sm font-medium text-foreground hover:bg-surface disabled:opacity-50"
                        >
                          {clearing === settingsKey.name ? "Clearing..." : "Clear"}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleTest(settingsKey.name)}
                          disabled={testState.status === "loading"}
                          className="inline-flex min-w-20 items-center justify-center gap-2 px-3 py-2 rounded bg-accent text-sm font-medium text-accent-foreground hover:brightness-95 disabled:opacity-70"
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
                          className="min-w-0 flex-1 rounded border border-default bg-surface-elevated px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
                          autoFocus
                        />
                        <button
                          type="button"
                          onClick={() => handleSave(settingsKey.name)}
                          disabled={saving === settingsKey.name}
                          className="bg-accent text-accent-foreground px-4 py-2 rounded hover:brightness-95 disabled:opacity-50"
                        >
                          {saving === settingsKey.name ? "Saving..." : "Save"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(null);
                            setDraftValue("");
                          }}
                          className="bg-surface text-foreground border border-default px-4 py-2 rounded hover:brightness-95"
                        >
                          Cancel
                        </button>
                      </div>
                    )}

                    {testState.status === "ok" && (
                      <p className="mt-3 text-sm font-medium text-success">OK</p>
                    )}
                    {testState.status === "error" && (
                      <p className="mt-3 text-sm font-medium text-danger">
                        X {testState.error}
                      </p>
                    )}
                  </section>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
