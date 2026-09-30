import { forwardRef, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { getProject, ProjectDetail } from "../api/projects";
import { ApiError } from "../api/errors";
import { findProvider, ModelCatalog, ProviderModels } from "../api/models";
import {
  IMAGE_PROVIDERS,
  STYLES,
  QUALITY_TIERS,
  MATERIALS_LLMS,
  DEFAULT_MATERIALS_LLM,
  DesignRequestOut,
  RenderOut,
  BuildSheetOut,
  MaterialItem,
  BuildStep,
  seedComposedPrompt,
  createDesignRequest,
  chooseRender,
  getDimensionDefaults,
  getDimensionFieldsForCategories,
  getBuildSheet,
  createBuildSheet,
} from "../api/designRequests";
import { exportBuildSheet } from "../utils/exportBuildSheet";
import {
  loadModelSelection,
  resolveSelectedModel,
  saveModelSelection,
} from "../utils/modelSelection";
import { useModelCatalog } from "../hooks/useModelCatalog";
import ModelPicker from "../components/ModelPicker";
import DesignRequestForm, { type IterationSource } from "../components/DesignRequestForm";
import TopNav from "../components/TopNav";

function sortDesignRequestsNewestFirst(
  designRequests: DesignRequestOut[],
): DesignRequestOut[] {
  return [...designRequests].sort((a, b) => {
    const byDate = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    return byDate !== 0 ? byDate : b.id - a.id;
  });
}

function formatImageProvider(value: string): string {
  return IMAGE_PROVIDERS.find((provider) => provider.value === value)?.label ?? value;
}

/** "Google Gemini Images (gemini-3.1-flash-image)" when the model is known. */
function formatImageProviderWithModel(dr: DesignRequestOut): string {
  const label = formatImageProvider(dr.image_provider);
  return dr.image_model ? `${label} (${dr.image_model})` : label;
}

function isKnownImageProvider(value: string | undefined): value is string {
  return !!value && IMAGE_PROVIDERS.some((provider) => provider.value === value);
}

function isKnownMaterialsLlm(value: string | undefined): value is string {
  return !!value && MATERIALS_LLMS.some((llm) => llm.value === value);
}

function formatSubmittedTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const yyyy = date.getUTCFullYear();
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(date.getUTCDate()).padStart(2, "0");
  const hh = String(date.getUTCHours()).padStart(2, "0");
  const min = String(date.getUTCMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${min} UTC`;
}

function getRenderPositionLabel(
  project: ProjectDetail,
  renderId: number,
  requestNumberById: Map<number, number>,
): string {
  for (const dr of project.design_requests) {
    const renderIndex = dr.renders.findIndex((render) => render.id === renderId);
    if (renderIndex !== -1) {
      return `${requestNumberById.get(dr.id) ?? dr.id}.${renderIndex + 1}`;
    }
  }
  return `#${renderId}`;
}

function getMostRecentDesignRequest(
  designRequests: DesignRequestOut[],
): DesignRequestOut | null {
  return (
    [...designRequests].sort((a, b) => {
      const byDate =
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      return byDate !== 0 ? byDate : b.id - a.id;
    })[0] ?? null
  );
}

function findRender(project: ProjectDetail, renderId: number): RenderOut | null {
  for (const dr of project.design_requests) {
    const render = dr.renders.find((r) => r.id === renderId);
    if (render) return render;
  }
  return null;
}

function isBuildSheetOut(value: unknown): value is BuildSheetOut {
  const candidate = value as Partial<BuildSheetOut> | null;
  return (
    candidate != null &&
    typeof candidate.id === "number" &&
    typeof candidate.render_id === "number" &&
    Array.isArray(candidate.material_items) &&
    Array.isArray(candidate.tool_list) &&
    Array.isArray(candidate.build_steps) &&
    Array.isArray(candidate.assumptions)
  );
}

function getDefaultActiveRenderId(project: ProjectDetail): number | null {
  const mostRecent = getMostRecentDesignRequest(project.design_requests);
  if (!mostRecent) return null;
  return (
    mostRecent.renders.find((render) => render.is_chosen)?.id ??
    mostRecent.renders[0]?.id ??
    null
  );
}

interface ActiveRenderContext {
  dr: DesignRequestOut;
  render: RenderOut;
  requestNumber: number;
  renderNumber: number;
}

function getDesignRequestNumberMap(
  designRequests: DesignRequestOut[],
): Map<number, number> {
  return new Map(
    [...designRequests]
      .sort((a, b) => {
        const byDate =
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        return byDate !== 0 ? byDate : a.id - b.id;
      })
      .map((dr, index) => [dr.id, index + 1]),
  );
}

function findActiveRenderContext(
  project: ProjectDetail,
  renderId: number | null,
): ActiveRenderContext | null {
  if (renderId == null) return null;

  const requestNumbers = getDesignRequestNumberMap(project.design_requests);
  for (const dr of project.design_requests) {
    const renderIndex = dr.renders.findIndex((render) => render.id === renderId);
    if (renderIndex >= 0) {
      return {
        dr,
        render: dr.renders[renderIndex],
        requestNumber: requestNumbers.get(dr.id) ?? 1,
        renderNumber: renderIndex + 1,
      };
    }
  }

  return null;
}

function formatFeatureCategories(categories: string[]): string {
  return categories.length > 0 ? categories.join(", ") : "No feature categories";
}

function getHeroLabel(context: ActiveRenderContext): string {
  return [
    `Design Request #${context.requestNumber}`,
    `Render ${context.renderNumber} of ${context.dr.renders.length}`,
    context.dr.style,
    context.dr.quality_tier,
    formatFeatureCategories(context.dr.feature_categories),
    formatImageProviderWithModel(context.dr),
  ].join(" · ");
}

function getRenderBreadcrumb(context: ActiveRenderContext): string {
  return [
    `Design Request #${context.requestNumber}`,
    `Render ${context.renderNumber} of ${context.dr.renders.length}`,
    context.dr.parent_render_id != null
      ? `iteration of Render #${context.dr.parent_render_id}`
      : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

export default function ProjectDetailPage() {
  const { id, renderId } = useParams<{ id: string; renderId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [activeRenderId, setActiveRenderId] = useState<number | null>(null);
  const [expandedDesignRequestIds, setExpandedDesignRequestIds] = useState<Set<number>>(
    () => new Set(),
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Model catalog (what each vendor currently offers) + remembered choices
  const { catalog: modelCatalog, loading: modelsLoading } = useModelCatalog();
  const savedSelectionRef = useRef(loadModelSelection());
  const savedSelection = savedSelectionRef.current;

  // Design Request form state
  const [showForm, setShowForm] = useState(false);
  const [imageProvider, setImageProvider] = useState<string>(
    isKnownImageProvider(savedSelection.imageProvider)
      ? savedSelection.imageProvider
      : IMAGE_PROVIDERS[0].value,
  );
  // Chosen model per provider slug, so switching providers back and forth keeps each pick.
  const [imageModels, setImageModels] = useState<Record<string, string>>(
    savedSelection.imageModels ?? {},
  );
  const [materialsModels, setMaterialsModels] = useState<Record<string, string>>(
    savedSelection.materialsModels ?? {},
  );
  const [groundingModel, setGroundingModel] = useState<string>(
    savedSelection.groundingModel ?? "",
  );
  const [featureCategories, setFeatureCategories] = useState<string[]>([]);
  const [style, setStyle] = useState<string>(STYLES[0]);
  const [qualityTier, setQualityTier] = useState<string>(QUALITY_TIERS[0]);
  const [composedPrompt, setComposedPrompt] = useState<string>("");
  // Once the user edits the prompt we stop rewriting it when chips change.
  const [promptIsCustom, setPromptIsCustom] = useState(false);
  const [iterationParentRenderId, setIterationParentRenderId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitWarning, setSubmitWarning] = useState<string | null>(null);

  // Project Dimensions + Build Sheet state (keyed by chosen render ID)
  const [dimensionValues, setDimensionValues] = useState<Record<number, Record<string, string>>>(
    {},
  );
  const [materialsLlmByRender, setMaterialsLlmByRender] = useState<Record<number, string>>({});
  const defaultMaterialsLlm = isKnownMaterialsLlm(savedSelection.materialsProvider)
    ? savedSelection.materialsProvider
    : DEFAULT_MATERIALS_LLM;

  const imageProviderEntry = findProvider(modelCatalog, imageProvider);
  const imageModel = resolveSelectedModel(imageProviderEntry, imageModels[imageProvider]);
  const groundingProviderEntry: ProviderModels | undefined = modelCatalog.grounding[0];
  const resolvedGroundingModel = resolveSelectedModel(groundingProviderEntry, groundingModel);

  function materialsLlmFor(renderId: number): string {
    return materialsLlmByRender[renderId] ?? defaultMaterialsLlm;
  }

  function materialsModelFor(llm: string): string {
    return resolveSelectedModel(findProvider(modelCatalog, llm), materialsModels[llm]);
  }

  function changeImageProvider(value: string) {
    setImageProvider(value);
    saveModelSelection({ imageProvider: value });
  }

  function changeImageModel(modelId: string) {
    setImageModels((prev) => ({ ...prev, [imageProvider]: modelId }));
    saveModelSelection({ imageModels: { [imageProvider]: modelId } });
  }

  function changeMaterialsLlm(renderId: number, value: string) {
    setMaterialsLlmByRender((prev) => ({ ...prev, [renderId]: value }));
    saveModelSelection({ materialsProvider: value });
  }

  function changeMaterialsModel(llm: string, modelId: string) {
    setMaterialsModels((prev) => ({ ...prev, [llm]: modelId }));
    saveModelSelection({ materialsModels: { [llm]: modelId } });
  }

  function changeGroundingModel(modelId: string) {
    setGroundingModel(modelId);
    saveModelSelection({ groundingModel: modelId });
  }
  const [generatingForRender, setGeneratingForRender] = useState<number | null>(null);
  const [buildSheetErrors, setBuildSheetErrors] = useState<Record<number, string>>({});
  const [buildSheets, setBuildSheets] = useState<Record<number, BuildSheetOut>>({});
  const fetchedDefaultsRef = useRef<Set<number>>(new Set());
  // Per-render status of the auto-fill call so the panel can say what happened.
  const [dimensionStatus, setDimensionStatus] = useState<
    Record<number, { state: "loading" } | { state: "error"; message: string } | { state: "done" }>
  >({});
  // Design Request whose renders were just generated in this session (drives the banner).
  const [justGeneratedRequestId, setJustGeneratedRequestId] = useState<number | null>(null);
  const heroRef = useRef<HTMLElement | null>(null);
  const fetchedBuildSheetsRef = useRef<Set<number>>(new Set());
  const designRequestFormRef = useRef<HTMLFormElement | null>(null);
  const pendingFormFocusRef = useRef(false);

  useEffect(() => {
    if (!id) return;
    getProject(Number(id))
      .then((loadedProject) => {
        const routeRenderId = renderId ? Number(renderId) : null;
        const routeRender =
          routeRenderId != null && Number.isFinite(routeRenderId)
            ? findRender(loadedProject, routeRenderId)
            : null;
        setActiveRenderId(routeRender?.id ?? getDefaultActiveRenderId(loadedProject));
        setProject(loadedProject);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!project) return;

    const routeRenderId = renderId ? Number(renderId) : null;
    const routeRender =
      routeRenderId != null && Number.isFinite(routeRenderId)
        ? findRender(project, routeRenderId)
        : null;
    const defaultRenderId = getDefaultActiveRenderId(project);
    const currentRender =
      activeRenderId != null ? findRender(project, activeRenderId) : null;
    const nextRenderId =
      routeRender?.id ?? (renderId ? defaultRenderId : currentRender?.id ?? defaultRenderId);

    setActiveRenderId((previous) =>
      previous === nextRenderId ? previous : nextRenderId,
    );

    if (!id || nextRenderId == null) return;

    const canonicalPath = `/projects/${id}/renders/${nextRenderId}`;
    if (location.pathname !== canonicalPath) {
      navigate(canonicalPath, { replace: routeRender == null });
    }
  }, [activeRenderId, id, location.pathname, navigate, project, renderId]);

  function loadDimensionDefaults(targetRenderId: number, force = false) {
    if (!force && fetchedDefaultsRef.current.has(targetRenderId)) return;
    fetchedDefaultsRef.current.add(targetRenderId);
    const llm = materialsLlmFor(targetRenderId);
    setDimensionStatus((prev) => ({ ...prev, [targetRenderId]: { state: "loading" } }));
    getDimensionDefaults(targetRenderId, {
      materialsLlm: llm,
      materialsModel: materialsModelFor(llm) || null,
    })
      .then((defaults) => {
        setDimensionValues((prev) => ({
          ...prev,
          [targetRenderId]: {
            ...Object.fromEntries(Object.entries(defaults).map(([k, v]) => [k, String(v)])),
            // Never overwrite something the user already typed.
            ...Object.fromEntries(
              Object.entries(prev[targetRenderId] ?? {}).filter(([, v]) => v.trim() !== ""),
            ),
          },
        }));
        setDimensionStatus((prev) => ({ ...prev, [targetRenderId]: { state: "done" } }));
      })
      .catch((e: unknown) => {
        setDimensionStatus((prev) => ({
          ...prev,
          [targetRenderId]: {
            state: "error",
            message: e instanceof Error ? e.message : "Unknown error",
          },
        }));
      });
  }

  useEffect(() => {
    if (!project || activeRenderId == null || !findRender(project, activeRenderId)) {
      return;
    }
    loadDimensionDefaults(activeRenderId);

    if (!fetchedBuildSheetsRef.current.has(activeRenderId)) {
      fetchedBuildSheetsRef.current.add(activeRenderId);
      getBuildSheet(activeRenderId)
        .then((bs) => {
          if (!isBuildSheetOut(bs)) return;
          setBuildSheets((prev) => ({ ...prev, [activeRenderId]: bs }));
        })
        .catch(() => {
          // No existing Build Sheet yet; that's expected
        });
    }
  }, [activeRenderId, project]);

  // Fetch dimension defaults for any chosen render we haven't fetched yet
  useEffect(() => {
    if (!project) return;
    for (const dr of project.design_requests) {
      const chosen = dr.renders.find((r) => r.is_chosen);
      if (chosen) loadDimensionDefaults(chosen.id);
    }
  }, [project]);

  // Load any persisted Build Sheet for chosen renders (no AI call)
  useEffect(() => {
    if (!project) return;
    for (const dr of project.design_requests) {
      const chosen = dr.renders.find((r) => r.is_chosen);
      if (chosen && !fetchedBuildSheetsRef.current.has(chosen.id)) {
        fetchedBuildSheetsRef.current.add(chosen.id);
        getBuildSheet(chosen.id)
          .then((bs) => {
            if (!isBuildSheetOut(bs)) return;
            setBuildSheets((prev) => ({ ...prev, [chosen.id]: bs }));
          })
          .catch(() => {
            // No existing Build Sheet yet; that's expected
          });
      }
    }
  }, [project]);

  // Re-seed the prompt when chips change, unless the user has taken over the text.
  useEffect(() => {
    if (!promptIsCustom) {
      setComposedPrompt(seedComposedPrompt(featureCategories, style, qualityTier));
    }
  }, [featureCategories, style, qualityTier, promptIsCustom]);

  useEffect(() => {
    if (!showForm || !pendingFormFocusRef.current) return;
    pendingFormFocusRef.current = false;
    const form = designRequestFormRef.current;
    if (!form) return;
    if (typeof form.scrollIntoView === "function") {
      form.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    form.focus({ preventScroll: true });
  }, [showForm, iterationParentRenderId]);

  function openForm() {
    setIterationParentRenderId(null);
    setPromptIsCustom(false);
    setComposedPrompt(seedComposedPrompt(featureCategories, style, qualityTier));
    setSubmitError(null);
    setSubmitWarning(null);
    pendingFormFocusRef.current = true;
    setShowForm(true);
  }

  function openIterateForm(render: RenderOut, dr: DesignRequestOut) {
    if (isKnownImageProvider(dr.image_provider)) {
      setImageProvider(dr.image_provider);
      if (dr.image_model) {
        setImageModels((prev) => ({ ...prev, [dr.image_provider]: dr.image_model as string }));
      }
    }
    setFeatureCategories([...dr.feature_categories]);
    setStyle(dr.style);
    setQualityTier(dr.quality_tier);
    setIterationParentRenderId(render.id);
    // The parent's prompt is kept verbatim; treat it as user-owned text.
    setPromptIsCustom(true);
    setComposedPrompt(dr.composed_prompt);
    setSubmitError(null);
    setSubmitWarning(null);
    pendingFormFocusRef.current = true;
    setShowForm(true);
  }

  function activateRender(nextRenderId: number) {
    setActiveRenderId(nextRenderId);
    if (!id) return;

    const nextPath = `/projects/${id}/renders/${nextRenderId}`;
    window.history.replaceState(window.history.state, "", nextPath);
    navigate(nextPath, { replace: true });
  }

  function switchToSitePhoto() {
    setIterationParentRenderId(null);
    setPromptIsCustom(false);
    setComposedPrompt(seedComposedPrompt(featureCategories, style, qualityTier));
  }

  function editPrompt(value: string) {
    setPromptIsCustom(true);
    setComposedPrompt(value);
  }

  function resetPrompt() {
    setPromptIsCustom(false);
    setComposedPrompt(seedComposedPrompt(featureCategories, style, qualityTier));
  }

  function closeForm() {
    setShowForm(false);
    setIterationParentRenderId(null);
    setPromptIsCustom(false);
  }

  function toggleCategory(cat: string) {
    setFeatureCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat],
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!id) return;
    setSubmitting(true);
    setSubmitError(null);
    setSubmitWarning(null);
    try {
      const dr = await createDesignRequest(Number(id), {
        image_provider: imageProvider,
        image_model: imageModel || null,
        feature_categories: featureCategories,
        style,
        quality_tier: qualityTier,
        composed_prompt: composedPrompt,
        parent_render_id: iterationParentRenderId,
      });
      setProject((prev) =>
        prev ? { ...prev, design_requests: [...prev.design_requests, dr] } : prev,
      );
      setJustGeneratedRequestId(dr.id);
      closeForm();
      window.setTimeout(() => {
        const hero = heroRef.current;
        if (hero && typeof hero.scrollIntoView === "function") {
          hero.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 0);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Unknown error";
      if (e instanceof ApiError && e.status === 429) {
        setSubmitWarning(message);
      } else {
        setSubmitError(message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleChooseRender(renderId: number, drId: number) {
    try {
      const updated = await chooseRender(renderId);
      activateRender(updated.id);
      setProject((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          design_requests: prev.design_requests.map((dr) =>
            dr.id === drId
              ? {
                  ...dr,
                  renders: dr.renders.map((r) => ({
                    ...r,
                    is_chosen: r.id === updated.id,
                  })),
                }
              : dr,
          ),
        };
      });
    } catch {
      // silently ignore — user can retry
    }
  }

  async function handleGenerateBuildSheet(renderId: number) {
    const llm = materialsLlmFor(renderId);
    const dims = dimensionValues[renderId] ?? {};
    setGeneratingForRender(renderId);
    setBuildSheetErrors((prev) => {
      const next = { ...prev };
      delete next[renderId];
      return next;
    });
    try {
      const bs = await createBuildSheet(renderId, llm, dims, {
        materialsModel: materialsModelFor(llm) || null,
        groundingModel: resolvedGroundingModel || null,
      });
      setBuildSheets((prev) => ({ ...prev, [renderId]: bs }));
    } catch (e: unknown) {
      setBuildSheetErrors((prev) => ({
        ...prev,
        [renderId]: e instanceof Error ? e.message : "Unknown error",
      }));
    } finally {
      setGeneratingForRender(null);
    }
  }

  // Clear the displayed Build Sheet so the generation form reappears. The next
  // generate call upserts (replaces) the stored sheet, so this is how a user
  // regenerates an existing sheet (e.g. to refresh material links).
  function handleRegenerateBuildSheet(renderId: number) {
    setBuildSheets((prev) => {
      const next = { ...prev };
      delete next[renderId];
      return next;
    });
    setBuildSheetErrors((prev) => {
      const next = { ...prev };
      delete next[renderId];
      return next;
    });
  }

  const activeContext =
    project != null ? findActiveRenderContext(project, activeRenderId) : null;
  const designRequestNumberById =
    project != null ? getDesignRequestNumberMap(project.design_requests) : new Map<number, number>();
  const designRequestsNewestFirst =
    project != null ? sortDesignRequestsNewestFirst(project.design_requests) : [];
  const iterationSource: IterationSource | null = (() => {
    if (!project || iterationParentRenderId == null) return null;
    const ctx = findActiveRenderContext(project, iterationParentRenderId);
    if (!ctx) return null;
    return {
      render: ctx.render,
      dr: ctx.dr,
      positionLabel: `${ctx.requestNumber}.${ctx.renderNumber}`,
      requestNumber: ctx.requestNumber,
    };
  })();

  useEffect(() => {
    if (!activeContext) return;
    setExpandedDesignRequestIds((previous) => {
      if (previous.has(activeContext.dr.id)) return previous;
      const next = new Set(previous);
      next.add(activeContext.dr.id);
      return next;
    });
  }, [activeContext?.dr.id]);

  function toggleDesignRequestExpanded(designRequestId: number) {
    setExpandedDesignRequestIds((previous) => {
      const next = new Set(previous);
      if (next.has(designRequestId)) {
        next.delete(designRequestId);
      } else {
        next.add(designRequestId);
      }
      return next;
    });
  }

  return (
    <div className="min-h-screen bg-surface text-foreground">
      <TopNav title={project ? project.address : "Loading..."} />

      <main className="mx-auto max-w-none px-4 py-6">
        {loading && <p className="text-muted">Loading project…</p>}
        {error && <p className="text-danger">{error}</p>}

        {project && (
          <>
            <ProjectSummary
              project={project}
              showNewRequestButton={!showForm}
              onNewRequest={openForm}
            />

            {showForm && (
              <DesignRequestForm
                formRef={designRequestFormRef}
                sitePhotoUrl={project.site_photo_url}
                iterationSource={iterationSource}
                featureCategories={featureCategories}
                style={style}
                qualityTier={qualityTier}
                composedPrompt={composedPrompt}
                promptIsCustom={promptIsCustom}
                imageProvider={imageProvider}
                imageProviderEntry={imageProviderEntry}
                imageModel={imageModel}
                modelsLoading={modelsLoading}
                submitting={submitting}
                submitError={submitError}
                submitWarning={submitWarning}
                onToggleCategory={toggleCategory}
                onStyleChange={setStyle}
                onQualityTierChange={setQualityTier}
                onPromptChange={editPrompt}
                onResetPrompt={resetPrompt}
                onImageProviderChange={changeImageProvider}
                onImageModelChange={changeImageModel}
                onUseSitePhoto={switchToSitePhoto}
                onSubmit={handleSubmit}
                onCancel={closeForm}
              />
            )}

            {activeContext && (
              <HeroSection
                ref={heroRef}
                context={activeContext}
                isNewRequest={justGeneratedRequestId === activeContext.dr.id}
                onDismissNew={() => setJustGeneratedRequestId(null)}
                onActivateRender={activateRender}
                dimensionStatus={dimensionStatus[activeContext.render.id] ?? null}
                onRetryDimensions={() => loadDimensionDefaults(activeContext.render.id, true)}
                buildSheet={buildSheets[activeContext.render.id] ?? null}
                dimensionValues={dimensionValues[activeContext.render.id] ?? {}}
                materialsLlm={materialsLlmFor(activeContext.render.id)}
                materialsModel={materialsModelFor(materialsLlmFor(activeContext.render.id))}
                groundingModel={resolvedGroundingModel}
                modelCatalog={modelCatalog}
                modelsLoading={modelsLoading}
                generating={generatingForRender === activeContext.render.id}
                error={buildSheetErrors[activeContext.render.id] ?? null}
                onChoose={() =>
                  handleChooseRender(activeContext.render.id, activeContext.dr.id)
                }
                onIterate={() =>
                  openIterateForm(activeContext.render, activeContext.dr)
                }
                onDimensionChange={(key, value) =>
                  setDimensionValues((prev) => ({
                    ...prev,
                    [activeContext.render.id]: {
                      ...(prev[activeContext.render.id] ?? {}),
                      [key]: value,
                    },
                  }))
                }
                onLlmChange={(value) => changeMaterialsLlm(activeContext.render.id, value)}
                onMaterialsModelChange={(modelId) =>
                  changeMaterialsModel(materialsLlmFor(activeContext.render.id), modelId)
                }
                onGroundingModelChange={changeGroundingModel}
                onGenerateBuildSheet={() =>
                  handleGenerateBuildSheet(activeContext.render.id)
                }
                onRegenerate={() =>
                  handleRegenerateBuildSheet(activeContext.render.id)
                }
              />
            )}

            {/* Design Tree section */}
            <section aria-label="Design Tree">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-foreground">
                  Design Tree
                </h2>
              </div>

              {project.design_requests.length === 0 && !showForm && (
                <p className="text-muted">
                  No design requests yet. Click "New Design Request" above to get
                  started.
                </p>
              )}

              <div className="max-h-[75vh] space-y-4 overflow-y-auto pr-1">
                {designRequestsNewestFirst.map((dr) => (
                  <DesignRequestCard
                    key={dr.id}
                    project={project}
                    dr={dr}
                    requestNumber={designRequestNumberById.get(dr.id) ?? dr.id}
                    activeRenderId={activeRenderId}
                    isExpanded={
                      activeContext?.dr.id === dr.id || expandedDesignRequestIds.has(dr.id)
                    }
                    buildSheets={buildSheets}
                    onActivateRender={activateRender}
                    onChooseRender={(renderId) => handleChooseRender(renderId, dr.id)}
                    onToggleExpanded={() => toggleDesignRequestExpanded(dr.id)}
                  />
                ))}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

type DimensionStatus =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "done" }
  | null;

interface HeroSectionProps {
  context: ActiveRenderContext;
  isNewRequest: boolean;
  onDismissNew: () => void;
  onActivateRender: (renderId: number) => void;
  dimensionStatus: DimensionStatus;
  onRetryDimensions: () => void;
  buildSheet: BuildSheetOut | null;
  dimensionValues: Record<string, string>;
  materialsLlm: string;
  materialsModel: string;
  groundingModel: string;
  modelCatalog: ModelCatalog;
  modelsLoading: boolean;
  generating: boolean;
  error: string | null;
  onChoose: () => void;
  onIterate: () => void;
  onDimensionChange: (key: string, value: string) => void;
  onLlmChange: (value: string) => void;
  onMaterialsModelChange: (modelId: string) => void;
  onGroundingModelChange: (modelId: string) => void;
  onGenerateBuildSheet: () => void;
  onRegenerate: () => void;
}

const HeroSection = forwardRef<HTMLElement, HeroSectionProps>(function HeroSection(
  {
  context,
  isNewRequest,
  onDismissNew,
  onActivateRender,
  dimensionStatus,
  onRetryDimensions,
  buildSheet,
  dimensionValues,
  materialsLlm,
  materialsModel,
  groundingModel,
  modelCatalog,
  modelsLoading,
  generating,
  error,
  onChoose,
  onIterate,
  onDimensionChange,
  onLlmChange,
  onMaterialsModelChange,
  onGroundingModelChange,
  onGenerateBuildSheet,
  onRegenerate,
  },
  ref,
) {
  const [imageLoaded, setImageLoaded] = useState(false);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);
  const retryCountRef = useRef(0);
  const imageUrl = context.render.image_url;
  const buildSheetTargetId = buildSheet
    ? `build-sheet-render-${context.render.id}`
    : `dimensions-render-${context.render.id}`;

  // Append a cache-busting param on retries so the browser refetches instead of
  // reusing a failed response.
  const displayedImageUrl =
    imageUrl && retryNonce > 0 ? `${imageUrl}${imageUrl.includes("?") ? "&" : "?"}r=${retryNonce}` : imageUrl;

  useEffect(() => {
    setImageLoaded(false);
    setImageFailed(false);
    setRetryNonce(0);
    retryCountRef.current = 0;
    // A cached image can finish before onLoad is wired up; check it directly.
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth > 0) {
      setImageLoaded(true);
    }
  }, [context.render.id, imageUrl]);

  function handleImageError() {
    // The backend can intermittently drop an image request; auto-retry a few
    // times before giving the user a manual retry control.
    if (retryCountRef.current < 3) {
      retryCountRef.current += 1;
      window.setTimeout(() => setRetryNonce((n) => n + 1), 400 * retryCountRef.current);
    } else {
      setImageFailed(true);
    }
  }

  function handleManualRetry() {
    retryCountRef.current = 0;
    setImageFailed(false);
    setImageLoaded(false);
    setRetryNonce((n) => n + 1);
  }

  function focusBuildSheetArea() {
    const target = document.getElementById(buildSheetTargetId);
    if (!target) return;
    if (typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    target.focus({ preventScroll: true });
  }

  return (
    <section ref={ref} aria-label="Active render hero" className="mb-8 scroll-mt-4">
      {isNewRequest && (
        <div
          role="status"
          className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded border border-accent bg-surface-elevated px-4 py-3 text-sm"
        >
          <p className="text-foreground">
            <span className="font-semibold">
              {context.dr.renders.length} new renders from Design Request #{context.requestNumber}.
            </span>{" "}
            You are viewing {context.requestNumber}.{context.renderNumber}. Click a thumbnail
            below the image to compare, then choose the one you like.
          </p>
          <button
            type="button"
            onClick={onDismissNew}
            className="text-xs font-medium text-muted hover:text-foreground"
          >
            Dismiss
          </button>
        </div>
      )}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold text-foreground">
          {getRenderBreadcrumb(context)}
        </p>
        {context.render.is_chosen && (
          <span className="rounded-full bg-accent px-2.5 py-1 text-xs font-semibold text-accent-foreground shadow-sm">
            Chosen
          </span>
        )}
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(60vw,1fr)_minmax(320px,380px)]">
        <div className="min-w-0">
          <div className="flex h-[62vh] min-h-[520px] items-center justify-center overflow-hidden rounded border border-default bg-surface shadow-sm max-lg:h-[52vh] max-lg:min-h-[360px] lg:min-w-[60vw]">
          {imageUrl ? (
            <div className="relative h-full w-full">
              {!imageLoaded && !imageFailed && (
                <div
                  aria-label="Loading active render"
                  className="absolute inset-0 flex items-center justify-center bg-surface-elevated"
                >
                  <span className="animate-pulse rounded-full border border-default px-3 py-1 text-xs font-medium text-muted">
                    Loading render…
                  </span>
                </div>
              )}
              {imageFailed ? (
                <div className="flex h-full w-full flex-col items-center justify-center gap-3 text-center">
                  <p className="text-sm font-medium text-muted">Image didn’t load.</p>
                  <button
                    type="button"
                    onClick={handleManualRetry}
                    className="rounded-lg border border-default px-4 py-2 text-sm font-semibold text-accent transition hover:border-accent"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <img
                  key={`${context.render.id}-${retryNonce}`}
                  ref={imgRef}
                  src={displayedImageUrl ?? undefined}
                  alt="Active render preview"
                  onLoad={() => setImageLoaded(true)}
                  onError={handleImageError}
                  className={`relative h-full w-full object-contain transition-opacity duration-150 ${
                    imageLoaded ? "opacity-100" : "opacity-0"
                  }`}
                />
              )}
            </div>
          ) : (
            <div className="flex h-full w-full items-center justify-center text-sm font-medium text-muted">
              No render image available
            </div>
          )}
          </div>

          {context.dr.renders.length > 1 && (
            <nav
              aria-label="Renders in this design request"
              className="mt-3 flex flex-wrap gap-3"
            >
              {context.dr.renders.map((sibling, index) => {
                const label = `${context.requestNumber}.${index + 1}`;
                const isCurrent = sibling.id === context.render.id;
                return (
                  <button
                    key={sibling.id}
                    type="button"
                    onClick={() => onActivateRender(sibling.id)}
                    aria-current={isCurrent ? "true" : undefined}
                    aria-label={`View Render ${label}${sibling.is_chosen ? " (chosen)" : ""}`}
                    className={`relative h-20 w-28 overflow-hidden rounded border-2 bg-surface transition ${
                      isCurrent
                        ? "border-accent ring-2 ring-accent/40"
                        : "border-default hover:border-accent"
                    }`}
                  >
                    {sibling.image_url && (
                      <img
                        src={sibling.image_url}
                        alt=""
                        className="h-full w-full object-cover"
                      />
                    )}
                    <span className="absolute bottom-1 left-1 rounded bg-surface-elevated/90 px-1.5 py-0.5 text-[11px] font-semibold text-foreground">
                      {label}
                    </span>
                    {sibling.is_chosen && (
                      <span
                        aria-hidden="true"
                        title="Chosen render"
                        className="absolute right-1 top-1 rounded-full bg-accent px-1.5 py-0.5 text-[10px] font-bold text-accent-foreground"
                      >
                        ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
          )}
        </div>

        <aside className="rounded border border-default bg-surface-elevated p-4 shadow-sm">
          <div className="mb-4 space-y-2">
            <p className="text-xs font-semibold uppercase text-muted">
              Active Render
            </p>
            <p className="text-sm font-medium text-foreground">
              {getHeroLabel(context)}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onChoose}
                disabled={context.render.is_chosen}
                className="rounded bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:bg-border disabled:text-muted"
              >
                Choose this Render
              </button>
              <button
                type="button"
                onClick={onIterate}
                className="rounded border border-default bg-surface-elevated px-4 py-2 text-sm font-semibold text-foreground hover:border-accent hover:text-accent"
              >
                Iterate from this Render
              </button>
              {context.render.is_chosen && (
                <a
                  href={`#${buildSheetTargetId}`}
                  onClick={() => {
                    window.setTimeout(focusBuildSheetArea, 0);
                  }}
                  className="rounded border border-accent bg-surface px-4 py-2 text-sm font-semibold text-accent hover:bg-surface-elevated"
                >
                  Build Sheet
                </a>
              )}
              {imageUrl && (
                <a
                  href={imageUrl}
                  download
                  className="rounded border border-default bg-surface-elevated px-4 py-2 text-sm font-semibold text-foreground hover:border-accent hover:text-accent"
                >
                  Download image
                </a>
              )}
            </div>
          </div>
        </aside>
      </div>

      <ProjectDimensionsPanel
        dr={context.dr}
        chosenRenderId={context.render.id}
        dimensionStatus={dimensionStatus}
        onRetryDimensions={onRetryDimensions}
        dimensionValues={dimensionValues}
        materialsLlm={materialsLlm}
        materialsModel={materialsModel}
        groundingModel={groundingModel}
        modelCatalog={modelCatalog}
        modelsLoading={modelsLoading}
        generating={generating}
        error={error}
        buildSheet={buildSheet}
        onDimensionChange={onDimensionChange}
        onLlmChange={onLlmChange}
        onMaterialsModelChange={onMaterialsModelChange}
        onGroundingModelChange={onGroundingModelChange}
        onGenerate={onGenerateBuildSheet}
      />

      {buildSheet && (
        <div
          id={`build-sheet-render-${context.render.id}`}
          tabIndex={-1}
          className="mt-12 scroll-mt-6 border-t border-default pt-10 focus:outline-none"
        >
          <div className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
            <h2 className="text-2xl font-bold tracking-tight text-foreground">Build Sheet</h2>
            <div className="flex items-center gap-3">
              <p className="text-sm text-muted">{getHeroLabel(context)}</p>
              <button
                type="button"
                onClick={onRegenerate}
                className="rounded-lg border border-default px-3 py-1.5 text-sm font-semibold text-foreground transition hover:border-accent hover:text-accent"
              >
                Regenerate
              </button>
            </div>
          </div>
          <BuildSheetDisplay buildSheet={buildSheet} renderImageUrl={context.render.image_url ?? null} />
        </div>
      )}
    </section>
  );
});

interface ProjectSummaryProps {
  project: ProjectDetail;
  showNewRequestButton: boolean;
  onNewRequest: () => void;
}

function ProjectSummary({ project, showNewRequestButton, onNewRequest }: ProjectSummaryProps) {
  return (
    <section
      aria-label="Project summary"
      className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded border border-default bg-surface-elevated p-3 shadow-sm"
    >
      <div className="flex min-w-0 items-center gap-3">
        {project.site_photo_url ? (
          <img
            src={project.site_photo_url}
            alt="Site Photo"
            className="h-16 w-24 shrink-0 rounded bg-surface object-contain"
          />
        ) : (
          <div className="flex h-16 w-24 shrink-0 items-center justify-center rounded bg-surface text-center text-xs font-medium text-muted">
            No Site Photo
          </div>
        )}
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground">{project.address}</p>
          <p className="mt-1 text-xs text-muted">
            Lot{" "}
            <span className="font-medium text-foreground">
              {project.lot_size_sqft != null
                ? `${project.lot_size_sqft.toLocaleString()} sqft`
                : "Not set"}
            </span>
            <span className="mx-2 text-border">|</span>
            House{" "}
            <span className="font-medium text-foreground">
              {project.house_sqft != null
                ? `${project.house_sqft.toLocaleString()} sqft`
                : "Not set"}
            </span>
            <span className="mx-2 text-border">|</span>
            {project.design_requests.length} design request
            {project.design_requests.length === 1 ? "" : "s"}
          </p>
        </div>
      </div>
      {showNewRequestButton && (
        <button
          type="button"
          onClick={onNewRequest}
          className="rounded bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground hover:opacity-90"
        >
          New Design Request
        </button>
      )}
    </section>
  );
}

interface DesignRequestCardProps {
  project: ProjectDetail;
  dr: DesignRequestOut;
  requestNumber: number;
  activeRenderId: number | null;
  isExpanded: boolean;
  buildSheets: Record<number, BuildSheetOut>;
  onActivateRender: (renderId: number) => void;
  onChooseRender: (renderId: number) => void;
  onToggleExpanded: () => void;
}

function DesignRequestCard({
  project,
  dr,
  requestNumber,
  activeRenderId,
  isExpanded,
  buildSheets,
  onActivateRender,
  onChooseRender,
  onToggleExpanded,
}: DesignRequestCardProps) {
  const requestNumbers = getDesignRequestNumberMap(project.design_requests);
  const chosenRender = dr.renders.find((render) => render.is_chosen) ?? null;
  const activeRenderInRequest = dr.renders.find((render) => render.id === activeRenderId) ?? null;
  const stripRender = activeRenderInRequest ?? chosenRender ?? dr.renders[0] ?? null;
  const hasActiveRender = activeRenderInRequest != null;
  const parentLabel =
    dr.parent_render_id != null
      ? getRenderPositionLabel(project, dr.parent_render_id, requestNumbers)
      : null;

  if (!isExpanded) {
    return (
      <article className="overflow-hidden rounded border border-default bg-surface-elevated shadow-sm">
        <div className="flex w-full items-center gap-4 p-3">
          {stripRender ? (
            <button
              type="button"
              role="link"
              {...{ href: `/projects/${project.id}/renders/${stripRender.id}` }}
              aria-label={`Open Render ${stripRender.id}`}
              className="block h-20 w-28 shrink-0 overflow-hidden rounded bg-surface focus:outline-none focus:ring-2 focus:ring-accent"
              onClick={(event) => {
                event.preventDefault();
                onActivateRender(stripRender.id);
              }}
            >
              {stripRender.image_url ? (
                <img
                  src={stripRender.image_url}
                  alt={`Design Request ${requestNumber} preview`}
                  className="h-full w-full object-contain"
                  loading="lazy"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-xs font-medium text-muted">
                  No image
                </div>
              )}
            </button>
          ) : (
            <div className="flex h-20 w-28 shrink-0 items-center justify-center rounded bg-surface text-xs font-medium text-muted">
              No image
            </div>
          )}

          <button
            type="button"
            onClick={onToggleExpanded}
            className="min-w-0 flex-1 text-left transition hover:text-accent focus:outline-none focus:ring-2 focus:ring-accent"
            aria-expanded={false}
          >
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold text-foreground">
                Design Request #{requestNumber}
              </h3>
              {chosenRender && (
                <span className="rounded-full bg-accent px-2 py-0.5 text-xs font-semibold text-accent-foreground">
                  Chosen Render
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-muted">
              Submitted {formatSubmittedTimestamp(dr.created_at)}
            </p>
            <p className="mt-1 truncate text-sm text-foreground">
              {dr.style} · {dr.quality_tier} ·{" "}
              {dr.feature_categories.join(", ") || "No categories"}
            </p>
            {dr.parent_render_id != null && (
              <p className="mt-1 text-xs font-semibold text-accent">
                Iteration of Render #{dr.parent_render_id}
              </p>
            )}
          </button>

          <div className="hidden shrink-0 items-center gap-1 sm:flex">
            {dr.renders.map((render, index) => (
              <button
                key={render.id}
                type="button"
                role="link"
                {...{ href: `/projects/${project.id}/renders/${render.id}` }}
                aria-label={`Open Render ${render.id}`}
                className="rounded border border-default bg-surface-elevated px-2 py-1 text-xs font-semibold text-foreground hover:border-accent hover:text-accent focus:outline-none focus:ring-2 focus:ring-accent"
                onClick={(event) => {
                  event.preventDefault();
                  onActivateRender(render.id);
                }}
              >
                R{index + 1}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={onToggleExpanded}
            className="shrink-0 text-sm font-semibold text-accent hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-accent"
            aria-expanded={false}
          >
            Expand
          </button>
        </div>
      </article>
    );
  }

  return (
    <article
      className={`rounded border bg-surface-elevated p-4 shadow-sm ${
        hasActiveRender ? "border-accent" : "border-default"
      }`}
    >
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">
              Design Request #{requestNumber}
            </h3>
            {hasActiveRender && (
              <span className="rounded-full border border-accent bg-surface px-2 py-0.5 text-xs font-semibold text-accent">
                Active Request
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-muted">
            Submitted {formatSubmittedTimestamp(dr.created_at)}
          </p>
          {dr.parent_render_id != null && (
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs font-semibold text-accent">
              <span>Iteration from Render #{dr.parent_render_id}</span>
              <button
                type="button"
                onClick={() => onActivateRender(dr.parent_render_id!)}
                className="rounded border border-accent bg-surface px-2 py-1 hover:bg-surface-elevated"
              >
                parent: Render {parentLabel}
              </button>
            </div>
          )}
        </div>

        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 lg:min-w-[560px] lg:grid-cols-4">
          <div>
            <dt className="text-xs font-semibold uppercase text-muted">
              Style
            </dt>
            <dd className="text-foreground">{dr.style}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase text-muted">
              Feature Categories
            </dt>
            <dd className="text-foreground">
              {dr.feature_categories.join(", ") || "No categories"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase text-muted">
              Quality Tier
            </dt>
            <dd className="text-foreground">{dr.quality_tier}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase text-muted">
              Image Provider
            </dt>
            <dd className="text-foreground">
              {formatImageProviderWithModel(dr)}
            </dd>
          </div>
        </dl>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {dr.renders.map((render, index) => (
          <RenderCard
            key={render.id}
            projectId={project.id}
            render={render}
            requestNumber={requestNumber}
            renderNumber={index + 1}
            isActive={activeRenderId === render.id}
            buildSheet={buildSheets[render.id] ?? null}
            onActivate={() => onActivateRender(render.id)}
            onChoose={() => onChooseRender(render.id)}
          />
        ))}
      </div>
    </article>
  );
}

interface RenderCardProps {
  projectId: number;
  render: RenderOut;
  requestNumber: number;
  renderNumber: number;
  isActive: boolean;
  buildSheet: BuildSheetOut | null;
  onActivate: () => void;
  onChoose: () => void;
}

function RenderCard({
  projectId,
  render,
  requestNumber,
  renderNumber,
  isActive,
  buildSheet,
  onActivate,
  onChoose,
}: RenderCardProps) {
  const thumbnailHref = `/projects/${projectId}/renders/${render.id}`;
  const thumbnailLabel = `Open Render ${render.id}`;
  const borderClass = render.is_chosen
    ? "border-accent"
    : "border-default";
  const activeClass = isActive
    ? "ring-4 ring-accent ring-offset-2 ring-offset-surface"
    : "hover:border-accent";

  return (
    <div
      aria-current={isActive ? "true" : undefined}
      className={`min-w-0 overflow-hidden rounded border-2 bg-surface-elevated transition ${borderClass} ${activeClass} ${
        render.is_chosen ? "shadow-sm" : ""
      }`}
    >
      <button
        type="button"
        role="link"
        {...{ href: thumbnailHref }}
        aria-label={thumbnailLabel}
        className="block w-full bg-transparent p-0 text-left focus:outline-none"
        onClick={(event) => {
          event.preventDefault();
          onActivate();
        }}
      >
        {render.image_url ? (
          <div className="relative h-[132px] w-full bg-surface lg:h-[180px]">
            <img
              src={render.image_url}
              alt={`Render ${requestNumber}.${renderNumber}`}
              loading="lazy"
              className="h-full w-full object-contain focus-visible:ring-2 focus-visible:ring-accent"
            />
            <span className="absolute left-2 bottom-2 rounded border border-default bg-surface-elevated px-2 py-0.5 text-xs font-semibold text-foreground shadow-sm">
              Render {requestNumber}.{renderNumber}
            </span>
            {render.is_chosen && (
            <span className="absolute left-2 top-2 rounded-full bg-accent px-2 py-0.5 text-xs font-semibold text-accent-foreground shadow-sm">
                Chosen render
              </span>
            )}
            {render.is_chosen && buildSheet && (
              <span
                title={`Build Sheet exists for Render ${requestNumber}.${renderNumber}`}
                className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-surface-elevated text-accent shadow"
              >
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                >
                  <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z" />
                  <path d="M14 2v5h5" />
                  <path d="M9 13h6" />
                  <path d="M9 17h6" />
                  <path d="M9 9h1" />
                </svg>
                <span className="sr-only">
                  Build Sheet exists for Render {requestNumber}.{renderNumber}
                </span>
              </span>
            )}
          </div>
        ) : (
          <div className="flex h-[132px] w-full items-center justify-center bg-surface lg:h-[180px]">
            <span className="text-muted text-sm">No image</span>
          </div>
        )}
      </button>
      <div className="p-2 space-y-1">
        {isActive && (
          <span className="text-accent font-medium text-sm block">
            Active
          </span>
        )}
        {render.is_chosen && (
          <span className="text-accent font-medium text-sm block">
            Chosen render
          </span>
        )}
        {!render.is_chosen && (
          <button
            type="button"
            onClick={onChoose}
            className="mt-2 w-full rounded bg-accent px-3 py-1.5 text-sm font-semibold text-accent-foreground hover:opacity-90"
          >
            Choose
          </button>
        )}
      </div>
    </div>
  );
}

interface ProjectDimensionsPanelProps {
  dr: DesignRequestOut;
  chosenRenderId: number;
  dimensionStatus: DimensionStatus;
  onRetryDimensions: () => void;
  dimensionValues: Record<string, string>;
  materialsLlm: string;
  materialsModel: string;
  groundingModel: string;
  modelCatalog: ModelCatalog;
  modelsLoading: boolean;
  generating: boolean;
  error: string | null;
  buildSheet: BuildSheetOut | null;
  onDimensionChange: (key: string, value: string) => void;
  onLlmChange: (value: string) => void;
  onMaterialsModelChange: (modelId: string) => void;
  onGroundingModelChange: (modelId: string) => void;
  onGenerate: () => void;
}

function ProjectDimensionsPanel({
  dr,
  chosenRenderId,
  dimensionStatus,
  onRetryDimensions,
  dimensionValues,
  materialsLlm,
  materialsModel,
  groundingModel,
  modelCatalog,
  modelsLoading,
  generating,
  error,
  buildSheet,
  onDimensionChange,
  onLlmChange,
  onMaterialsModelChange,
  onGroundingModelChange,
  onGenerate,
}: ProjectDimensionsPanelProps) {
  const materialsProviderEntry = findProvider(modelCatalog, materialsLlm);
  const groundingProviderEntry = modelCatalog.grounding[0];
  const fields = getDimensionFieldsForCategories(dr.feature_categories);
  const missing = fields.filter((f) => (dimensionValues[f.key] ?? "").trim() === "");
  const allFilled = missing.length === 0;

  // Once a build sheet exists it is rendered below (see HeroSection); this setup panel
  // is replaced by it.
  if (buildSheet) {
    return null;
  }

  return (
    <section
      id={`dimensions-render-${chosenRenderId}`}
      aria-label="Build sheet setup"
      className="mt-8 rounded-lg border border-default bg-surface-elevated p-5 shadow-sm sm:p-6"
      tabIndex={-1}
    >
      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Build Sheet for this render</h3>
          <p className="mt-1 text-sm text-muted">
            Confirm the dimensions, pick the models, then generate a materials list, tool list,
            build steps, and cost range.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {/* Dimensions */}
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">
              Project Dimensions
            </h4>
            {fields.length > 0 && dimensionStatus?.state === "loading" && (
              <p role="status" className="text-xs text-muted">
                <span className="animate-pulse">Auto-filling dimensions from the render…</span>
              </p>
            )}
            {fields.length > 0 && dimensionStatus?.state === "done" && (
              <p className="text-xs text-muted">
                Auto-filled from the render; adjust anything that looks off.
              </p>
            )}
          </div>

          {fields.length > 0 && dimensionStatus?.state === "error" && (
            <div role="alert" className="mb-3 rounded border border-danger bg-surface px-3 py-2 text-xs">
              <p className="text-danger">Couldn't auto-fill dimensions: {dimensionStatus.message}</p>
              <button
                type="button"
                onClick={onRetryDimensions}
                className="mt-1 font-medium text-accent hover:underline"
              >
                Try again
              </button>
              <span className="text-muted"> or type them in below.</span>
            </div>
          )}

          {fields.length > 0 ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {fields.map((field) => (
                <div key={field.key}>
                  <label
                    htmlFor={`dim-${chosenRenderId}-${field.key}`}
                    className="mb-1 block text-xs font-medium text-foreground"
                  >
                    {field.label}
                  </label>
                  <input
                    id={`dim-${chosenRenderId}-${field.key}`}
                    type="number"
                    min="0"
                    step="0.5"
                    aria-label={field.label}
                    value={dimensionValues[field.key] ?? ""}
                    onChange={(e) => onDimensionChange(field.key, e.target.value)}
                    className="w-full rounded border border-default bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
                  />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">
              No measurements needed for {formatFeatureCategories(dr.feature_categories)}.
            </p>
          )}
        </div>

        {/* Models */}
        <div className="min-w-0 space-y-5">
          <fieldset>
            <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
              Materials LLM
            </legend>
            <div className="flex flex-wrap gap-2">
              {MATERIALS_LLMS.map((opt) => {
                const on = materialsLlm === opt.value;
                return (
                  <label
                    key={opt.value}
                    className={`flex cursor-pointer select-none items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition ${
                      on
                        ? "border-accent bg-surface text-foreground"
                        : "border-default bg-surface-elevated text-foreground hover:border-accent"
                    }`}
                  >
                    <input
                      type="radio"
                      name={`materialsLlm-${chosenRenderId}`}
                      value={opt.value}
                      checked={on}
                      onChange={() => onLlmChange(opt.value)}
                      className="h-3.5 w-3.5"
                    />
                    {opt.label}
                  </label>
                );
              })}
            </div>
            <div className="mt-3">
              <ModelPicker
                label="Materials model"
                provider={materialsProviderEntry}
                value={materialsModel}
                loading={modelsLoading}
                onChange={onMaterialsModelChange}
              />
            </div>
          </fieldset>

          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
              Product research
            </h4>
            <ModelPicker
              label="Product research model"
              provider={groundingProviderEntry}
              value={groundingModel}
              loading={modelsLoading}
              onChange={onGroundingModelChange}
            />
          </div>
        </div>
      </div>

      {error && <p className="mt-5 text-sm text-danger">{error}</p>}

      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-default pt-5">
        <button
          disabled={!allFilled || generating}
          onClick={onGenerate}
          className="rounded bg-accent px-5 py-2.5 text-sm font-semibold text-accent-foreground hover:opacity-90 disabled:opacity-50"
        >
          {generating ? "Generating Build Sheet…" : "Generate Build Sheet"}
        </button>
        <span className="text-xs text-muted">
          {generating
            ? "Researching products and pricing the materials. This takes about a minute."
            : allFilled
              ? "Runs product research, then prices every material for this design."
              : `Fill in ${missing.length} more dimension${missing.length === 1 ? "" : "s"} to enable.`}
        </span>
      </div>
    </section>
  );
}

/* ---- Small inline icons (no icon-library dependency) ---- */
function Icon({ path, className = "h-4 w-4" }: { path: string; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}
const ICON = {
  clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  wrench:
    "M14.7 6.3a4 4 0 0 0-5.4 5.2L4 17l3 3 5.5-5.3a4 4 0 0 0 5.2-5.4l-2.3 2.3-2.1-.6-.6-2.1 2.3-2.3Z",
  external: "M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5",
  download: "M12 3v12m0 0 4-4m-4 4-4-4M4 21h16",
  info: "M12 16v-5m0-3h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  alert: "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
  layers: "M12 3 3 8l9 5 9-5-9-5ZM3 13l9 5 9-5M3 18l9 5 9-5",
  spark: "M12 3v4m0 10v4m9-9h-4M7 12H3m13.5-6.5-2.8 2.8M9.3 14.7l-2.8 2.8m11 0-2.8-2.8M9.3 9.3 6.5 6.5",
};

interface ExcludedMaterial {
  label: string;
  url: string | null;
  reason: string;
}

/** Split backend assumptions into real assumptions vs dropped-material notes. */
function partitionAssumptions(assumptions: string[]): {
  kept: string[];
  excluded: ExcludedMaterial[];
} {
  const kept: string[] = [];
  const excluded: ExcludedMaterial[] = [];
  for (const raw of assumptions) {
    const a = raw.trim();
    const isDrop = /failed validation/i.test(a) || /^dropped\b/i.test(a);
    if (!isDrop) {
      kept.push(a);
      continue;
    }
    const urlMatch = a.match(/https?:\/\/\S+/);
    let url = urlMatch ? urlMatch[0].replace(/[.,;]+$/, "") : null;
    // Label = text before "— candidate URL" / "candidate URL", minus a leading "Dropped".
    let label = a
      .replace(/^dropped\s+/i, "")
      .split(/—?\s*candidate url/i)[0]
      .trim();
    if (!label) label = a;
    const reasonMatch = a.match(/failed validation:\s*(.+?)\s*$/i);
    const reason = reasonMatch ? reasonMatch[1].replace(/\.$/, "") : "Link was a search/category page";
    excluded.push({ label, url, reason });
  }
  return { kept, excluded };
}

function BuildSheetDisplay({
  buildSheet,
  renderImageUrl,
}: {
  buildSheet: BuildSheetOut;
  renderImageUrl: string | null;
}) {
  const [exporting, setExporting] = useState(false);
  const { kept: assumptions, excluded } = partitionAssumptions(buildSheet.assumptions);

  async function handleExport() {
    setExporting(true);
    try {
      await exportBuildSheet(buildSheet, renderImageUrl);
    } finally {
      setExporting(false);
    }
  }

  const hasMaterials = buildSheet.material_items.length > 0;
  const stats = [
    { label: "Materials", value: buildSheet.material_items.length },
    { label: "Build steps", value: buildSheet.build_steps.length },
    { label: "Tools", value: buildSheet.tool_list.length },
  ];

  return (
    <div className="space-y-8">
      {/* ───────────── Cost / skill banner ───────────── */}
      <div
        className="as-fade-up relative overflow-hidden rounded-2xl border border-default bg-surface-elevated shadow-sm"
        style={{ animationDelay: "0ms" }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 140% at 0% 0%, color-mix(in srgb, var(--color-accent) 14%, transparent), transparent 55%)",
          }}
        />
        <div className="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-wrap items-end gap-x-10 gap-y-6">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
                Total estimated cost
              </p>
              <p className="mt-1 text-4xl font-bold tracking-tight text-foreground [font-variant-numeric:tabular-nums]">
                {buildSheet.total_cost_range || "—"}
              </p>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
                Skill level
              </span>
              <span
                className="inline-flex w-fit items-center gap-1.5 rounded-full border border-accent px-3 py-1 text-sm font-semibold text-accent"
                style={{ background: "color-mix(in srgb, var(--color-accent) 10%, transparent)" }}
              >
                <Icon path={ICON.spark} className="h-3.5 w-3.5" />
                {buildSheet.skill_level || "—"}
              </span>
            </div>
            <div className="flex gap-6">
              {stats.map((s) => (
                <div key={s.label}>
                  <p className="text-2xl font-semibold text-foreground [font-variant-numeric:tabular-nums]">
                    {s.value}
                  </p>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted">
                    {s.label}
                  </p>
                </div>
              ))}
            </div>
          </div>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-accent-foreground shadow-sm transition hover:opacity-90 disabled:opacity-50"
          >
            <Icon path={ICON.download} className="h-4 w-4" />
            {exporting ? "Exporting…" : "Export build sheet"}
          </button>
        </div>
      </div>

      {/* ───────────── Steps (wide) + side rail ───────────── */}
      <div className="grid gap-8 lg:grid-cols-[1.6fr_1fr]">
        {/* Build steps — vertical timeline */}
        {buildSheet.build_steps.length > 0 && (
          <section className="as-fade-up" style={{ animationDelay: "80ms" }}>
            <h3 className="mb-5 flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
              <Icon path={ICON.layers} className="h-5 w-5 text-accent" />
              Build instructions
            </h3>
            <ol className="relative">
              {buildSheet.build_steps.map((step: BuildStep, i: number) => {
                const last = i === buildSheet.build_steps.length - 1;
                return (
                  <li key={i} className="flex gap-4 pb-6 last:pb-0">
                    {/* rail */}
                    <div className="flex flex-col items-center">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-bold text-accent-foreground shadow-sm [font-variant-numeric:tabular-nums]">
                        {step.step_number ?? i + 1}
                      </span>
                      {!last && <span className="mt-1 w-px flex-1 bg-border" />}
                    </div>
                    {/* card */}
                    <div className="flex-1 rounded-xl border border-default bg-surface-elevated p-4 shadow-sm">
                      <p className="text-sm leading-relaxed text-foreground">{step.description}</p>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        {step.estimated_time && (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-2.5 py-1 text-xs font-medium text-muted">
                            <Icon path={ICON.clock} className="h-3.5 w-3.5" />
                            {step.estimated_time}
                          </span>
                        )}
                        {step.skill_notes && (
                          <span className="text-xs italic text-muted">{step.skill_notes}</span>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        )}

        {/* Side rail: tools + assumptions + excluded */}
        <div className="space-y-8">
          {buildSheet.tool_list.length > 0 && (
            <section className="as-fade-up" style={{ animationDelay: "140ms" }}>
              <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
                <Icon path={ICON.wrench} className="h-5 w-5 text-accent" />
                Tools needed
              </h3>
              <div className="flex flex-wrap gap-2">
                {buildSheet.tool_list.map((tool: string, i: number) => (
                  <span
                    key={i}
                    className="inline-flex items-center rounded-lg border border-default bg-surface-elevated px-3 py-1.5 text-sm text-foreground shadow-sm"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </section>
          )}

          {assumptions.length > 0 && (
            <section className="as-fade-up" style={{ animationDelay: "200ms" }}>
              <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
                <Icon path={ICON.info} className="h-5 w-5 text-accent" />
                Assumptions
              </h3>
              <ul
                className="space-y-2.5 rounded-xl border-l-2 border-accent bg-surface-elevated p-4 shadow-sm"
                style={{ borderLeftColor: "var(--color-accent)" }}
              >
                {assumptions.map((a, i) => (
                  <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-muted">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {excluded.length > 0 && (
            <section className="as-fade-up" style={{ animationDelay: "240ms" }}>
              <details className="group rounded-xl border border-default bg-surface-elevated shadow-sm">
                <summary className="flex cursor-pointer list-none items-center gap-2 p-4 text-sm font-semibold text-foreground">
                  <Icon path={ICON.alert} className="h-4 w-4 text-muted" />
                  {excluded.length} material{excluded.length > 1 ? "s" : ""} excluded
                  <span className="ml-auto text-xs font-normal text-muted transition group-open:rotate-180">
                    ▾
                  </span>
                </summary>
                <div className="border-t border-default px-4 pb-4 pt-3">
                  <p className="mb-3 text-xs text-muted">
                    These were dropped because their links pointed to a search/category page
                    instead of a specific product. You can still open the candidate link to find
                    the item manually.
                  </p>
                  <ul className="space-y-3">
                    {excluded.map((e, i) => (
                      <li key={i} className="text-sm">
                        <p className="text-foreground">{e.label}</p>
                        <p className="text-xs text-muted">{e.reason}</p>
                        {e.url && (
                          <a
                            href={e.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-0.5 inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
                          >
                            Open candidate link
                            <Icon path={ICON.external} className="h-3 w-3" />
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              </details>
            </section>
          )}
        </div>
      </div>

      {/* ───────────── Materials & costs (full width) ───────────── */}
      <section className="as-fade-up" style={{ animationDelay: "120ms" }}>
        <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
          <Icon path={ICON.layers} className="h-5 w-5 text-accent" />
          Materials &amp; costs
        </h3>
        {hasMaterials ? (
          <div className="overflow-hidden rounded-xl border border-default shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-surface text-left">
                    {[
                      ["Material", "left"],
                      ["Qty", "right"],
                      ["Unit", "left"],
                      ["Unit cost", "right"],
                      ["Total", "right"],
                      ["Vendor", "left"],
                      ["Link", "right"],
                    ].map(([h, align]) => (
                      <th
                        key={h}
                        className={`px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted ${
                          align === "right" ? "text-right" : "text-left"
                        }`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-default bg-surface-elevated">
                  {buildSheet.material_items.map((item: MaterialItem, i: number) => (
                    <tr key={i} className="transition-colors hover:bg-surface">
                      <td className="px-4 py-3 font-medium text-foreground">
                        {item.name}
                        {item.notes && (
                          <span className="block text-xs font-normal text-muted">{item.notes}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-muted [font-variant-numeric:tabular-nums]">
                        {item.quantity}
                      </td>
                      <td className="px-4 py-3 text-muted">{item.unit}</td>
                      <td className="px-4 py-3 text-right text-muted [font-variant-numeric:tabular-nums]">
                        {item.unit_cost_range}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-foreground [font-variant-numeric:tabular-nums]">
                        {item.total_cost_range}
                      </td>
                      <td className="px-4 py-3 text-muted">{item.vendor}</td>
                      <td className="px-4 py-3 text-right">
                        {item.product_url ? (
                          <a
                            href={item.product_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-lg border border-default px-2.5 py-1 text-xs font-medium text-accent transition hover:border-accent"
                          >
                            View
                            <Icon path={ICON.external} className="h-3 w-3" />
                          </a>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-default bg-surface-elevated p-6 text-center">
            <p className="text-sm font-medium text-foreground">No itemized materials available</p>
            <p className="mt-1 text-sm text-muted">
              {excluded.length > 0
                ? `${excluded.length} candidate material${
                    excluded.length > 1 ? "s were" : " was"
                  } dropped because their links pointed to category pages. See "materials excluded" above.`
                : "The materials list came back empty for this build sheet."}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
