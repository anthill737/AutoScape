import type { ProviderModels } from "../api/models";
import { modelOptions } from "../utils/modelSelection";

interface ModelPickerProps {
  /** Visible label and accessible name, e.g. "Image model". */
  label: string;
  provider: ProviderModels | undefined;
  value: string;
  loading?: boolean;
  disabled?: boolean;
  compact?: boolean;
  onChange: (modelId: string) => void;
}

/**
 * Dropdown of the models a provider currently offers, with a one-line status hint
 * (missing key, or a fallback list because the vendor could not be reached).
 */
export default function ModelPicker({
  label,
  provider,
  value,
  loading = false,
  disabled = false,
  compact = false,
  onChange,
}: ModelPickerProps) {
  const options = modelOptions(provider, value);
  const hint = statusHint(provider, loading);

  return (
    <div className={compact ? "min-w-0" : "min-w-0 space-y-1"}>
      <label className="block text-xs font-medium text-foreground">
        <span className={compact ? "sr-only" : "mb-1 block"}>{label}</span>
        <select
          aria-label={label}
          value={value}
          disabled={disabled || options.length === 0}
          onChange={(e) => onChange(e.target.value)}
          className="w-full max-w-full rounded border border-default bg-surface-elevated px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
        >
          {options.length === 0 && <option value="">No models available</option>}
          {options.map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name}
              {m.id !== m.display_name ? ` — ${m.id}` : ""}
            </option>
          ))}
        </select>
      </label>
      {hint && (
        <p className={`text-[11px] ${hint.tone === "warn" ? "text-danger" : "text-muted"}`}>
          {hint.text}
        </p>
      )}
    </div>
  );
}

function statusHint(
  provider: ProviderModels | undefined,
  loading: boolean,
): { text: string; tone: "info" | "warn" } | null {
  if (loading && !provider) return { text: "Loading models…", tone: "info" };
  if (!provider) return null;
  if (!provider.key_set) {
    return { text: `${provider.key_env} not set — add it in Settings.`, tone: "warn" };
  }
  if (provider.source === "fallback") {
    return {
      text: "Showing a built-in list; the vendor's model list could not be loaded.",
      tone: "info",
    };
  }
  return null;
}
