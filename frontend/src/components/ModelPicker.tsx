import { useId, useMemo, useState } from "react";
import { computeModelBadges, type ModelInfo, type ProviderModels } from "../api/models";
import { modelOptions } from "../utils/modelSelection";

interface ModelPickerProps {
  /** Visible label and accessible name, e.g. "Image model". */
  label: string;
  provider: ProviderModels | undefined;
  value: string;
  loading?: boolean;
  disabled?: boolean;
  /** Narrow layout: shorter option text, details stacked below. */
  compact?: boolean;
  onChange: (modelId: string) => void;
}

const TIER_LABEL: Record<string, string> = {
  best: "Top quality",
  balanced: "Balanced",
  fast: "Fast & cheap",
  legacy: "Older",
  unknown: "",
};

function qualityDots(quality: number | null): string {
  if (quality == null) return "quality n/a";
  return "●".repeat(quality) + "○".repeat(5 - quality);
}

function costSigns(rank: number | null): string {
  if (rank == null) return "cost n/a";
  return "$".repeat(rank);
}

/** Text inside the native option, so the dropdown itself is comparable. */
function optionLabel(
  m: ModelInfo,
  badges: ReturnType<typeof computeModelBadges>,
  compact: boolean,
): string {
  const parts = [m.display_name];
  if (!compact) parts.push(qualityDots(m.quality), costSigns(m.cost_rank));
  if (m.recommended) parts.push("Recommended");
  else if (badges.bestQualityId === m.id) parts.push("Best quality");
  else if (badges.cheapestId === m.id) parts.push("Cheapest");
  if (!m.current) parts.push("older / snapshot");
  return parts.join(" · ");
}

/**
 * Picks a vendor model with enough context to choose: every model the vendor lists is
 * shown, each option carries quality dots and a cost band, the selected model gets a
 * summary card (price, note, id), and a "Compare" table lays them side by side with
 * Best quality / Cheapest / Recommended badges. Dated snapshots and retired ids are
 * marked "older / snapshot" and can be hidden with one checkbox.
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
  const [hideOlder, setHideOlder] = useState(false);
  const [compare, setCompare] = useState(false);
  const compareId = useId();

  const allOptions = useMemo(() => modelOptions(provider, value), [provider, value]);
  const badges = useMemo(() => computeModelBadges(allOptions), [allOptions]);
  const selected = allOptions.find((m) => m.id === value);
  // Keep the selected model visible even if it is an older one.
  const visible = allOptions.filter((m) => !hideOlder || m.current || m.id === value);
  const olderCount = allOptions.filter((m) => !m.current).length;
  const currentCount = allOptions.length - olderCount;
  const hint = statusHint(provider, loading);

  return (
    <div className="min-w-0 space-y-2">
      <label className="block text-xs font-medium text-foreground">
        <span className="mb-1 flex items-baseline justify-between gap-2">
          <span>{label}</span>
          {provider && (
            <span className="font-normal text-muted">
              {currentCount} current{olderCount > 0 ? ` + ${olderCount} older` : ""}
            </span>
          )}
        </span>
        <select
          aria-label={label}
          value={value}
          disabled={disabled || visible.length === 0}
          onChange={(e) => onChange(e.target.value)}
          className="w-full max-w-full rounded border border-default bg-surface-elevated px-2 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
        >
          {visible.length === 0 && <option value="">No models available</option>}
          {visible.map((m) => (
            <option key={m.id} value={m.id}>
              {optionLabel(m, badges, compact)}
            </option>
          ))}
        </select>
      </label>

      {selected && <SelectedSummary model={selected} badges={badges} />}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <button
          type="button"
          onClick={() => setCompare((v) => !v)}
          aria-expanded={compare}
          aria-controls={compareId}
          className="font-medium text-accent hover:underline"
        >
          {compare ? "Hide comparison" : `Compare ${label.toLowerCase()}s`}
        </button>
        {olderCount > 0 && (
          <label className="flex cursor-pointer items-center gap-1.5 text-muted">
            <input
              type="checkbox"
              checked={hideOlder}
              onChange={(e) => setHideOlder(e.target.checked)}
              className="h-3.5 w-3.5"
            />
            Hide older & snapshot models ({olderCount})
          </label>
        )}
      </div>

      {compare && (
        <ComparisonTable
          id={compareId}
          label={label}
          models={visible}
          badges={badges}
          value={value}
          onChange={onChange}
        />
      )}

      {hint && (
        <p className={`text-[11px] ${hint.tone === "warn" ? "text-danger" : "text-muted"}`}>
          {hint.text}
        </p>
      )}
    </div>
  );
}

function Badge({ children, tone = "accent" }: { children: string; tone?: "accent" | "muted" }) {
  const cls =
    tone === "accent"
      ? "border-accent text-accent"
      : "border-default text-muted";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${cls}`}>
      {children}
    </span>
  );
}

function badgesFor(m: ModelInfo, badges: ReturnType<typeof computeModelBadges>) {
  const out: { text: string; tone: "accent" | "muted" }[] = [];
  if (m.recommended) out.push({ text: "Recommended", tone: "accent" });
  if (badges.bestQualityId === m.id) out.push({ text: "Best quality", tone: "accent" });
  if (badges.cheapestId === m.id) out.push({ text: "Cheapest", tone: "accent" });
  if (!m.current) out.push({ text: "Older / snapshot", tone: "muted" });
  else if (TIER_LABEL[m.tier]) out.push({ text: TIER_LABEL[m.tier], tone: "muted" });
  return out;
}

function SelectedSummary({
  model,
  badges,
}: {
  model: ModelInfo;
  badges: ReturnType<typeof computeModelBadges>;
}) {
  return (
    <div className="rounded border border-default bg-surface px-3 py-2 text-xs" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-foreground">{model.display_name}</span>
        {badgesFor(model, badges).map((b) => (
          <Badge key={b.text} tone={b.tone}>
            {b.text}
          </Badge>
        ))}
      </div>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-muted">
        <dt>Quality</dt>
        <dd className="text-foreground">
          <span aria-hidden="true">{qualityDots(model.quality)}</span>
          <span className="sr-only">
            {model.quality != null ? `${model.quality} of 5` : "unknown"}
          </span>
        </dd>
        <dt>Cost</dt>
        <dd className="text-foreground">{model.cost ?? costSigns(model.cost_rank)}</dd>
        {model.note && (
          <>
            <dt>Note</dt>
            <dd className="text-foreground">{model.note}</dd>
          </>
        )}
        <dt>ID</dt>
        <dd>
          <code className="text-[11px] text-muted">{model.id}</code>
        </dd>
      </dl>
    </div>
  );
}

function ComparisonTable({
  id,
  label,
  models,
  badges,
  value,
  onChange,
}: {
  id: string;
  label: string;
  models: ModelInfo[];
  badges: ReturnType<typeof computeModelBadges>;
  value: string;
  onChange: (modelId: string) => void;
}) {
  return (
    <div id={id} className="overflow-x-auto rounded border border-default">
      <table className="w-full text-left text-xs" aria-label={`${label} comparison`}>
        <thead className="bg-surface text-[11px] uppercase text-muted">
          <tr>
            <th scope="col" className="px-3 py-2">Model</th>
            <th scope="col" className="px-3 py-2">Quality</th>
            <th scope="col" className="px-3 py-2">Cost</th>
            <th scope="col" className="px-3 py-2">Notes</th>
            <th scope="col" className="px-3 py-2">
              <span className="sr-only">Select</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-default">
          {models.map((m) => {
            const isSelected = m.id === value;
            return (
              <tr key={m.id} className={isSelected ? "bg-surface-elevated" : undefined}>
                <td className="px-3 py-2 align-top">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium text-foreground">{m.display_name}</span>
                    {badgesFor(m, badges).map((b) => (
                      <Badge key={b.text} tone={b.tone}>
                        {b.text}
                      </Badge>
                    ))}
                  </div>
                  <code className="text-[11px] text-muted">{m.id}</code>
                </td>
                <td className="px-3 py-2 align-top text-foreground">
                  <span aria-hidden="true">{qualityDots(m.quality)}</span>
                  <span className="sr-only">
                    {m.quality != null ? `${m.quality} of 5` : "unknown"}
                  </span>
                </td>
                <td className="px-3 py-2 align-top text-foreground">
                  {m.cost ?? costSigns(m.cost_rank)}
                </td>
                <td className="px-3 py-2 align-top text-muted">{m.note ?? ""}</td>
                <td className="px-3 py-2 align-top text-right">
                  <button
                    type="button"
                    onClick={() => onChange(m.id)}
                    disabled={isSelected}
                    aria-label={isSelected ? `${m.display_name} selected` : `Use ${m.display_name}`}
                    className="rounded border border-default px-2 py-1 font-medium text-foreground hover:border-accent hover:text-accent disabled:cursor-default disabled:border-accent disabled:text-accent"
                  >
                    {isSelected ? "Selected" : "Use"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
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
