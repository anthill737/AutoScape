import type { FormEvent, MutableRefObject } from "react";
import type { ProviderModels } from "../api/models";
import { IMAGE_PROVIDERS, type DesignRequestOut, type RenderOut } from "../api/designRequests";
import type { SpaceConfig } from "../api/spaces";
import ModelPicker from "./ModelPicker";

export interface IterationSource {
  render: RenderOut;
  dr: DesignRequestOut;
  /** Position label such as "2.1" (Design Request 2, render 1). */
  positionLabel: string;
  requestNumber: number;
}

interface DesignRequestFormProps {
  formRef: MutableRefObject<HTMLFormElement | null>;
  space: SpaceConfig;
  roomType: string | null;
  sitePhotoUrl: string | null;
  /** Null when the new renders start from the site photo. */
  iterationSource: IterationSource | null;
  featureCategories: string[];
  style: string;
  qualityTier: string;
  composedPrompt: string;
  promptIsCustom: boolean;
  imageProvider: string;
  imageProviderEntry: ProviderModels | undefined;
  imageModel: string;
  modelsLoading: boolean;
  submitting: boolean;
  submitError: string | null;
  submitWarning: string | null;
  onToggleCategory: (category: string) => void;
  onStyleChange: (value: string) => void;
  onQualityTierChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onResetPrompt: () => void;
  onImageProviderChange: (value: string) => void;
  onImageModelChange: (modelId: string) => void;
  onUseSitePhoto: () => void;
  onSubmit: (e: FormEvent) => void;
  onCancel: () => void;
}

/**
 * Everything that shapes the next three renders lives here, in one panel, so there is
 * never a question of whether a setting elsewhere on the page applies. Nothing is sent
 * until "Generate Renders" is clicked. Vocabulary (categories, styles) comes from the
 * project's space config, so an interior project offers cabinets and flooring where an
 * outdoor one offers decks and pools.
 */
export default function DesignRequestForm({
  formRef,
  space,
  roomType,
  sitePhotoUrl,
  iterationSource,
  featureCategories,
  style,
  qualityTier,
  composedPrompt,
  promptIsCustom,
  imageProvider,
  imageProviderEntry,
  imageModel,
  modelsLoading,
  submitting,
  submitError,
  submitWarning,
  onToggleCategory,
  onStyleChange,
  onQualityTierChange,
  onPromptChange,
  onResetPrompt,
  onImageProviderChange,
  onImageModelChange,
  onUseSitePhoto,
  onSubmit,
  onCancel,
}: DesignRequestFormProps) {
  const iterating = iterationSource != null;
  const sourceImageUrl = iterating ? iterationSource.render.image_url : sitePhotoUrl;
  const isInterior = space.id === "interior";
  const photoNoun = isInterior ? "room photo" : "site photo";

  return (
    <form
      id="design-request-form"
      ref={formRef}
      onSubmit={onSubmit}
      aria-label={iterating ? "Iterate on a render" : "New design request"}
      className="as-card mb-8 border-accent p-5 sm:p-6"
      tabIndex={-1}
    >
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="as-title">
            {iterating
              ? `Iterate on Render #${iterationSource.render.id}`
              : "New Design Request"}
          </h3>
          <p className="as-help mt-1">
            {iterating
              ? `Settings below were copied from Design Request #${iterationSource.requestNumber}. Change anything, then generate.`
              : "Pick what you want, check the prompt, then generate. Nothing is sent until you click Generate."}
          </p>
        </div>
        <button type="button" onClick={onCancel} disabled={submitting} className="btn-secondary btn-sm">
          Cancel
        </button>
      </div>

      {iterating && (
        <input type="hidden" name="parent_render_id" value={iterationSource.render.id} />
      )}

      {/* Starting image */}
      <section aria-label="Starting image" className="as-well mb-5 flex flex-wrap items-center gap-4 p-3">
        {sourceImageUrl ? (
          <img
            src={sourceImageUrl}
            alt={iterating ? `Render ${iterationSource.positionLabel}` : isInterior ? "Room photo" : "Site photo"}
            className="h-20 w-28 shrink-0 rounded-lg object-cover"
          />
        ) : (
          <div className="flex h-20 w-28 shrink-0 items-center justify-center rounded-lg bg-surface-elevated text-xs text-muted">
            No image
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="as-eyebrow">Starting from</p>
          <p className="mt-0.5 text-sm font-semibold text-foreground">
            {iterating
              ? `Render ${iterationSource.positionLabel} (Design Request #${iterationSource.requestNumber})`
              : `The ${photoNoun}`}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {iterating
              ? "The new renders will edit this render instead of the original photo."
              : `The new renders will edit the original ${photoNoun}.`}
          </p>
        </div>
        {iterating && (
          <button type="button" onClick={onUseSitePhoto} className="text-sm font-medium text-accent hover:underline">
            Start from the {photoNoun} instead
          </button>
        )}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 1 · features */}
        <fieldset className="min-w-0">
          <legend className="as-eyebrow">1 · What to change</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {space.feature_categories.map((category) => {
              const on = featureCategories.includes(category);
              return (
                <label key={category} className={`chip ${on ? "chip-on" : ""}`}>
                  <input
                    type="checkbox"
                    aria-label={category}
                    checked={on}
                    onChange={() => onToggleCategory(category)}
                  />
                  {category}
                </label>
              );
            })}
          </div>
          {featureCategories.length === 0 && (
            <p className="mt-2 text-xs text-muted">
              Nothing selected: the prompt asks for a general {isInterior ? "room" : "outdoor"} design.
            </p>
          )}
        </fieldset>

        {/* 2 + 3 · style, tier */}
        <div className="grid min-w-0 grid-cols-1 gap-6 sm:grid-cols-2">
          <fieldset className="min-w-0">
            <legend className="as-eyebrow">2 · Style</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {space.styles.map((styleOption) => {
                const on = style === styleOption;
                return (
                  <label key={styleOption} className={`chip ${on ? "chip-on" : ""}`}>
                    <input
                      type="radio"
                      name="style"
                      aria-label={styleOption}
                      value={styleOption}
                      checked={on}
                      onChange={() => onStyleChange(styleOption)}
                    />
                    {styleOption}
                  </label>
                );
              })}
            </div>
          </fieldset>

          <fieldset className="min-w-0">
            <legend className="as-eyebrow">3 · Quality tier</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {space.quality_tiers.map((tier) => {
                const on = qualityTier === tier;
                return (
                  <label key={tier} className={`chip ${on ? "chip-on" : ""}`}>
                    <input
                      type="radio"
                      name="qualityTier"
                      aria-label={tier}
                      value={tier}
                      checked={on}
                      onChange={() => onQualityTierChange(tier)}
                    />
                    {tier}
                  </label>
                );
              })}
            </div>
            <p className="mt-2 text-xs text-muted">
              Sets the budget level of materials in the design and build sheet.
            </p>
          </fieldset>
        </div>

        {/* 4 · image model */}
        <fieldset className="min-w-0">
          <legend className="as-eyebrow">4 · Image model</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {IMAGE_PROVIDERS.map((provider) => {
              const on = imageProvider === provider.value;
              return (
                <label key={provider.value} className={`chip ${on ? "chip-on" : ""}`}>
                  <input
                    type="radio"
                    name="imageProvider"
                    aria-label={provider.label}
                    value={provider.value}
                    checked={on}
                    onChange={() => onImageProviderChange(provider.value)}
                  />
                  {provider.label}
                </label>
              );
            })}
          </div>
          <div className="mt-3">
            <ModelPicker
              label="Image model"
              provider={imageProviderEntry}
              value={imageModel}
              loading={modelsLoading}
              onChange={onImageModelChange}
            />
          </div>
        </fieldset>

        {/* 5 · prompt */}
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <label htmlFor="composed-prompt" className="as-eyebrow">
              5 · Prompt
            </label>
            {promptIsCustom ? (
              <button type="button" onClick={onResetPrompt} className="text-xs font-medium text-accent hover:underline">
                Reset to suggested prompt
              </button>
            ) : (
              <span className="text-xs text-muted">Written from your choices; edit freely.</span>
            )}
          </div>
          <textarea
            id="composed-prompt"
            value={composedPrompt}
            onChange={(e) => onPromptChange(e.target.value)}
            rows={6}
            className="field mt-2"
          />
          {promptIsCustom && (
            <p className="mt-1 text-xs text-muted">
              You edited the prompt, so changes to the chips above no longer rewrite it.
            </p>
          )}
          {isInterior && roomType && !promptIsCustom && (
            <p className="mt-1 text-xs text-muted">Room: {roomType}.</p>
          )}
        </div>
      </div>

      {submitWarning && <div className="alert-danger mt-5">{submitWarning}</div>}
      {submitError && <p className="mt-5 text-sm text-danger">{submitError}</p>}

      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-default pt-5">
        <button type="submit" disabled={submitting} className="btn-primary btn-lg">
          {submitting ? "Generating…" : "Generate Renders"}
        </button>
        <span className="text-xs text-muted">
          {submitting
            ? "Editing the image with the model above. This can take a minute."
            : "Makes 3 variations with the settings in this panel."}
        </span>
      </div>
    </form>
  );
}
